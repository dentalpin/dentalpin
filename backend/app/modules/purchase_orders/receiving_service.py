"""ReceivingService — Phase 13d.

Records a delivery against a PO (possibly partial, possibly split
across several receipt events over time), applies quality-checked
quantities to inventory stock, and derives the PO header status.

This is the ONLY code path allowed to set
``PurchaseOrder.status`` to ``partially_received`` or
``fully_received`` — see purchase_orders' own service.py, whose
``_ALLOWED_TRANSITIONS`` deliberately has empty sets for both.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.events import EventType, event_bus
from app.modules.inventory.schemas import InventoryMovementCreate
from app.modules.inventory.service import InventoryService

from .models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt, PurchaseOrderReceiptLine
from .schemas import PurchaseOrderReceiptCreate

# Statuses a PO must be in for a receipt to be recordable against it.
_RECEIVABLE_STATUSES = {"sent", "confirmed", "partially_received"}


class ReceivingService:
    @staticmethod
    async def _get_po_with_items(db: AsyncSession, clinic_id: UUID, po_id: UUID) -> PurchaseOrder:
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
    async def record_receipt(
        db: AsyncSession,
        clinic_id: UUID,
        po_id: UUID,
        payload: PurchaseOrderReceiptCreate,
        received_by: UUID | None,
    ) -> tuple[PurchaseOrder, PurchaseOrderReceipt]:
        po = await ReceivingService._get_po_with_items(db, clinic_id, po_id)
        if po.status not in _RECEIVABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot record a receipt against a purchase order that is '{po.status}' — "
                    "it must be sent, confirmed, or already partially received"
                ),
            )

        items_by_id = {i.id: i for i in po.items}

        receipt = PurchaseOrderReceipt(
            clinic_id=clinic_id,
            purchase_order_id=po.id,
            received_date=payload.received_date or date.today(),
            received_by=received_by,
            notes=payload.notes,
        )

        for line_payload in payload.lines:
            po_item = items_by_id.get(line_payload.purchase_order_item_id)
            if po_item is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Line item {line_payload.purchase_order_item_id} does not belong to this purchase order",
                )

            receipt.lines.append(
                PurchaseOrderReceiptLine(
                    clinic_id=clinic_id,
                    purchase_order_item_id=po_item.id,
                    quantity_received=line_payload.quantity_received,
                    quality_status=line_payload.quality_status,
                    notes=line_payload.notes,
                )
            )

            # Every received unit counts toward "the supplier delivered
            # this" fulfillment tracking, regardless of quality outcome
            # — a damaged item was still shipped, it's just unusable.
            po_item.quantity_received = Decimal(str(po_item.quantity_received)) + line_payload.quantity_received

            # Only "good" units become usable stock. Damaged/expired/
            # wrong_item are logged above (receipt line) but never
            # touch inventory — they were never actually receivable
            # stock in the first place.
            if line_payload.quality_status == "good":
                await InventoryService.record_movement(
                    db,
                    clinic_id,
                    po_item.inventory_item_id,
                    InventoryMovementCreate(
                        reason="purchase",
                        quantity_delta=line_payload.quantity_received,
                        unit_cost=po_item.unit_price,
                        reference=f"PO:{po.po_number}",
                        notes=f"Received against {po.po_number}",
                    ),
                    received_by,
                )

        db.add(receipt)

        # Derive header status from total received vs. total ordered
        # across every line item on the PO (not just the ones in this
        # receipt — a prior partial receipt may have covered others).
        total_ordered = sum(Decimal(str(i.quantity_ordered)) for i in po.items)
        total_received = sum(Decimal(str(i.quantity_received)) for i in po.items)
        if total_received >= total_ordered and total_ordered > 0:
            po.status = "fully_received"
        elif total_received > 0:
            po.status = "partially_received"

        await db.commit()
        await db.refresh(po, attribute_names=["items"])
        await db.refresh(receipt, attribute_names=["lines"])

        await event_bus.publish(
            EventType.PURCHASE_ORDER_RECEIVED,
            {
                "clinic_id": str(clinic_id),
                "purchase_order_id": str(po.id),
                "po_number": po.po_number,
                "receipt_id": str(receipt.id),
                "new_status": po.status,
                "received_by": str(received_by) if received_by else None,
                "line_count": len(receipt.lines),
            },
        )

        return po, receipt

    @staticmethod
    async def list_receipts(
        db: AsyncSession, clinic_id: UUID, po_id: UUID
    ) -> list[PurchaseOrderReceipt]:
        await ReceivingService._get_po_with_items(db, clinic_id, po_id)  # 404s if wrong clinic
        stmt = (
            select(PurchaseOrderReceipt)
            .where(
                PurchaseOrderReceipt.purchase_order_id == po_id,
                PurchaseOrderReceipt.clinic_id == clinic_id,
            )
            .options(selectinload(PurchaseOrderReceipt.lines))
            .order_by(PurchaseOrderReceipt.received_date.desc())
        )
        return list((await db.execute(stmt)).scalars().all())
