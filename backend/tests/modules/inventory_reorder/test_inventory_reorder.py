"""inventory_reorder: suggestion math, sourcing, on-order, generation, isolation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.inventory.models import StockMovement
from app.modules.inventory.schemas import InventoryItemCreate, InventoryItemUpdate
from app.modules.inventory.service import InventoryService
from app.modules.inventory_reorder.service import ReorderService
from app.modules.purchase_orders.schemas import PurchaseOrderCreate, PurchaseOrderLineCreate
from app.modules.purchase_orders.service import PurchaseOrderService
from app.modules.supplier_items.schemas import SupplierItemCreate
from app.modules.supplier_items.service import SupplierItemService
from app.modules.suppliers.schemas import SupplierCreate
from app.modules.suppliers.service import SupplierService


async def _make_supplier(
    db: AsyncSession,
    clinic_id,
    *,
    name="Acme Supplies",
    preferred=False,
    lead_time=5,
) -> tuple:
    return await SupplierService.create_supplier(
        db,
        clinic_id,
        SupplierCreate(
            name=name,
            payment_terms="NET30",
            lead_time_days=lead_time,
            is_preferred=preferred,
        ),
    )


async def _make_item(db: AsyncSession, clinic_id, *, name="Gloves", stock=0, active=True) -> object:
    return await InventoryService.create_item(
        db,
        clinic_id,
        InventoryItemCreate(
            name=name,
            category="consumables",
            unit="units",
            stock_quantity=Decimal(stock),
            unit_cost=Decimal("2.50"),
        ),
        created_by=None,
    )


async def _make_link(db, clinic_id, supplier_id, item_id, *, price="3.00") -> object:
    link, _, _ = await SupplierItemService.create_link(
        db,
        clinic_id,
        SupplierItemCreate(
            supplier_id=supplier_id,
            inventory_item_id=item_id,
            supplier_sku="SKU-1",
            price=Decimal(price),
        ),
    )
    return link


async def _add_consumption(db: AsyncSession, clinic_id, item_id, qty: int, days_ago: int) -> None:
    """Append a past consumption movement directly to the ledger."""
    db.add(
        StockMovement(
            clinic_id=clinic_id,
            inventory_item_id=item_id,
            delta=-Decimal(qty),
            reason="consumption",
            reference_type="treatment_performance",
            reference_id=uuid4(),
            created_at=datetime.now(UTC) - timedelta(days=days_ago),
        )
    )
    await db.commit()


async def _suggestions(db: AsyncSession, clinic_id) -> dict:
    return {
        s["inventory_item_id"]: s for s in await ReorderService.compute_suggestions(db, clinic_id)
    }


async def _open_order(db, clinic_id, supplier_id, item_id, qty=10) -> object:
    return await PurchaseOrderService.create_order(
        db,
        clinic_id,
        PurchaseOrderCreate(
            supplier_id=supplier_id,
            notes="Open reorder",
            lines=[
                PurchaseOrderLineCreate(inventory_item_id=item_id, quantity_ordered=Decimal(qty))
            ],
        ),
        created_by=None,
    )


@pytest.mark.asyncio
async def test_suggestion_math(db_session: AsyncSession, test_clinic: Clinic):
    _, supplier = await _make_supplier(db_session, test_clinic.id, lead_time=5)
    item = await _make_item(db_session, test_clinic.id, name="Gloves", stock=0)
    await _make_link(db_session, test_clinic.id, supplier.id, item.id)

    # 30 units consumed over the last 90 days -> daily_usage 0.33,
    # reorder_point ceil(0.33 * 5) = ceil(1.65) = 2, stock 0 -> suggest 2.
    for days_ago, qty in ((2, 10), (20, 10), (60, 10)):
        await _add_consumption(db_session, test_clinic.id, item.id, qty, days_ago)

    suggestions = await _suggestions(db_session, test_clinic.id)
    suggestion = suggestions[item.id]
    assert suggestion["usage_90d"] == Decimal("30")
    assert suggestion["daily_usage"] == Decimal("0.33")
    assert suggestion["lead_time_days"] == 5
    assert suggestion["reorder_point"] == Decimal("2")
    assert suggestion["stock_quantity"] == Decimal("0")
    assert suggestion["on_order"] == Decimal("0")
    assert suggestion["suggested_quantity"] == Decimal("2")
    assert suggestion["supplier_id"] == supplier.id
    assert suggestion["supplier_name"] == "Acme Supplies"
    assert suggestion["unit_price"] == Decimal("3.00")


@pytest.mark.asyncio
async def test_preferred_supplier_wins_over_first_link(
    db_session: AsyncSession, test_clinic: Clinic
):
    _, regular = await _make_supplier(db_session, test_clinic.id, name="Regular Supplies")
    _, preferred = await _make_supplier(
        db_session, test_clinic.id, name="Preferred Supplies", preferred=True
    )
    item = await _make_item(db_session, test_clinic.id)
    # Linked first to the non-preferred supplier, then the preferred one.
    await _make_link(db_session, test_clinic.id, regular.id, item.id, price="8.00")
    await _make_link(db_session, test_clinic.id, preferred.id, item.id, price="5.50")
    await _add_consumption(db_session, test_clinic.id, item.id, 45, 10)

    suggestions = await _suggestions(db_session, test_clinic.id)
    suggestion = suggestions[item.id]
    assert suggestion["supplier_id"] == preferred.id
    assert suggestion["supplier_name"] == "Preferred Supplies"
    assert suggestion["unit_price"] == Decimal("5.50")


@pytest.mark.asyncio
async def test_on_order_reduces_suggestion(db_session: AsyncSession, test_clinic: Clinic):
    _, supplier = await _make_supplier(db_session, test_clinic.id, lead_time=5)
    item = await _make_item(db_session, test_clinic.id, stock=0)
    await _make_link(db_session, test_clinic.id, supplier.id, item.id)
    await _add_consumption(db_session, test_clinic.id, item.id, 30, 5)

    # Nothing on order -> suggestion 2.
    before = await _suggestions(db_session, test_clinic.id)
    assert before[item.id]["suggested_quantity"] == Decimal("2")

    # A draft PO for 3 covers stock_quantity+on_order projection -> suggest 0.
    await _open_order(db_session, test_clinic.id, supplier.id, item.id, qty=3)
    after = await _suggestions(db_session, test_clinic.id)
    assert item.id not in after


@pytest.mark.asyncio
async def test_exclusions(db_session: AsyncSession, test_clinic: Clinic):
    _, supplier = await _make_supplier(db_session, test_clinic.id, lead_time=5)
    no_usage = await _make_item(db_session, test_clinic.id, name="No usage", stock=0)
    await _make_link(db_session, test_clinic.id, supplier.id, no_usage.id)
    no_link = await _make_item(db_session, test_clinic.id, name="No link", stock=0)
    await _add_consumption(db_session, test_clinic.id, no_link.id, 100, 5)
    inactive = await _make_item(db_session, test_clinic.id, name="Inactive", stock=0)
    await InventoryService.update_item(
        db_session, test_clinic.id, inactive.id, InventoryItemUpdate(is_active=False)
    )
    await _make_link(db_session, test_clinic.id, supplier.id, inactive.id)
    await _add_consumption(db_session, test_clinic.id, inactive.id, 100, 5)
    _, no_lead = await _make_supplier(db_session, test_clinic.id, name="No Lead", lead_time=None)
    no_lead_item = await _make_item(db_session, test_clinic.id, name="No lead time", stock=0)
    await _make_link(db_session, test_clinic.id, no_lead.id, no_lead_item.id)
    await _add_consumption(db_session, test_clinic.id, no_lead_item.id, 100, 5)

    suggestions = await _suggestions(db_session, test_clinic.id)
    assert no_usage.id not in suggestions  # no demand
    assert no_link.id not in suggestions  # no sourcing link
    assert inactive.id not in suggestions  # not active
    assert no_lead_item.id not in suggestions  # lead_time None -> reorder_point 0


@pytest.mark.asyncio
async def test_inactive_link_excluded_from_sourcing(db_session: AsyncSession, test_clinic: Clinic):
    _, supplier = await _make_supplier(db_session, test_clinic.id, lead_time=5)
    item = await _make_item(db_session, test_clinic.id, name="Delisted", stock=0)
    link = await _make_link(db_session, test_clinic.id, supplier.id, item.id)
    await _add_consumption(db_session, test_clinic.id, item.id, 100, 5)
    assert item.id in await _suggestions(db_session, test_clinic.id)

    # Delist the vendor link (revive-on-relink soft-delete) → no sourcing.
    link.is_active = False
    await db_session.commit()
    assert item.id not in await _suggestions(db_session, test_clinic.id)


@pytest.mark.asyncio
async def test_cross_clinic_isolation(db_session: AsyncSession, test_clinic: Clinic):
    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999991",
        address={"street": "Calle Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other_clinic)
    await db_session.commit()

    _, foreign_supplier = await _make_supplier(db_session, other_clinic.id, name="Foreign Supplier")
    foreign_item = await _make_item(db_session, other_clinic.id, name="Foreign Item", stock=0)
    await _make_link(db_session, other_clinic.id, foreign_supplier.id, foreign_item.id)
    await _add_consumption(db_session, other_clinic.id, foreign_item.id, 500, 5)
    await _open_order(db_session, other_clinic.id, foreign_supplier.id, foreign_item.id, qty=200)

    suggestions = await _suggestions(db_session, test_clinic.id)
    assert foreign_item.id not in suggestions
    assert suggestions == {}


@pytest.mark.asyncio
async def test_generate_orders_groups_one_po_per_supplier(
    db_session: AsyncSession, test_clinic: Clinic
):
    _, supplier_a = await _make_supplier(db_session, test_clinic.id, name="Supplier A")
    _, supplier_b = await _make_supplier(db_session, test_clinic.id, name="Supplier B")
    item_a = await _make_item(db_session, test_clinic.id, name="Item A", stock=0)
    item_b = await _make_item(db_session, test_clinic.id, name="Item B", stock=0)
    item_c = await _make_item(db_session, test_clinic.id, name="Item C", stock=0)
    await _make_link(db_session, test_clinic.id, supplier_a.id, item_a.id)
    await _make_link(db_session, test_clinic.id, supplier_a.id, item_b.id)
    await _make_link(db_session, test_clinic.id, supplier_b.id, item_c.id)
    for item in (item_a, item_b, item_c):
        await _add_consumption(db_session, test_clinic.id, item.id, 45, 10)

    orders = await ReorderService.generate_orders(
        db_session, test_clinic.id, [item_a.id, item_b.id, item_c.id], created_by=None
    )
    assert len(orders) == 2
    by_supplier = {o["supplier_id"]: o for o in orders}
    assert set(by_supplier) == {supplier_a.id, supplier_b.id}
    assert {line["item_name"] for line in by_supplier[supplier_a.id]["lines"]} == {
        "Item A",
        "Item B",
    }
    assert {line["item_name"] for line in by_supplier[supplier_b.id]["lines"]} == {"Item C"}
    # All orders start as drafts, 201-able.
    assert all(o["status"] == "draft" for o in orders)
    # The generated POs count as on-order on a re-run.
    remaining = await _suggestions(db_session, test_clinic.id)
    assert item_a.id not in remaining and item_c.id not in remaining


@pytest.mark.asyncio
async def test_generate_orders_400_on_unsuggested_item(
    db_session: AsyncSession, test_clinic: Clinic
):
    _, supplier = await _make_supplier(db_session, test_clinic.id)
    item = await _make_item(db_session, test_clinic.id, name="No demand", stock=0)
    await _make_link(db_session, test_clinic.id, supplier.id, item.id)

    with pytest.raises(HTTPException) as exc:
        await ReorderService.generate_orders(db_session, test_clinic.id, [item.id], created_by=None)
    assert exc.value.status_code == 400
