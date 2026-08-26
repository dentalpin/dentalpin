"""inventory core upgrade (#226): auto-deduction driven by
treatment_consumables links when a treatment is performed.

The links table belongs to the treatment_consumables module (not merged
into this branch's base), so these tests create it with raw DDL — the
same shape its migration produces. That also exercises the fail-soft
inspector path: without the table, deduction is a logged no-op.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.events import event_bus
from app.core.events.types import EventType
from app.modules.inventory.models import StockMovement
from app.modules.inventory.schemas import InventoryItemCreate
from app.modules.inventory.service import InventoryService


async def _create_links_table(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS treatment_consumables (
                id UUID PRIMARY KEY,
                clinic_id UUID NOT NULL,
                catalog_item_id UUID NOT NULL,
                inventory_item_id UUID NOT NULL,
                quantity NUMERIC(10, 2) NOT NULL
            )
            """
        )
    )


async def _seed_link(db_session: AsyncSession, clinic_id, catalog_item_id, item_id, quantity):
    await db_session.execute(
        text(
            "INSERT INTO treatment_consumables (id, clinic_id, catalog_item_id, "
            "inventory_item_id, quantity) VALUES (:id, :c, :cat, :inv, :q)"
        ),
        {
            "id": str(uuid4()),
            "c": str(clinic_id),
            "cat": str(catalog_item_id),
            "inv": str(item_id),
            "q": quantity,
        },
    )


def _performance_payload(clinic_id, catalog_item_id, treatment_id=None, actor=None):
    payload = {
        "clinic_id": str(clinic_id),
        "catalog_item_id": str(catalog_item_id),
        "treatment_id": str(treatment_id or uuid4()),
    }
    if actor:
        payload["performed_by"] = str(actor)
    return payload


@pytest.mark.asyncio
async def test_deduction_clamps_at_zero_and_records_partial(
    db_session: AsyncSession, test_clinic: Clinic
):
    """Underflow floors at zero — clinical care is never blocked by
    bookkeeping — and the movement records what was actually applied."""
    await _create_links_table(db_session)
    item = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(
            name="Scarce item", category="consumables", stock_quantity=Decimal("1")
        ),
        created_by=None,
    )
    catalog_item_id = uuid4()
    await _seed_link(db_session, test_clinic.id, catalog_item_id, item.id, 4)

    applied = await InventoryService.deduct_for_treatment(
        db_session,
        clinic_id=test_clinic.id,
        catalog_item_id=catalog_item_id,
        treatment_reference_id=uuid4(),
        actor_id=None,
    )

    # refresh() discards un-flushed in-memory changes — flush first so the
    # deduction (held by the caller's transaction, ADR 0019) is written.
    await db_session.flush()
    await db_session.refresh(item)
    assert item.stock_quantity == Decimal("0")  # clamped, never negative
    assert len(applied) == 1
    assert applied[0]["requested"] == 4.0
    assert applied[0]["applied"] == -1.0


@pytest.mark.asyncio
async def test_no_links_means_no_op(db_session: AsyncSession, test_clinic: Clinic):
    await _create_links_table(db_session)
    item = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(name="Unlinked", category="other", stock_quantity=Decimal("9")),
        created_by=None,
    )
    applied = await InventoryService.deduct_for_treatment(
        db_session,
        clinic_id=test_clinic.id,
        catalog_item_id=uuid4(),  # no links for this treatment
        treatment_reference_id=None,
        actor_id=None,
    )
    assert applied == []
    await db_session.refresh(item)
    assert item.stock_quantity == Decimal("9")


@pytest.mark.asyncio
async def test_missing_links_table_is_a_logged_no_op(db_session: AsyncSession, test_clinic: Clinic):
    """Soft runtime coupling: treatment_consumables absent → skip cleanly."""
    item = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(name="Whatever", category="other", stock_quantity=Decimal("3")),
        created_by=None,
    )
    applied = await InventoryService.deduct_for_treatment(
        db_session,
        clinic_id=test_clinic.id,
        catalog_item_id=uuid4(),
        treatment_reference_id=None,
        actor_id=None,
    )
    assert applied == []
    await db_session.refresh(item)
    assert item.stock_quantity == Decimal("3")


@pytest.mark.asyncio
async def test_auto_deduction_on_treatment_performed(db_session: AsyncSession, test_clinic: Clinic):
    await _create_links_table(db_session)
    item = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(
            name="Anesthetic vial", category="consumables", stock_quantity=Decimal("10")
        ),
        created_by=None,
    )
    catalog_item_id = uuid4()
    await _seed_link(db_session, test_clinic.id, catalog_item_id, item.id, 2)

    await event_bus.publish(
        EventType.ODONTOGRAM_TREATMENT_PERFORMED,
        _performance_payload(test_clinic.id, catalog_item_id),
        db=db_session,
    )
    await db_session.refresh(item)

    # 10 - 2 = 8 and a consumption movement referencing the performance.
    assert item.stock_quantity == Decimal("8")
    movements, total = await InventoryService.list_movements(
        db_session, test_clinic.id, inventory_item_id=item.id
    )
    assert total == 2
    consumption = movements[0]  # newest first
    assert consumption.reason == "consumption"
    assert consumption.delta == Decimal("-2")
    assert consumption.reference_type == "treatment_performance"
    assert consumption.reference_id is not None


@pytest.mark.asyncio
async def test_rollback_discards_deduction(db_session: AsyncSession, test_clinic: Clinic):
    """ADR 0019: a rolled-back treatment must not consume stock.

    The clinic id is captured before publish/rollback — rollback expires
    ORM attributes and touching them afterwards raises MissingGreenlet.
    """
    clinic_id = test_clinic.id
    await _create_links_table(db_session)
    item = await InventoryService.create_item(
        db_session,
        clinic_id,
        InventoryItemCreate(name="Syringes", category="consumables", stock_quantity=Decimal("6")),
        created_by=None,
    )
    await _seed_link(db_session, clinic_id, uuid4(), item.id, 1)

    await event_bus.publish(
        EventType.ODONTOGRAM_TREATMENT_PERFORMED,
        _performance_payload(clinic_id, uuid4()),
        db=db_session,
    )
    await db_session.rollback()

    movements = (
        (
            await db_session.execute(
                select(StockMovement).where(StockMovement.clinic_id == clinic_id)
            )
        )
        .scalars()
        .all()
    )
    # The opening-stock movement was committed by create_item before the
    # publish; only the deduction must be gone.
    assert all(m.reason != "consumption" for m in movements)
