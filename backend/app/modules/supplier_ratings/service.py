"""SupplierRatingService — computed delivery/quality/price metrics
(derived from purchase_orders + receiving data, Phase 13c/13d) plus
manual communication ratings.

Depends on `contacts` (validate supplier) and `purchase_orders` (the
actual metrics source) — reads both, writes only to this module's own
`supplier_ratings` table.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contacts.models import Contact
from app.modules.purchase_orders.models import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderReceipt,
    PurchaseOrderReceiptLine,
)

from .models import SupplierRating
from .schemas import SupplierRatingCreate

# Only these statuses represent a real transaction — draft/cancelled
# never actually happened, so they're excluded from price/quality
# aggregates.
_COMPLETED_STATUSES = ("confirmed", "partially_received", "fully_received")


class SupplierRatingService:
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
    async def add_rating(
        db: AsyncSession, clinic_id: UUID, supplier_contact_id: UUID,
        payload: SupplierRatingCreate, rated_by: UUID | None,
    ) -> SupplierRating:
        await SupplierRatingService._validate_supplier(db, clinic_id, supplier_contact_id)
        rating = SupplierRating(
            clinic_id=clinic_id,
            supplier_contact_id=supplier_contact_id,
            communication_score=payload.communication_score,
            notes=payload.notes,
            rated_by=rated_by,
        )
        db.add(rating)
        await db.commit()
        await db.refresh(rating)
        return rating

    @staticmethod
    async def get_dashboard(db: AsyncSession, clinic_id: UUID, supplier_contact_id: UUID) -> dict:
        supplier = await SupplierRatingService._validate_supplier(db, clinic_id, supplier_contact_id)

        # On-time delivery: among fully_received POs with an expected
        # delivery date set, what fraction had their latest receipt on
        # or before that date.
        fully_received_stmt = select(PurchaseOrder).where(
            PurchaseOrder.clinic_id == clinic_id,
            PurchaseOrder.supplier_contact_id == supplier_contact_id,
            PurchaseOrder.status == "fully_received",
            PurchaseOrder.expected_delivery_date.isnot(None),
        )
        fully_received = (await db.execute(fully_received_stmt)).scalars().all()

        on_time_count = 0
        dated_count = 0
        for po in fully_received:
            latest_receipt_stmt = select(func.max(PurchaseOrderReceipt.received_date)).where(
                PurchaseOrderReceipt.purchase_order_id == po.id
            )
            latest_date = (await db.execute(latest_receipt_stmt)).scalar_one_or_none()
            if latest_date is None:
                continue
            dated_count += 1
            if latest_date <= po.expected_delivery_date:
                on_time_count += 1

        on_time_pct = (on_time_count / dated_count * 100) if dated_count > 0 else None

        completed_count_stmt = select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.clinic_id == clinic_id,
            PurchaseOrder.supplier_contact_id == supplier_contact_id,
            PurchaseOrder.status.in_(_COMPLETED_STATUSES),
        )
        completed_order_count = (await db.execute(completed_count_stmt)).scalar_one()

        avg_price_stmt = (
            select(func.avg(PurchaseOrderItem.unit_price))
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
            .where(
                PurchaseOrder.clinic_id == clinic_id,
                PurchaseOrder.supplier_contact_id == supplier_contact_id,
                PurchaseOrder.status.in_(_COMPLETED_STATUSES),
            )
        )
        avg_price = (await db.execute(avg_price_stmt)).scalar_one_or_none()

        quality_stmt = (
            select(
                func.count(PurchaseOrderReceiptLine.id),
                func.count(PurchaseOrderReceiptLine.id).filter(
                    PurchaseOrderReceiptLine.quality_status == "good"
                ),
            )
            .join(
                PurchaseOrderItem,
                PurchaseOrderItem.id == PurchaseOrderReceiptLine.purchase_order_item_id,
            )
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
            .where(
                PurchaseOrder.clinic_id == clinic_id,
                PurchaseOrder.supplier_contact_id == supplier_contact_id,
            )
        )
        total_lines, good_lines = (await db.execute(quality_stmt)).one()
        quality_pct = (good_lines / total_lines * 100) if total_lines > 0 else None

        ratings_stmt = (
            select(SupplierRating)
            .where(
                SupplierRating.clinic_id == clinic_id,
                SupplierRating.supplier_contact_id == supplier_contact_id,
            )
            .order_by(SupplierRating.rated_at.desc())
        )
        ratings = (await db.execute(ratings_stmt)).scalars().all()
        avg_communication = (
            sum(r.communication_score for r in ratings) / len(ratings) if ratings else None
        )

        return {
            "supplier_contact_id": supplier_contact_id,
            "supplier_name": supplier.name,
            "on_time_delivery_pct": on_time_pct,
            "completed_order_count": completed_order_count,
            "avg_unit_price": Decimal(str(avg_price)) if avg_price is not None else None,
            "quality_good_pct": quality_pct,
            "total_receipt_lines": total_lines,
            "avg_communication_score": avg_communication,
            "ratings": ratings,
        }
