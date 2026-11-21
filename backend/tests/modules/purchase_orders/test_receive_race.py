"""Concurrent writes to one purchase order are serialized.

``receive_order`` and ``transition_order`` read the order and its lines
without a lock, check them, then write. Two deliveries of the full quantity
recorded at the same moment both passed the "would exceed ordered quantity"
check: stock went up twice, two receipts were stored and the order was
stamped ``received`` twice. A cancel racing a receive left a cancelled order
whose goods had been booked into stock. Production hands each request its own
session, so these tests do too.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.database import async_session_maker
from app.modules.inventory.models import InventoryItem
from app.modules.inventory.schemas import InventoryItemCreate
from app.modules.inventory.service import InventoryService
from app.modules.purchase_orders.models import PurchaseOrder, PurchaseReceipt
from app.modules.purchase_orders.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseReceiptCreate,
    ReceiptLineCreate,
    StatusTransition,
)
from app.modules.purchase_orders.service import PurchaseOrderService
from app.modules.suppliers.schemas import SupplierCreate
from app.modules.suppliers.service import SupplierService


async def _sent_order(db: AsyncSession, clinic_id) -> tuple:
    supplier, _ = await SupplierService.create_supplier(
        db, clinic_id, SupplierCreate(name="Acme", payment_terms="NET30", lead_time_days=5)
    )
    item = await InventoryService.create_item(
        db,
        clinic_id,
        InventoryItemCreate(name="Gloves", category="consumables", unit_cost=Decimal("1")),
        created_by=None,
    )
    order = await PurchaseOrderService.create_order(
        db,
        clinic_id,
        PurchaseOrderCreate(
            supplier_id=supplier.id,
            lines=[
                PurchaseOrderLineCreate(inventory_item_id=item.id, quantity_ordered=Decimal(10))
            ],
        ),
        created_by=None,
    )
    await PurchaseOrderService.transition_order(
        db, clinic_id, order.id, StatusTransition(status="sent")
    )
    line = (await PurchaseOrderService.list_lines(db, clinic_id, order.id))[0]
    return order.id, line.id, item.id


async def _receive_all(clinic_id, order_id, line_id) -> int:
    async with async_session_maker() as session:
        try:
            await PurchaseOrderService.receive_order(
                session,
                clinic_id,
                order_id,
                PurchaseReceiptCreate(
                    lines=[
                        ReceiptLineCreate(
                            purchase_order_line_id=line_id, quantity_received=Decimal(10)
                        )
                    ]
                ),
                received_by=None,
            )
        except HTTPException as exc:
            await session.rollback()
            return exc.status_code
        return 200


async def _cancel(clinic_id, order_id) -> int:
    async with async_session_maker() as session:
        try:
            await PurchaseOrderService.transition_order(
                session, clinic_id, order_id, StatusTransition(status="cancelled")
            )
        except HTTPException as exc:
            await session.rollback()
            return exc.status_code
        return 200


async def _state(clinic_id, order_id, item_id) -> tuple:
    async with async_session_maker() as fresh:
        stock = await fresh.scalar(
            select(InventoryItem.stock_quantity).where(InventoryItem.id == item_id)
        )
        receipts = await fresh.scalar(
            select(func.count())
            .select_from(PurchaseReceipt)
            .where(PurchaseReceipt.purchase_order_id == order_id)
        )
        status = await fresh.scalar(
            select(PurchaseOrder.status).where(PurchaseOrder.id == order_id)
        )
    return stock, receipts, status


@pytest.mark.asyncio
async def test_two_full_deliveries_at_once_book_stock_once(
    db_session: AsyncSession, test_clinic: Clinic
):
    order_id, line_id, item_id = await _sent_order(db_session, test_clinic.id)

    outcomes = await asyncio.gather(
        _receive_all(test_clinic.id, order_id, line_id),
        _receive_all(test_clinic.id, order_id, line_id),
    )

    assert sorted(outcomes) == [200, 409]
    assert await _state(test_clinic.id, order_id, item_id) == (Decimal(10), 1, "received")


@pytest.mark.asyncio
async def test_a_cancel_racing_a_receive_does_not_cancel_received_goods(
    db_session: AsyncSession, test_clinic: Clinic
):
    order_id, line_id, item_id = await _sent_order(db_session, test_clinic.id)

    outcomes = await asyncio.gather(
        _receive_all(test_clinic.id, order_id, line_id),
        _cancel(test_clinic.id, order_id),
    )

    stock, receipts, status = await _state(test_clinic.id, order_id, item_id)
    # Exactly one wins, and the order's status agrees with the stock.
    assert sorted(outcomes) == [200, 409]
    assert (stock, receipts, status) in {
        (Decimal(10), 1, "received"),
        (Decimal(0), 0, "cancelled"),
    }
