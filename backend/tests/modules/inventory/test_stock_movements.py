"""inventory core upgrade (#226): movements ledger, valuation, audit trail."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.inventory.schemas import InventoryItemCreate, InventoryItemUpdate
from app.modules.inventory.service import InventoryService


@pytest.mark.asyncio
async def test_opening_stock_and_adjustments_are_ledgered(
    db_session: AsyncSession, test_clinic: Clinic
):
    item = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(
            name="Gloves M",
            category="consumables",
            stock_quantity=Decimal("10"),
            unit_cost=Decimal("4.5"),
        ),
        created_by=None,
    )

    await InventoryService.adjust_stock(
        db_session,
        test_clinic.id,
        item.id,
        Decimal("-3"),
        reason="consumption",
        note="clinic use",
        created_by=None,
    )
    await InventoryService.adjust_stock(
        db_session,
        test_clinic.id,
        item.id,
        Decimal("50"),
        reason="restock",
        created_by=None,
    )
    # Underflow is rejected AND leaves no ledger row.
    with pytest.raises(HTTPException) as exc_info:
        await InventoryService.adjust_stock(db_session, test_clinic.id, item.id, Decimal("-999"))
    assert exc_info.value.status_code == 409

    movements, total = await InventoryService.list_movements(db_session, test_clinic.id)
    assert total == 3  # initial(10) -3 +50 — the rejected one never lands
    assert sum(m["movement"].delta for m in movements) == Decimal("57")

    # Look rows up by reason: created_at ties are possible within one
    # transaction, so positional indexing would be flaky.
    by_reason = {m["movement"]["reason"]: m["movement"] for m in movements}
    assert by_reason["initial"].delta == Decimal("10")
    consumption = by_reason["consumption"]
    assert consumption.delta == Decimal("-3")
    assert consumption.note == "clinic use"
    assert by_reason["restock"].delta == Decimal("50")


@pytest.mark.asyncio
async def test_absolute_patch_set_records_correction(db_session: AsyncSession, test_clinic: Clinic):
    item = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(name="Composite", category="consumables", stock_quantity=Decimal("8")),
        created_by=None,
    )
    updated = await InventoryService.update_item(
        db_session,
        test_clinic.id,
        item.id,
        InventoryItemUpdate(stock_quantity=Decimal("5")),
    )
    assert updated.stock_quantity == Decimal("5")

    movements, _ = await InventoryService.list_movements(db_session, test_clinic.id)
    correction = next(m["movement"] for m in movements if m["movement"].reason == "correction")
    assert correction.delta == Decimal("-3")


@pytest.mark.asyncio
async def test_delete_blocked_with_history_allowed_without(
    db_session: AsyncSession, test_clinic: Clinic
):
    """Items with ledger history are deactivated instead of erased — the
    audit trail must never be deleted."""
    with_history = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(name="With history", category="office", stock_quantity=Decimal("5")),
        created_by=None,
    )
    without = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(name="No history", category="office", stock_quantity=Decimal("0")),
        created_by=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await InventoryService.delete_item(db_session, test_clinic.id, with_history.id)
    assert exc_info.value.status_code == 409

    await InventoryService.delete_item(db_session, test_clinic.id, without.id)
    rows, total = await InventoryService.list_items(
        db_session, test_clinic.id, include_inactive=True
    )
    assert {r.name for r in rows} == {"With history"}


@pytest.mark.asyncio
async def test_valuation(db_session: AsyncSession, test_clinic: Clinic):
    await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(
            name="Valued",
            category="consumables",
            stock_quantity=Decimal("10"),
            unit_cost=Decimal("2.50"),
        ),
        created_by=None,
    )
    await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(name="Unknown cost", category="office"),
        created_by=None,
    )
    result = await InventoryService.stock_valuation(db_session, test_clinic.id)
    assert result["total_value"] == Decimal("25.00")
    assert result["valued_items"] == 1
    assert result["unvalued_items"] == 1


@pytest.mark.asyncio
async def test_movements_http_is_clinic_scoped(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
):
    item = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(name="Clinic A item", category="other", stock_quantity=Decimal("4")),
        created_by=None,
    )

    res = await client.get(f"/api/v1/inventory/{item.id}/movements", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 1
    assert Decimal(body["data"][0]["delta"]) == Decimal("4")
    assert body["data"][0]["reason"] == "initial"

    # A foreign/nonexistent item id → scoped 404.
    res = await client.get(f"/api/v1/inventory/{uuid4()}/movements", headers=auth_headers)
    assert res.status_code == 404

    res = await client.get("/api/v1/inventory/valuation", headers=auth_headers)
    assert res.status_code == 200, res.text
