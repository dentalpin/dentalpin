"""PurchaseOrderService — header/line-item CRUD, lifecycle transitions,
send-to-supplier (PDF generation is in pdf.py, not here).

Status lifecycle this service drives: draft → sent → confirmed, with
cancelled reachable from draft/sent/confirmed. ``partially_received``
and ``fully_received`` are NOT settable through anything here — those
belong exclusively to the Phase 13d receiving flow, which will update
``PurchaseOrderItem.quantity_received`` and derive the header status
from it. Attempting to reach them via this service is a bug, not a
missing feature — enforced by ``_ALLOWED_TRANSITIONS`` below.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.events import EventType, event_bus
from app.modules.contacts.models import Contact
from app.modules.inventory.models import InventoryItem
from app.modules.notifications.gateway import NotificationGateway

from .models import PurchaseOrder, PurchaseOrderItem
from .schemas import (
    PurchaseOrderCreate,
    PurchaseOrderItemCreate,
    PurchaseOrderItemUpdate,
    PurchaseOrderUpdate,
)

# Only the transitions this service is allowed to perform. Receiving
# (13d) drives sent/confirmed -> partially_received/fully_received
# directly against the model, bypassing this table entirely.
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"sent", "cancelled"},
    "sent": {"confirmed", "cancelled"},
    "confirmed": {"cancelled"},
    "partially_received": set(),
    "fully_received": set(),
    "cancelled": set(),
}


class PurchaseOrderService:
    # ------------------------------------------------------------ numbering
    @staticmethod
    async def _generate_po_number(db: AsyncSession, clinic_id: UUID) -> str:
        year = datetime.now(UTC).year
        result = await db.execute(
            select(func.count(PurchaseOrder.id)).where(
                PurchaseOrder.clinic_id == clinic_id,
                PurchaseOrder.po_number.like(f"PO-{year}-%"),
            )
        )
        count = result.scalar_one()
        return f"PO-{year}-{count + 1:04d}"

    # ------------------------------------------------------------ totals
    @staticmethod
    def _recompute_totals(po: PurchaseOrder) -> None:
        subtotal = sum((Decimal(str(i.line_total)) for i in po.items), Decimal("0"))
        po.subtotal = subtotal
        po.total = subtotal + Decimal(str(po.shipping_cost)) + Decimal(str(po.tax_amount))

    # ------------------------------------------------------------ validation
    @staticmethod
    async def _validate_supplier(db: AsyncSession, clinic_id: UUID, contact_id: UUID) -> Contact:
        contact = await db.get(Contact, contact_id)
        if contact is None or contact.clinic_id != clinic_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
        if contact.contact_type != "supplier":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Contact is not a supplier"
            )
        return contact

    @staticmethod
    async def _validate_inventory_item(
        db: AsyncSession, clinic_id: UUID, item_id: UUID
    ) -> InventoryItem:
        item = await db.get(InventoryItem, item_id)
        if item is None or item.clinic_id != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )
        return item

    @staticmethod
    def _require_draft(po: PurchaseOrder) -> None:
        if po.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Purchase order is '{po.status}' — only draft orders can be edited",
            )

    # ------------------------------------------------------------ CRUD
    @staticmethod
    async def create(
        db: AsyncSession, clinic_id: UUID, payload: PurchaseOrderCreate, created_by: UUID | None
    ) -> PurchaseOrder:
        await PurchaseOrderService._validate_supplier(db, clinic_id, payload.supplier_contact_id)

        po = PurchaseOrder(
            clinic_id=clinic_id,
            po_number=await PurchaseOrderService._generate_po_number(db, clinic_id),
            supplier_contact_id=payload.supplier_contact_id,
            status="draft",
            expected_delivery_date=payload.expected_delivery_date,
            shipping_cost=payload.shipping_cost,
            tax_amount=payload.tax_amount,
            notes=payload.notes,
            created_by=created_by,
        )

        for idx, item_payload in enumerate(payload.items):
            inv_item = await PurchaseOrderService._validate_inventory_item(
                db, clinic_id, item_payload.inventory_item_id
            )
            po.items.append(
                PurchaseOrderItem(
                    clinic_id=clinic_id,
                    inventory_item_id=inv_item.id,
                    description=item_payload.description or inv_item.name,
                    unit_price=item_payload.unit_price,
                    quantity_ordered=item_payload.quantity_ordered,
                    line_total=item_payload.unit_price * item_payload.quantity_ordered,
                    display_order=idx,
                )
            )

        PurchaseOrderService._recompute_totals(po)
        db.add(po)
        await db.commit()
        await db.refresh(po, attribute_names=["items"])

        await event_bus.publish(
            EventType.PURCHASE_ORDER_CREATED,
            {
                "clinic_id": str(clinic_id),
                "purchase_order_id": str(po.id),
                "po_number": po.po_number,
                "supplier_contact_id": str(po.supplier_contact_id),
                "total": float(po.total),
                "created_by": str(created_by) if created_by else None,
            },
        )
        return po

    @staticmethod
    async def get(db: AsyncSession, clinic_id: UUID, po_id: UUID) -> PurchaseOrder:
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id, PurchaseOrder.clinic_id == clinic_id)
            .options(selectinload(PurchaseOrder.items))
        )
        po = (await db.execute(stmt)).scalar_one_or_none()
        if po is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found"
            )
        return po

    @staticmethod
    async def list_orders(
        db: AsyncSession,
        clinic_id: UUID,
        status_filter: str | None = None,
        supplier_contact_id: UUID | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[tuple[PurchaseOrder, str]], int]:
        stmt = (
            select(PurchaseOrder, Contact.name)
            .join(Contact, Contact.id == PurchaseOrder.supplier_contact_id)
            .where(PurchaseOrder.clinic_id == clinic_id)
        )
        if status_filter:
            stmt = stmt.where(PurchaseOrder.status == status_filter)
        if supplier_contact_id:
            stmt = stmt.where(PurchaseOrder.supplier_contact_id == supplier_contact_id)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(PurchaseOrder.po_number.ilike(like), Contact.name.ilike(like)))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(PurchaseOrder.order_date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows], total

    @staticmethod
    async def update(
        db: AsyncSession, clinic_id: UUID, po_id: UUID, payload: PurchaseOrderUpdate
    ) -> PurchaseOrder:
        po = await PurchaseOrderService.get(db, clinic_id, po_id)
        PurchaseOrderService._require_draft(po)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(po, field, value)
        PurchaseOrderService._recompute_totals(po)
        await db.commit()
        await db.refresh(po, attribute_names=["items"])
        return po

    @staticmethod
    async def delete(db: AsyncSession, clinic_id: UUID, po_id: UUID) -> None:
        po = await PurchaseOrderService.get(db, clinic_id, po_id)
        PurchaseOrderService._require_draft(po)
        await db.delete(po)
        await db.commit()

    # ------------------------------------------------------------ line items
    @staticmethod
    async def add_item(
        db: AsyncSession, clinic_id: UUID, po_id: UUID, payload: PurchaseOrderItemCreate
    ) -> PurchaseOrder:
        po = await PurchaseOrderService.get(db, clinic_id, po_id)
        PurchaseOrderService._require_draft(po)
        inv_item = await PurchaseOrderService._validate_inventory_item(
            db, clinic_id, payload.inventory_item_id
        )
        po.items.append(
            PurchaseOrderItem(
                clinic_id=clinic_id,
                inventory_item_id=inv_item.id,
                description=payload.description or inv_item.name,
                unit_price=payload.unit_price,
                quantity_ordered=payload.quantity_ordered,
                line_total=payload.unit_price * payload.quantity_ordered,
                display_order=len(po.items),
            )
        )
        PurchaseOrderService._recompute_totals(po)
        await db.commit()
        await db.refresh(po, attribute_names=["items"])
        return po

    @staticmethod
    async def update_item(
        db: AsyncSession,
        clinic_id: UUID,
        po_id: UUID,
        item_id: UUID,
        payload: PurchaseOrderItemUpdate,
    ) -> PurchaseOrder:
        po = await PurchaseOrderService.get(db, clinic_id, po_id)
        PurchaseOrderService._require_draft(po)
        item = next((i for i in po.items if i.id == item_id), None)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line item not found")

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        item.line_total = Decimal(str(item.unit_price)) * Decimal(str(item.quantity_ordered))

        PurchaseOrderService._recompute_totals(po)
        await db.commit()
        await db.refresh(po, attribute_names=["items"])
        return po

    @staticmethod
    async def remove_item(db: AsyncSession, clinic_id: UUID, po_id: UUID, item_id: UUID) -> PurchaseOrder:
        po = await PurchaseOrderService.get(db, clinic_id, po_id)
        PurchaseOrderService._require_draft(po)
        item = next((i for i in po.items if i.id == item_id), None)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line item not found")
        po.items.remove(item)
        await db.flush()
        PurchaseOrderService._recompute_totals(po)
        await db.commit()
        await db.refresh(po, attribute_names=["items"])
        return po

    # ------------------------------------------------------------ lifecycle
    @staticmethod
    def _transition(po: PurchaseOrder, new_status: str) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(po.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot move purchase order from '{po.status}' to '{new_status}'",
            )

    @staticmethod
    async def send(
        db: AsyncSession, clinic_id: UUID, po_id: UUID, user_id: UUID | None, send_email: bool = True
    ) -> PurchaseOrder:
        po = await PurchaseOrderService.get(db, clinic_id, po_id)
        PurchaseOrderService._transition(po, "sent")
        if not po.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot send a purchase order with no line items",
            )

        po.status = "sent"
        po.sent_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(po, attribute_names=["items"])

        await event_bus.publish(
            EventType.PURCHASE_ORDER_SENT,
            {
                "clinic_id": str(clinic_id),
                "purchase_order_id": str(po.id),
                "po_number": po.po_number,
                "supplier_contact_id": str(po.supplier_contact_id),
                "total": float(po.total),
                "sent_by": str(user_id) if user_id else None,
            },
        )

        if send_email:
            await PurchaseOrderService._send_email(db, clinic_id, po)

        return po

    @staticmethod
    async def _send_email(db: AsyncSession, clinic_id: UUID, po: PurchaseOrder) -> None:
        """Best-effort email to the supplier. NOT an attachment — the
        email carries the PO's data rendered via a "purchase_order_sent"
        template, same pattern as invoice_sent/budget_sent (neither of
        those attaches a PDF either; the PDF is an in-app
        preview/download only). If you want a real PDF attached, that
        needs new capability in the notification channel adapters —
        out of scope here, see the install guide.
        """
        supplier = await db.get(Contact, po.supplier_contact_id)
        if supplier is None or not supplier.email:
            return  # No address to send to — "sent" still stands (e.g. sent by phone).

        context = {
            "po_number": po.po_number,
            "supplier_name": supplier.name,
            "order_date": po.order_date.strftime("%d/%m/%Y") if po.order_date else None,
            "expected_delivery_date": (
                po.expected_delivery_date.strftime("%d/%m/%Y")
                if po.expected_delivery_date
                else None
            ),
            "items": [
                {
                    "description": i.description,
                    "quantity_ordered": float(i.quantity_ordered),
                    "unit_price": float(i.unit_price),
                    "line_total": float(i.line_total),
                }
                for i in po.items
            ],
            "subtotal": float(po.subtotal),
            "shipping_cost": float(po.shipping_cost),
            "tax_amount": float(po.tax_amount),
            "total": float(po.total),
            "notes": po.notes,
        }

        await NotificationGateway.enqueue(
            db=db,
            clinic_id=clinic_id,
            notification_type="purchase_order_sent",
            to_address=supplier.email,
            context=context,
            patient_id=None,  # suppliers are contacts, not patients — see gateway.py, this is a supported path
            triggered_by_event="purchase_order.sent",
        )

    @staticmethod
    async def confirm(db: AsyncSession, clinic_id: UUID, po_id: UUID, user_id: UUID | None) -> PurchaseOrder:
        po = await PurchaseOrderService.get(db, clinic_id, po_id)
        PurchaseOrderService._transition(po, "confirmed")
        po.status = "confirmed"
        po.confirmed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(po, attribute_names=["items"])

        await event_bus.publish(
            EventType.PURCHASE_ORDER_CONFIRMED,
            {
                "clinic_id": str(clinic_id),
                "purchase_order_id": str(po.id),
                "po_number": po.po_number,
                "confirmed_by": str(user_id) if user_id else None,
            },
        )
        return po

    @staticmethod
    async def cancel(
        db: AsyncSession, clinic_id: UUID, po_id: UUID, user_id: UUID | None, reason: str
    ) -> PurchaseOrder:
        po = await PurchaseOrderService.get(db, clinic_id, po_id)
        PurchaseOrderService._transition(po, "cancelled")
        po.status = "cancelled"
        po.cancelled_at = datetime.now(UTC)
        po.cancellation_reason = reason
        await db.commit()
        await db.refresh(po, attribute_names=["items"])

        await event_bus.publish(
            EventType.PURCHASE_ORDER_CANCELLED,
            {
                "clinic_id": str(clinic_id),
                "purchase_order_id": str(po.id),
                "po_number": po.po_number,
                "reason": reason,
                "cancelled_by": str(user_id) if user_id else None,
            },
        )
        return po
