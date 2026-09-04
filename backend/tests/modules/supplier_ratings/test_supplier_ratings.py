"""supplier_ratings: on-demand metrics + manual review CRUD + tenant isolation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.inventory.schemas import InventoryItemCreate
from app.modules.inventory.service import InventoryService
from app.modules.purchase_orders.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseReceiptCreate,
    ReceiptLineCreate,
    StatusTransition,
)
from app.modules.purchase_orders.service import PurchaseOrderService
from app.modules.supplier_ratings.schemas import (
    SupplierRatingMetrics,
    SupplierReviewCreate,
    SupplierReviewUpdate,
)
from app.modules.supplier_ratings.service import SupplierRatingsService
from app.modules.suppliers.schemas import SupplierCreate
from app.modules.suppliers.service import SupplierService


async def _make_supplier(db: AsyncSession, clinic_id, *, name="Acme Supplies") -> tuple:
    return await SupplierService.create_supplier(
        db, clinic_id, SupplierCreate(name=name, payment_terms="NET30", lead_time_days=5)
    )


async def _make_item(db: AsyncSession, clinic_id, *, name="Composite A2") -> object:
    return await InventoryService.create_item(
        db,
        clinic_id,
        InventoryItemCreate(name=name, category="consumables", unit_cost=Decimal("12.50")),
        created_by=None,
    )


async def _make_order(
    db: AsyncSession, clinic_id, supplier_id, item_id, *, qty=10, expected_date=None
) -> object:
    return await PurchaseOrderService.create_order(
        db,
        clinic_id,
        PurchaseOrderCreate(
            supplier_id=supplier_id,
            notes="Rating test order",
            expected_date=expected_date,
            lines=[
                PurchaseOrderLineCreate(inventory_item_id=item_id, quantity_ordered=Decimal(qty))
            ],
        ),
        created_by=None,
    )


async def _receive_all(
    db: AsyncSession,
    clinic_id,
    order,
    *,
    good=10,
    rejected=0,
) -> object:
    await PurchaseOrderService.transition_order(
        db, clinic_id, order.id, StatusTransition(status="sent")
    )
    await PurchaseOrderService.transition_order(
        db, clinic_id, order.id, StatusTransition(status="confirmed")
    )
    line = (await PurchaseOrderService.list_lines(db, clinic_id, order.id))[0]
    lines = []
    if good:
        lines.append(
            ReceiptLineCreate(
                purchase_order_line_id=line.id,
                quantity_received=Decimal(str(good)),
                quality="good",
            )
        )
    if rejected:
        lines.append(
            ReceiptLineCreate(
                purchase_order_line_id=line.id,
                quantity_received=Decimal(str(rejected)),
                quality="rejected",
            )
        )
    return await PurchaseOrderService.receive_order(
        db,
        clinic_id,
        order.id,
        PurchaseReceiptCreate(lines=lines),
        received_by=None,
    )


@pytest.mark.asyncio
async def test_metrics_on_time_and_reject_rates(db_session: AsyncSession, test_clinic: Clinic):
    _, supplier = await _make_supplier(db_session, test_clinic.id)
    item = await _make_item(db_session, test_clinic.id)

    # Two late deliveries (due yesterday), full receipts.
    for _ in range(2):
        order = await _make_order(
            db_session, test_clinic.id, supplier.id, item.id, qty=10, expected_date=date(2000, 1, 1)
        )
        await _receive_all(db_session, test_clinic.id, order)

    # One on-time delivery (due in the future) with 3 rejected units.
    # Rejected units never fulfil a line (L26): the rejection is recorded
    # first (order stays open), then the full good quantity closes it.
    order = await _make_order(
        db_session, test_clinic.id, supplier.id, item.id, qty=13, expected_date=date(2100, 1, 1)
    )
    await PurchaseOrderService.transition_order(
        db_session, test_clinic.id, order.id, StatusTransition(status="sent")
    )
    await PurchaseOrderService.transition_order(
        db_session, test_clinic.id, order.id, StatusTransition(status="confirmed")
    )
    line = (await PurchaseOrderService.list_lines(db_session, test_clinic.id, order.id))[0]
    await PurchaseOrderService.receive_order(
        db_session,
        test_clinic.id,
        order.id,
        PurchaseReceiptCreate(
            lines=[
                ReceiptLineCreate(
                    purchase_order_line_id=line.id,
                    quantity_received=Decimal(3),
                    quality="rejected",
                )
            ]
        ),
        received_by=None,
    )
    await PurchaseOrderService.receive_order(
        db_session,
        test_clinic.id,
        order.id,
        PurchaseReceiptCreate(
            lines=[
                ReceiptLineCreate(
                    purchase_order_line_id=line.id,
                    quantity_received=Decimal(13),
                    quality="good",
                )
            ]
        ),
        received_by=None,
    )

    # One draft PO not received yet.
    await _make_order(db_session, test_clinic.id, supplier.id, item.id, qty=10)

    result, _ = await SupplierRatingsService.get_ratings(db_session, test_clinic.id, supplier.id)
    metrics: SupplierRatingMetrics = result["metrics"]

    assert metrics.po_count == 4
    assert metrics.received_count == 3
    assert metrics.received_with_due_date == 3
    assert metrics.on_time_deliveries == 1
    assert metrics.on_time_rate == Decimal("0.33")
    # 2 late x 10 good = 20 good; on-time 13 good + 3 rejected = 16.
    assert metrics.received_quantity == Decimal("36")
    assert metrics.rejected_quantity == Decimal("3")
    assert metrics.reject_rate == Decimal("0.08")


@pytest.mark.asyncio
async def test_metrics_with_no_due_date_exclude_from_total(
    db_session: AsyncSession, test_clinic: Clinic
):
    _, supplier = await _make_supplier(db_session, test_clinic.id)
    item = await _make_item(db_session, test_clinic.id)

    # Received with no expected_date → counts as received but not in total.
    order = await _make_order(db_session, test_clinic.id, supplier.id, item.id, qty=5)
    await _receive_all(db_session, test_clinic.id, order, good=5)

    result, _ = await SupplierRatingsService.get_ratings(db_session, test_clinic.id, supplier.id)
    metrics = result["metrics"]
    assert metrics.po_count == 1
    assert metrics.received_count == 1
    assert metrics.received_with_due_date == 0
    assert metrics.on_time_rate is None
    # Actually received quantity is still counted.
    assert metrics.received_quantity == Decimal("5")
    assert metrics.reject_rate == Decimal("0.00")


@pytest.mark.asyncio
async def test_list_ratings_paginated(db_session: AsyncSession, test_clinic: Clinic):
    _, a = await _make_supplier(db_session, test_clinic.id, name="Alpha Supply")
    _, b = await _make_supplier(db_session, test_clinic.id, name="Beta Materials")
    # Beta gets a lower average via two reviews; Alpha none.
    await SupplierRatingsService.create_review(
        db_session,
        test_clinic.id,
        SupplierReviewCreate(supplier_id=b.id, score=4, comment="fast replies"),
        created_by=None,
    )

    items, total = await SupplierRatingsService.list_ratings(db_session, test_clinic.id)
    assert total == 2
    names = [i["supplier_name"] for i in items]
    assert names == ["Alpha Supply", "Beta Materials"]
    by_name = {i["supplier_name"]: i for i in items}
    assert by_name["Alpha Supply"]["review"] is None
    assert by_name["Beta Materials"]["review"].score == 4
    assert by_name["Alpha Supply"]["metrics"].po_count == 0


@pytest.mark.asyncio
async def test_review_crud_and_conflict(db_session: AsyncSession, test_clinic: Clinic):
    _, supplier = await _make_supplier(db_session, test_clinic.id)

    created = await SupplierRatingsService.create_review(
        db_session,
        test_clinic.id,
        SupplierReviewCreate(supplier_id=supplier.id, score=3, comment="ok"),
        created_by=None,
    )
    assert created.score == 3

    # A second rating for the same supplier conflicts.
    with pytest.raises(HTTPException) as exc:
        await SupplierRatingsService.create_review(
            db_session,
            test_clinic.id,
            SupplierReviewCreate(supplier_id=supplier.id, score=5, comment="dup"),
            created_by=None,
        )
    assert exc.value.status_code == 409

    updated = await SupplierRatingsService.update_review(
        db_session, test_clinic.id, created.id, SupplierReviewUpdate(score=5, comment="great")
    )
    assert updated.score == 5
    assert updated.comment == "great"

    review, contact = await SupplierRatingsService.get_review(
        db_session, test_clinic.id, created.id
    )
    assert review.id == created.id
    assert contact.name == "Acme Supplies"

    await SupplierRatingsService.delete_review(db_session, test_clinic.id, created.id)
    with pytest.raises(HTTPException) as exc:
        await SupplierRatingsService.get_review(db_session, test_clinic.id, created.id)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_score_bounds_are_validated():
    with pytest.raises(ValidationError):
        SupplierReviewCreate(supplier_id=uuid4(), score=0)
    with pytest.raises(ValidationError):
        SupplierReviewCreate(supplier_id=uuid4(), score=6)


@pytest.mark.asyncio
async def test_rating_endpoints_clinic_isolated(db_session: AsyncSession, test_clinic: Clinic):
    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999991",
        address={"street": "Calle Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other_clinic)
    await db_session.commit()

    _, foreign_supplier = await _make_supplier(db_session, other_clinic.id, name="Other Supplier")

    # Review created in the other clinic is invisible here.
    await SupplierRatingsService.create_review(
        db_session,
        other_clinic.id,
        SupplierReviewCreate(supplier_id=foreign_supplier.id, score=2, comment="foreign"),
        created_by=None,
    )
    items, total = await SupplierRatingsService.list_ratings(db_session, test_clinic.id)
    assert total == 0

    # Cannot rate a foreign supplier from this clinic (unknown supplier id is a 404).
    with pytest.raises(HTTPException) as exc:
        await SupplierRatingsService.create_review(
            db_session,
            test_clinic.id,
            SupplierReviewCreate(supplier_id=foreign_supplier.id, score=5, comment="nope"),
            created_by=None,
        )
    assert exc.value.status_code == 404

    # Detail lookup for a foreign supplier is a 404 here.
    with pytest.raises(HTTPException) as exc:
        await SupplierRatingsService.get_ratings(db_session, test_clinic.id, foreign_supplier.id)
    assert exc.value.status_code == 404
