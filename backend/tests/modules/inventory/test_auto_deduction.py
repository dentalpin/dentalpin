"""inventory core upgrade (#226): auto-deduction driven by
treatment_consumables links when a treatment is performed.

These tests exercise ``InventoryService.apply_consumption`` (the clean
public primitive) and the event-bus round-trip through
``treatment_consumables.events.on_treatment_performed`` which resolves
links with its own ORM model.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.events import event_bus
from app.core.events.types import EventType
from app.modules.inventory.models import StockMovement
from app.modules.inventory.schemas import InventoryItemCreate
from app.modules.inventory.service import InventoryService


async def _create_links_table(db_session: AsyncSession) -> None:
    # IF NOT EXISTS + the fixture's teardown DROP are both required: this
    # raw table is NOT in Base.metadata, so conftest's drop_all never
    # removes it — a leak would poison the shared CI database and make the
    # later alembic-roundtrip step report schema drift.
    await db_session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS treatment_consumables (
                id UUID PRIMARY KEY,
                clinic_id UUID NOT NULL,
                catalog_item_id UUID NOT NULL,
                inventory_item_id UUID NOT NULL,
                quantity NUMERIC(10, 2) NOT NULL DEFAULT 1,
                note VARCHAR(200),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )


@pytest_asyncio.fixture
async def links_table(db_session: AsyncSession):
    """Raw treatment_consumables table, dropped again on teardown.

    ``create_all`` creates the table from the ORM model which uses
    a Python-side default only — the INSERT via raw SQL then hits the
    NOT NULL guard.  Drop that and recreate with the raw DDL that
    carries ``DEFAULT now()`` so raw INSERTs work.
    """
    await db_session.execute(text("DROP TABLE IF EXISTS treatment_consumables"))
    await db_session.commit()
    await _create_links_table(db_session)
    await db_session.commit()
    yield
    await db_session.execute(text("DROP TABLE IF EXISTS treatment_consumables"))
    await db_session.commit()


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
    db_session: AsyncSession, test_clinic: Clinic, links_table
):
    """Underflow floors at zero — clinical care is never blocked by
    bookkeeping — and the movement records what was actually applied."""
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

    # Resolve links the way treatment_consumables/events.py does.
    from app.modules.treatment_consumables.models import TreatmentConsumable
    rows = (
        await db_session.execute(
            select(TreatmentConsumable.inventory_item_id, TreatmentConsumable.quantity).where(
                TreatmentConsumable.clinic_id == test_clinic.id,
                TreatmentConsumable.catalog_item_id == catalog_item_id,
            )
        )
    ).all()
    links = [(r.inventory_item_id, Decimal(str(r.quantity))) for r in rows]

    applied = await InventoryService.apply_consumption(
        db_session,
        clinic_id=test_clinic.id,
        links=links,
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
async def test_no_links_means_no_op(db_session: AsyncSession, test_clinic: Clinic, links_table):
    item = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(name="Unlinked", category="other", stock_quantity=Decimal("9")),
        created_by=None,
    )
    # Empty links list → no deduction (mirrors treatment_consumables
    # returning early when no rows match).
    applied = await InventoryService.apply_consumption(
        db_session,
        clinic_id=test_clinic.id,
        links=[],
        treatment_reference_id=None,
        actor_id=None,
    )
    assert applied == []
    await db_session.refresh(item)
    assert item.stock_quantity == Decimal("9")


@pytest.mark.asyncio
async def test_deduction_with_zero_links(
    db_session: AsyncSession, test_clinic: Clinic, links_table
):
    """apply_consumption with an empty links list is a no-op — the
    caller (treatment_consumables) returns early when no rows match."""
    item = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(name="Whatever", category="other", stock_quantity=Decimal("3")),
        created_by=None,
    )
    applied = await InventoryService.apply_consumption(
        db_session,
        clinic_id=test_clinic.id,
        links=[],
        treatment_reference_id=None,
        actor_id=None,
    )
    assert applied == []
    await db_session.refresh(item)
    assert item.stock_quantity == Decimal("3")


@pytest.mark.asyncio
async def test_auto_deduction_on_treatment_performed(
    db_session: AsyncSession, test_clinic: Clinic, links_table
):
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
    # flush() is required: the handler's changes live in the caller's
    # uncommitted transaction — refresh() without flush discards them.
    await db_session.flush()
    await db_session.refresh(item)

    # 10 - 2 = 8 and a consumption movement referencing the performance.
    assert item.stock_quantity == Decimal("8")
    movements, total = await InventoryService.list_movements(
        db_session, test_clinic.id, inventory_item_id=item.id
    )
    assert total == 2
    consumption = movements[0]["movement"]  # newest first
    assert consumption.reason == "consumption"
    assert consumption.delta == Decimal("-2")
    assert consumption.reference_type == "treatment_performance"
    assert consumption.reference_id is not None


@pytest.mark.asyncio
async def test_rollback_discards_deduction(
    db_session: AsyncSession, test_clinic: Clinic, links_table
):
    """ADR 0019: a rolled-back treatment must not consume stock.

    The clinic id is captured before publish/rollback — rollback expires
    ORM attributes and touching them afterwards raises MissingGreenlet.
    """
    clinic_id = test_clinic.id
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


@pytest.mark.asyncio
async def test_auto_deduction_is_idempotent(
    db_session: AsyncSession, test_clinic: Clinic, links_table
):
    """Double-deduction for the same treatment produces only one consumption
    row — the partial unique index makes the second a no-op (#226)."""
    item = await InventoryService.create_item(
        db_session,
        test_clinic.id,
        InventoryItemCreate(
            name="Gauze pads", category="consumables", stock_quantity=Decimal("10")
        ),
        created_by=None,
    )
    catalog_item_id = uuid4()
    treatment_id = uuid4()
    await _seed_link(db_session, test_clinic.id, catalog_item_id, item.id, 3)

    payload = _performance_payload(test_clinic.id, catalog_item_id, treatment_id=treatment_id)

    # First publish — deducts 3.
    await event_bus.publish(
        EventType.ODONTOGRAM_TREATMENT_PERFORMED, payload, db=db_session
    )
    await db_session.flush()

    # Second publish — same treatment_id, same reference_id → idempotent.
    await event_bus.publish(
        EventType.ODONTOGRAM_TREATMENT_PERFORMED, payload, db=db_session
    )
    await db_session.flush()

    await db_session.refresh(item)
    # Stock: 10 - 3 = 7 (not 4).
    assert item.stock_quantity == Decimal("7")

    movements, total = await InventoryService.list_movements(
        db_session, test_clinic.id, inventory_item_id=item.id
    )
    consumption_rows = [m for m in movements if m["movement"].reason == "consumption"]
    assert len(consumption_rows) == 1
    assert consumption_rows[0]["movement"].delta == Decimal("-3")
