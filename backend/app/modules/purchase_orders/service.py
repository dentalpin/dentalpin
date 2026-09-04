"""Business logic for purchase orders."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.core.events.types import EventType
from app.modules.contacts.models import Contact
from app.modules.inventory.models import InventoryItem
from app.modules.inventory.service import InventoryService

from .models import PurchaseOrder, PurchaseOrderLine, PurchaseReceipt, PurchaseReceiptLine
from .schemas import PurchaseOrderCreate, PurchaseOrderUpdate

if TYPE_CHECKING:
    from .schemas import PurchaseReceiptCreate

# Allowed explicit transitions. ``received`` is stamped only implicitly
# when every line fulfils (receive batch), never via this map.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"sent", "cancelled"}),
    "sent": frozenset({"draft", "confirmed", "cancelled"}),
    "confirmed": frozenset({"cancelled"}),
    "cancelled": frozenset(),
    "received": frozenset(),
}

RECEIVABLE_STATUSES = frozenset({"sent", "confirmed"})
STOCK_REASON = "purchase_receipt"


class PurchaseOrderService:
    @staticmethod
    async def _assert_supplier(db: AsyncSession, clinic_id: UUID, supplier_id: UUID) -> Contact:
        contact = (
            await db.execute(
                select(Contact).where(
                    Contact.id == supplier_id,
                    Contact.clinic_id == clinic_id,
                    Contact.contact_type == "supplier",
                )
            )
        ).scalar_one_or_none()
        if contact is None:
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                "supplier_id does not match a supplier contact in this clinic",
            )
        return contact

    @staticmethod
    async def _assert_item(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> InventoryItem:
        return await InventoryService.get_item(db, clinic_id, item_id)

    @staticmethod
    async def get_order(db: AsyncSession, clinic_id: UUID, order_id: UUID) -> PurchaseOrder:
        stmt = select(PurchaseOrder).where(
            PurchaseOrder.id == order_id, PurchaseOrder.clinic_id == clinic_id
        )
        order = (await db.execute(stmt)).scalar_one_or_none()
        if order is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Purchase order not found")
        return order

    @staticmethod
    async def get_line(
        db: AsyncSession, clinic_id: UUID, order_id: UUID, line_id: UUID
    ) -> PurchaseOrderLine:
        stmt = select(PurchaseOrderLine).where(
            PurchaseOrderLine.id == line_id,
            PurchaseOrderLine.purchase_order_id == order_id,
            PurchaseOrderLine.clinic_id == clinic_id,
        )
        line = (await db.execute(stmt)).scalar_one_or_none()
        if line is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Purchase order line not found")
        return line

    @staticmethod
    async def list_lines(
        db: AsyncSession, clinic_id: UUID, order_id: UUID
    ) -> list[PurchaseOrderLine]:
        stmt = select(PurchaseOrderLine).where(
            PurchaseOrderLine.purchase_order_id == order_id,
            PurchaseOrderLine.clinic_id == clinic_id,
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def _item_names(
        db: AsyncSession, clinic_id: UUID, item_ids: set[UUID]
    ) -> dict[UUID, str]:
        if not item_ids:
            return {}
        rows = (
            (
                await db.execute(
                    select(InventoryItem).where(
                        InventoryItem.id.in_(item_ids), InventoryItem.clinic_id == clinic_id
                    )
                )
            )
            .scalars()
            .all()
        )
        return {item.id: item.name for item in rows}

    @staticmethod
    async def list_orders(
        db: AsyncSession,
        clinic_id: UUID,
        order_status: str | None = None,
        supplier_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PurchaseOrder], int]:
        stmt = select(PurchaseOrder).where(PurchaseOrder.clinic_id == clinic_id)
        if order_status:
            stmt = stmt.where(PurchaseOrder.status == order_status)
        if supplier_id:
            stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (
            (
                await db.execute(
                    stmt.order_by(PurchaseOrder.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    @staticmethod
    async def list_order_responses(
        db: AsyncSession,
        clinic_id: UUID,
        order_status: str | None = None,
        supplier_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        orders, total = await PurchaseOrderService.list_orders(
            db, clinic_id, order_status, supplier_id, page, page_size
        )
        return [
            await PurchaseOrderService.get_order_response(db, clinic_id, o.id) for o in orders
        ], total

    @staticmethod
    async def get_order_response(db: AsyncSession, clinic_id: UUID, order_id: UUID) -> dict:
        order = await PurchaseOrderService.get_order(db, clinic_id, order_id)
        supplier = (
            await db.execute(
                select(Contact).where(
                    Contact.id == order.supplier_id, Contact.clinic_id == clinic_id
                )
            )
        ).scalar_one_or_none()
        lines = await PurchaseOrderService.list_lines(db, clinic_id, order_id)
        item_names = await PurchaseOrderService._item_names(
            db, clinic_id, {line.inventory_item_id for line in lines}
        )
        return {
            "id": order.id,
            "clinic_id": order.clinic_id,
            "supplier_id": order.supplier_id,
            "supplier_name": supplier.name if supplier else "",
            "status": order.status,
            "expected_date": order.expected_date,
            "notes": order.notes,
            "created_by": order.created_by,
            "received_at": order.received_at,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "lines": [
                {
                    "id": line.id,
                    "inventory_item_id": line.inventory_item_id,
                    "item_name": item_names.get(line.inventory_item_id, ""),
                    "quantity_ordered": line.quantity_ordered,
                    "quantity_received": line.quantity_received,
                    "unit_price": line.unit_price,
                }
                for line in lines
            ],
        }

    @staticmethod
    async def create_order(
        db: AsyncSession, clinic_id: UUID, payload: PurchaseOrderCreate, created_by: UUID | None
    ) -> PurchaseOrder:
        await PurchaseOrderService._assert_supplier(db, clinic_id, payload.supplier_id)
        item_ids = {line.inventory_item_id for line in payload.lines}
        if len(item_ids) != len(payload.lines):
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST, "duplicate inventory_item_id in lines"
            )
        for item_id in item_ids:
            await PurchaseOrderService._assert_item(db, clinic_id, item_id)

        order = PurchaseOrder(
            clinic_id=clinic_id,
            supplier_id=payload.supplier_id,
            status="draft",
            expected_date=payload.expected_date,
            notes=payload.notes,
            created_by=created_by,
        )
        db.add(order)
        await db.flush()
        for payload_line in payload.lines:
            db.add(
                PurchaseOrderLine(
                    clinic_id=clinic_id,
                    purchase_order_id=order.id,
                    inventory_item_id=payload_line.inventory_item_id,
                    quantity_ordered=payload_line.quantity_ordered,
                    quantity_received=Decimal("0"),
                    unit_price=payload_line.unit_price,
                )
            )
        # ADR 0019 — publish *inside* the transaction with the publisher's
        # session so transactional subscribers see the row and roll back
        # with it; the router owns the commit.
        await event_bus.publish(
            EventType.PURCHASE_ORDER_CREATED,
            {
                "clinic_id": str(clinic_id),
                "order_id": str(order.id),
                "supplier_id": str(order.supplier_id),
                "status": order.status,
            },
            db=db,
        )
        await db.commit()
        await db.refresh(order)
        return order

    @staticmethod
    async def update_order(
        db: AsyncSession, clinic_id: UUID, order_id: UUID, payload: PurchaseOrderUpdate
    ) -> PurchaseOrder:
        order = await PurchaseOrderService.get_order(db, clinic_id, order_id)
        if order.status == "received":
            raise HTTPException(
                http_status.HTTP_409_CONFLICT, "received purchase orders cannot be edited"
            )
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(order, field, value)
        await db.commit()
        await db.refresh(order)
        return order

    @staticmethod
    async def transition_order(
        db: AsyncSession,
        clinic_id: UUID,
        order_id: UUID,
        payload,
    ) -> PurchaseOrder:
        """Apply an explicit status change (draft -> sent -> confirmed -> cancelled)."""
        order = await PurchaseOrderService.get_order(db, clinic_id, order_id)
        to_status = payload.status
        if to_status not in ALLOWED_TRANSITIONS.get(order.status, frozenset()):
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                f"status transition {order.status} -> {to_status} not allowed",
            )
        old_status = order.status
        order.status = to_status
        await db.flush()
        await event_bus.publish(
            EventType.PURCHASE_ORDER_STATUS_CHANGED,
            {
                "clinic_id": str(clinic_id),
                "order_id": str(order.id),
                "supplier_id": str(order.supplier_id),
                "from_status": old_status,
                "status": to_status,
            },
            db=db,
        )
        await db.commit()
        await db.refresh(order)
        return order

    @staticmethod
    async def receive_order(
        db: AsyncSession,
        clinic_id: UUID,
        order_id: UUID,
        payload: PurchaseReceiptCreate,
        received_by: UUID | None,
    ) -> PurchaseOrder:
        """Batch-receive a delivery; only ``good`` units move stock and fulfil.

        ``rejected`` units are recorded on the receipt (audit trail) but do
        not count towards ``quantity_received``: the line stays open so the
        replacement can be received later.

        The whole batch is one transaction: the receipt rows, the per-line
        good stock movements (``reason='purchase_receipt'`` through
        ``InventoryService.apply_movement``) and the auto-transition to
        ``received`` when every line fulfils all commit or roll back
        together.
        """
        order = await PurchaseOrderService.get_order(db, clinic_id, order_id)
        if order.status not in RECEIVABLE_STATUSES:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                f"purchase order in status {order.status} cannot be received",
            )

        lines_by_id: dict[UUID, PurchaseOrderLine] = {
            line.id: line for line in await PurchaseOrderService.list_lines(db, clinic_id, order_id)
        }
        if not lines_by_id:
            raise HTTPException(http_status.HTTP_409_CONFLICT, "purchase order has no lines")

        receipt = PurchaseReceipt(
            clinic_id=clinic_id, purchase_order_id=order.id, received_by=received_by
        )
        db.add(receipt)
        await db.flush()

        applied: list[dict] = []
        for entry in payload.lines:
            line = lines_by_id.get(entry.purchase_order_line_id)
            if line is None:
                raise HTTPException(
                    http_status.HTTP_400_BAD_REQUEST,
                    "receipt line does not belong to this purchase order",
                )
            if entry.quantity_received <= 0:
                raise HTTPException(
                    http_status.HTTP_400_BAD_REQUEST, "quantity_received must be positive"
                )
            if line.quantity_received + entry.quantity_received > line.quantity_ordered:
                raise HTTPException(
                    http_status.HTTP_409_CONFLICT,
                    "received quantity would exceed ordered quantity for a line",
                )
            db.add(
                PurchaseReceiptLine(
                    clinic_id=clinic_id,
                    receipt_id=receipt.id,
                    purchase_order_line_id=line.id,
                    quantity_received=entry.quantity_received,
                    quality=entry.quality,
                )
            )
            if entry.quality == "good":
                line.quantity_received += entry.quantity_received
                updated, _applied = await InventoryService.apply_movement(
                    db,
                    clinic_id=clinic_id,
                    item_id=line.inventory_item_id,
                    delta=entry.quantity_received,
                    reason=STOCK_REASON,
                    note=f"PO {str(order.id)} receipt {str(receipt.id)}",
                    created_by=received_by,
                    reference_type="purchase_receipt",
                    reference_id=receipt.id,
                    clamp_at_zero=False,
                )
                if updated is None:
                    raise HTTPException(
                        http_status.HTTP_409_CONFLICT,
                        "inventory item for a receipt line could not be updated",
                    )
                applied.append(
                    {
                        "inventory_item_id": line.inventory_item_id,
                        "quantity": entry.quantity_received,
                    }
                )

        fully_received = all(
            line.quantity_received >= line.quantity_ordered for line in lines_by_id.values()
        )
        old_status = order.status
        if fully_received:
            order.status = "received"
            order.received_at = datetime.now(UTC)

        await db.flush()
        await event_bus.publish(
            EventType.PURCHASE_ORDER_RECEIVED,
            {
                "clinic_id": str(clinic_id),
                "order_id": str(order.id),
                "supplier_id": str(order.supplier_id),
                "receipt_id": str(receipt.id),
                "applied": applied,
                "fully_received": fully_received,
            },
            db=db,
        )
        if old_status != order.status:
            await event_bus.publish(
                EventType.PURCHASE_ORDER_STATUS_CHANGED,
                {
                    "clinic_id": str(clinic_id),
                    "order_id": str(order.id),
                    "supplier_id": str(order.supplier_id),
                    "from_status": old_status,
                    "status": order.status,
                },
                db=db,
            )
        await db.commit()
        await db.refresh(order)
        return order

    @staticmethod
    async def list_receipts(
        db: AsyncSession, clinic_id: UUID, order_id: UUID
    ) -> list[PurchaseReceipt]:
        stmt = (
            select(PurchaseReceipt)
            .where(
                PurchaseReceipt.purchase_order_id == order_id,
                PurchaseReceipt.clinic_id == clinic_id,
            )
            .order_by(PurchaseReceipt.received_at.desc())
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_receipt_response(db: AsyncSession, clinic_id: UUID, receipt_id: UUID) -> dict:
        receipt = (
            await db.execute(
                select(PurchaseReceipt).where(
                    PurchaseReceipt.id == receipt_id, PurchaseReceipt.clinic_id == clinic_id
                )
            )
        ).scalar_one_or_none()
        if receipt is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Receipt not found")

        lines = (
            (
                await db.execute(
                    select(PurchaseReceiptLine).where(PurchaseReceiptLine.receipt_id == receipt.id)
                )
            )
            .scalars()
            .all()
        )
        line_ids = {line.purchase_order_line_id for line in lines}
        item_ids: set[UUID] = set()
        item_by_line: dict[UUID, UUID] = {}
        if line_ids:
            po_lines = (
                (
                    await db.execute(
                        select(PurchaseOrderLine).where(
                            PurchaseOrderLine.id.in_(line_ids),
                            PurchaseOrderLine.clinic_id == clinic_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for po_line in po_lines:
                item_ids.add(po_line.inventory_item_id)
                item_by_line[po_line.id] = po_line.inventory_item_id
        item_names = await PurchaseOrderService._item_names(db, clinic_id, item_ids)

        return {
            "id": receipt.id,
            "purchase_order_id": receipt.purchase_order_id,
            "received_at": receipt.received_at,
            "received_by": receipt.received_by,
            "lines": [
                {
                    "id": line.id,
                    "purchase_order_line_id": line.purchase_order_line_id,
                    "inventory_item_id": item_by_line.get(line.purchase_order_line_id),
                    "item_name": item_names.get(item_by_line.get(line.purchase_order_line_id), ""),
                    "quantity_received": line.quantity_received,
                    "quality": line.quality,
                }
                for line in lines
            ],
        }
