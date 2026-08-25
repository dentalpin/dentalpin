"""inventory: service CRUD, atomic adjustments and tenant isolation."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.events import event_bus
from app.core.events.types import EventType
from app.modules.inventory.schemas import (
    InventoryItemCreate,
    InventoryItemUpdate,
)
from app.modules.inventory.service import InventoryService


@pytest.mark.asyncio
async def test_create_list_update_delete(db_session: AsyncSession, test_clinic: Clinic):
    item = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(
            name="Composite A2",
            category="consumables",
            unit="syringes",
            stock_quantity=Decimal("25"),
            min_quantity=Decimal("5"),
        ),
        created_by=None,
    )
    assert item.stock_quantity == Decimal("25")
    assert item.is_low_stock is False

    rows, total = await InventoryService.list_items(db_session, test_clinic.id)
    assert total == 1
    assert rows[0].id == item.id

    updated = await InventoryService.update_item(
        db_session,
        test_clinic.id,
        item.id,
        InventoryItemUpdate(min_quantity=Decimal("30")),
    )
    # 25 stock vs a raised threshold of 30 -> now low.
    assert updated.is_low_stock is True

    # The item has ledger history (opening stock) — deletion is refused
    # in favour of deactivation so the audit trail survives (#226).
    with pytest.raises(HTTPException) as exc_info:
        await InventoryService.delete_item(db_session, test_clinic.id, item.id)
    assert exc_info.value.status_code == 409

    deactivated = await InventoryService.update_item(
        db_session,
        test_clinic.id,
        item.id,
        InventoryItemUpdate(is_active=False),
    )
    assert deactivated.is_active is False
    rows, total = await InventoryService.list_items(db_session, test_clinic.id)
    assert total == 0  # inactive rows are hidden by default
    rows, total = await InventoryService.list_items(
        db_session, test_clinic.id, include_inactive=True
    )
    assert total == 1


@pytest.mark.asyncio
async def test_adjust_stock_is_atomic_and_guards_negative(
    db_session: AsyncSession, test_clinic: Clinic
):
    """PR #153 post-mortem: quantity changes must be atomic DB updates with
    a floor guard — not read-modify-write in the app."""
    item = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(name="Gloves M", category="consumables", stock_quantity=Decimal("10")),
        created_by=None,
    )

    restocked = await InventoryService.adjust_stock(
        db_session, test_clinic.id, item.id, Decimal("-3")
    )
    assert restocked.stock_quantity == Decimal("7")

    restocked = await InventoryService.adjust_stock(
        db_session, test_clinic.id, item.id, Decimal("5")
    )
    assert restocked.stock_quantity == Decimal("12")

    # -20 would drive it negative -> rejected at the atomic UPDATE.
    with pytest.raises(HTTPException) as exc_info:
        await InventoryService.adjust_stock(db_session, test_clinic.id, item.id, Decimal("-20"))
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_low_stock_filter(db_session: AsyncSession, test_clinic: Clinic):
    low = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(
            name="Suction tips",
            category="consumables",
            stock_quantity=Decimal("2"),
            min_quantity=Decimal("10"),
        ),
        created_by=None,
    )
    ok = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(
            name="Impression trays",
            category="equipment",
            stock_quantity=Decimal("50"),
            min_quantity=Decimal("5"),
        ),
        created_by=None,
    )

    low_rows, low_total = await InventoryService.list_items(
        db_session, test_clinic.id, low_stock_only=True
    )
    assert low_total == 1
    assert low_rows[0].id == low.id
    assert low_rows[0].is_low_stock is True

    all_rows, all_total = await InventoryService.list_items(db_session, test_clinic.id)
    assert all_total == 2
    assert {r.id for r in all_rows} == {low.id, ok.id}
    assert next(r for r in all_rows if r.id == ok.id).is_low_stock is False


@pytest.mark.asyncio
async def test_low_stock_event_fires_only_on_crossing(
    db_session: AsyncSession, test_clinic: Clinic
):
    """``inventory.low_stock`` fires once per not-low → low crossing:
    on the crossing adjustment, not again while already low, and again
    only after recovering above the threshold. Creation at/below the
    threshold counts as a crossing."""
    captured: list[dict] = []

    async def _spy(data: dict) -> None:
        captured.append(data)

    event_bus.subscribe(EventType.INVENTORY_STOCK_LOW, _spy)
    try:
        item = await InventoryService.create_item(
            db_session,
            test_clinic.id,
            InventoryItemCreate(
                name="Anesthetic carpules",
                category="consumables",
                stock_quantity=Decimal("10"),
                min_quantity=Decimal("5"),
            ),
            created_by=None,
        )
        assert captured == []  # created above threshold — no alert

        await InventoryService.adjust_stock(db_session, test_clinic.id, item.id, Decimal("-5"))
        assert len(captured) == 1  # 10 -> 5 crosses the threshold
        assert captured[0]["item_id"] == str(item.id)
        assert captured[0]["clinic_id"] == str(test_clinic.id)

        await InventoryService.adjust_stock(db_session, test_clinic.id, item.id, Decimal("-2"))
        assert len(captured) == 1  # still low — no re-fire

        await InventoryService.adjust_stock(db_session, test_clinic.id, item.id, Decimal("20"))
        await InventoryService.adjust_stock(db_session, test_clinic.id, item.id, Decimal("-19"))
        assert len(captured) == 2  # recovered, then crossed again

        born_low = await InventoryService.create_item(
            db_session,
            test_clinic.id,
            InventoryItemCreate(
                name="Etch gel",
                category="consumables",
                stock_quantity=Decimal("0"),
                min_quantity=Decimal("3"),
            ),
            created_by=None,
        )
        assert len(captured) == 3  # already-low creation is a day-one alert
        assert captured[2]["item_id"] == str(born_low.id)
    finally:
        event_bus.unsubscribe(EventType.INVENTORY_STOCK_LOW, _spy)


@pytest.mark.asyncio
async def test_items_are_clinic_scoped(db_session: AsyncSession, test_clinic: Clinic):
    other_clinic = Clinic(
        id=uuid4(), name="Other Clinic", tax_id="B11111111", address={}, settings={}
    )
    db_session.add(other_clinic)
    await db_session.commit()

    other_item = await InventoryService.create_item(
        db_session,
        other_clinic.id,
        InventoryItemCreate(name="Other clinic stock", category="other"),
        created_by=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await InventoryService.get_item(db_session, test_clinic.id, other_item.id)
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await InventoryService.adjust_stock(db_session, test_clinic.id, other_item.id, Decimal("5"))
    assert exc_info.value.status_code == 404

    rows, total = await InventoryService.list_items(db_session, test_clinic.id)
    assert total == 0
