"""purchase_orders: PO lifecycle, batch receiving, tenant isolation."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.inventory.schemas import InventoryItemCreate
from app.modules.inventory.service import InventoryService
from app.modules.purchase_orders.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderUpdate,
    PurchaseReceiptCreate,
    ReceiptLineCreate,
    StatusTransition,
)
from app.modules.purchase_orders.service import PurchaseOrderService
from app.modules.suppliers.schemas import SupplierCreate
from app.modules.suppliers.service import SupplierService


async def _make_supplier(db: AsyncSession, clinic_id, *, name="Acme Supplies") -> object:
    contact, _ = await SupplierService.create_supplier(
        db, clinic_id, SupplierCreate(name=name, payment_terms="NET30", lead_time_days=5)
    )
    return contact


async def _make_item(db: AsyncSession, clinic_id, *, name="Composite A2") -> object:
    return await InventoryService.create_item(
        db,
        clinic_id,
        InventoryItemCreate(name=name, category="consumables", unit_cost=Decimal("12.50")),
        created_by=None,
    )


async def _make_order(db: AsyncSession, clinic_id, supplier_id, item_id, *, qty=10) -> object:
    return await PurchaseOrderService.create_order(
        db,
        clinic_id,
        PurchaseOrderCreate(
            supplier_id=supplier_id,
            notes="First reorder",
            lines=[
                PurchaseOrderLineCreate(inventory_item_id=item_id, quantity_ordered=Decimal(qty))
            ],
        ),
        created_by=None,
    )


async def _line_of(db: AsyncSession, clinic_id, order_id) -> object:
    return (await PurchaseOrderService.list_lines(db, clinic_id, order_id))[0]


@pytest.mark.asyncio
async def test_lifecycle_and_receiving(db_session: AsyncSession, test_clinic: Clinic):
    supplier = await _make_supplier(db_session, test_clinic.id)
    item = await _make_item(db_session, test_clinic.id, name="Gloves")
    order = await _make_order(db_session, test_clinic.id, supplier.id, item.id, qty=10)

    assert order.status == "draft"

    responses, total = await PurchaseOrderService.list_order_responses(db_session, test_clinic.id)
    assert total == 1
    assert responses[0]["supplier_name"] == "Acme Supplies"
    assert responses[0]["lines"][0]["item_name"] == "Gloves"

    detail = await PurchaseOrderService.get_order_response(db_session, test_clinic.id, order.id)
    assert detail["status"] == "draft"

    # draft -> sent -> confirmed
    order = await PurchaseOrderService.transition_order(
        db_session, test_clinic.id, order.id, StatusTransition(status="sent")
    )
    assert order.status == "sent"
    order = await PurchaseOrderService.transition_order(
        db_session, test_clinic.id, order.id, StatusTransition(status="confirmed")
    )
    assert order.status == "confirmed"

    # 7 good + 3 rejected: good moves stock, rejected neither moves stock nor
    # fulfils the line, so the order stays open for the replacement.
    line = await _line_of(db_session, test_clinic.id, order.id)
    item_before = await InventoryService.get_item(db_session, test_clinic.id, item.id)
    assert item_before.stock_quantity == 0

    order = await PurchaseOrderService.receive_order(
        db_session,
        test_clinic.id,
        order.id,
        PurchaseReceiptCreate(
            lines=[
                ReceiptLineCreate(
                    purchase_order_line_id=line.id,
                    quantity_received=Decimal("7"),
                    quality="good",
                ),
                ReceiptLineCreate(
                    purchase_order_line_id=line.id,
                    quantity_received=Decimal("3"),
                    quality="rejected",
                ),
            ]
        ),
        received_by=None,
    )
    assert order.status == "confirmed"  # 3 rejected units still outstanding
    assert order.received_at is None

    item_after = await InventoryService.get_item(db_session, test_clinic.id, item.id)
    assert item_after.stock_quantity == 7  # only the good 7 hit stock

    line = await _line_of(db_session, test_clinic.id, order.id)
    assert line.quantity_received == 7  # accepted units only

    receipts = await PurchaseOrderService.list_receipts(db_session, test_clinic.id, order.id)
    assert len(receipts) == 1
    receipt_response = await PurchaseOrderService.get_receipt_response(
        db_session, test_clinic.id, receipts[0].id
    )
    assert len(receipt_response["lines"]) == 2
    assert {ln["quality"] for ln in receipt_response["lines"]} == {"good", "rejected"}

    # Replacement for the rejected units completes the order.
    order = await PurchaseOrderService.receive_order(
        db_session,
        test_clinic.id,
        order.id,
        PurchaseReceiptCreate(
            lines=[
                ReceiptLineCreate(
                    purchase_order_line_id=line.id,
                    quantity_received=Decimal("3"),
                    quality="good",
                )
            ]
        ),
        received_by=None,
    )
    assert order.status == "received"
    assert order.received_at is not None
    assert order.received_at.tzinfo is not None
    item_final = await InventoryService.get_item(db_session, test_clinic.id, item.id)
    assert item_final.stock_quantity == 10


@pytest.mark.asyncio
async def test_receive_guards(db_session: AsyncSession, test_clinic: Clinic):
    supplier = await _make_supplier(db_session, test_clinic.id)
    item_a = await _make_item(db_session, test_clinic.id, name="Gloves")
    item_b = await _make_item(db_session, test_clinic.id, name="Masks")
    order = await _make_order(db_session, test_clinic.id, supplier.id, item_a.id, qty=10)
    line = await _line_of(db_session, test_clinic.id, order.id)

    # Cannot receive a draft.
    with pytest.raises(HTTPException) as exc:
        await PurchaseOrderService.receive_order(
            db_session,
            test_clinic.id,
            order.id,
            PurchaseReceiptCreate(
                lines=[
                    ReceiptLineCreate(
                        purchase_order_line_id=line.id,
                        quantity_received=Decimal("1"),
                        quality="good",
                    )
                ]
            ),
            received_by=None,
        )
    assert exc.value.status_code == 409

    # Invalid transition: draft -> received is not allowed.
    with pytest.raises(HTTPException) as exc:
        await PurchaseOrderService.transition_order(
            db_session, test_clinic.id, order.id, StatusTransition(status="received")
        )
    assert exc.value.status_code == 409

    await PurchaseOrderService.transition_order(
        db_session, test_clinic.id, order.id, StatusTransition(status="sent")
    )

    # Over-receipt is rejected.
    with pytest.raises(HTTPException) as exc:
        await PurchaseOrderService.receive_order(
            db_session,
            test_clinic.id,
            order.id,
            PurchaseReceiptCreate(
                lines=[
                    ReceiptLineCreate(
                        purchase_order_line_id=line.id,
                        quantity_received=Decimal("11"),
                        quality="good",
                    )
                ]
            ),
            received_by=None,
        )
    assert exc.value.status_code == 409

    # Foreign line id is rejected.
    foreign = uuid4()
    with pytest.raises(HTTPException) as exc:
        await PurchaseOrderService.receive_order(
            db_session,
            test_clinic.id,
            order.id,
            PurchaseReceiptCreate(
                lines=[
                    ReceiptLineCreate(
                        purchase_order_line_id=foreign,
                        quantity_received=Decimal("1"),
                        quality="good",
                    )
                ]
            ),
            received_by=None,
        )
    assert exc.value.status_code == 400

    # Duplicate items in a PO are rejected at creation.
    with pytest.raises(HTTPException) as exc:
        await PurchaseOrderService.create_order(
            db_session,
            test_clinic.id,
            PurchaseOrderCreate(
                supplier_id=supplier.id,
                lines=[
                    PurchaseOrderLineCreate(
                        inventory_item_id=item_b.id, quantity_ordered=Decimal("2")
                    ),
                    PurchaseOrderLineCreate(
                        inventory_item_id=item_b.id, quantity_ordered=Decimal("3")
                    ),
                ],
            ),
            created_by=None,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_partial_receipt_keeps_order_open(db_session: AsyncSession, test_clinic: Clinic):
    supplier = await _make_supplier(db_session, test_clinic.id)
    item = await _make_item(db_session, test_clinic.id)
    order = await _make_order(db_session, test_clinic.id, supplier.id, item.id, qty=10)

    await PurchaseOrderService.transition_order(
        db_session, test_clinic.id, order.id, StatusTransition(status="sent")
    )
    await PurchaseOrderService.transition_order(
        db_session, test_clinic.id, order.id, StatusTransition(status="confirmed")
    )

    line = await _line_of(db_session, test_clinic.id, order.id)
    order = await PurchaseOrderService.receive_order(
        db_session,
        test_clinic.id,
        order.id,
        PurchaseReceiptCreate(
            lines=[
                ReceiptLineCreate(
                    purchase_order_line_id=line.id,
                    quantity_received=Decimal("4"),
                    quality="good",
                )
            ]
        ),
        received_by=None,
    )
    assert order.status == "confirmed"  # still 6 outstanding

    item_after = await InventoryService.get_item(db_session, test_clinic.id, item.id)
    assert item_after.stock_quantity == 4


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

    foreign_supplier = await _make_supplier(db_session, other_clinic.id, name="Other Supplier")
    foreign_item = await _make_item(db_session, other_clinic.id, name="Other Item")

    # Foreign supplier is not visible in test_clinic -> 400.
    with pytest.raises(HTTPException) as exc:
        await PurchaseOrderService.create_order(
            db_session,
            test_clinic.id,
            PurchaseOrderCreate(
                supplier_id=foreign_supplier.id,
                lines=[
                    PurchaseOrderLineCreate(
                        inventory_item_id=foreign_item.id, quantity_ordered=Decimal("5")
                    )
                ],
            ),
            created_by=None,
        )
    assert exc.value.status_code == 400

    # In-clinic supplier, foreign item -> 404.
    my_supplier = await _make_supplier(db_session, test_clinic.id)
    with pytest.raises(HTTPException) as exc:
        await PurchaseOrderService.create_order(
            db_session,
            test_clinic.id,
            PurchaseOrderCreate(
                supplier_id=my_supplier.id,
                lines=[
                    PurchaseOrderLineCreate(
                        inventory_item_id=foreign_item.id, quantity_ordered=Decimal("5")
                    )
                ],
            ),
            created_by=None,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_metadata_and_lock_after_received(
    db_session: AsyncSession, test_clinic: Clinic
):
    supplier = await _make_supplier(db_session, test_clinic.id)
    item = await _make_item(db_session, test_clinic.id)
    order = await _make_order(db_session, test_clinic.id, supplier.id, item.id, qty=5)

    order = await PurchaseOrderService.update_order(
        db_session,
        test_clinic.id,
        order.id,
        PurchaseOrderUpdate(notes="Urgent delivery"),
    )
    assert order.notes == "Urgent delivery"

    await PurchaseOrderService.transition_order(
        db_session, test_clinic.id, order.id, StatusTransition(status="sent")
    )
    line = await _line_of(db_session, test_clinic.id, order.id)
    order = await PurchaseOrderService.receive_order(
        db_session,
        test_clinic.id,
        order.id,
        PurchaseReceiptCreate(
            lines=[
                ReceiptLineCreate(
                    purchase_order_line_id=line.id,
                    quantity_received=Decimal("5"),
                    quality="good",
                )
            ]
        ),
        received_by=None,
    )
    assert order.status == "received"

    with pytest.raises(HTTPException) as exc:
        await PurchaseOrderService.update_order(
            db_session,
            test_clinic.id,
            order.id,
            PurchaseOrderUpdate(notes="Too late"),
        )
    assert exc.value.status_code == 409
