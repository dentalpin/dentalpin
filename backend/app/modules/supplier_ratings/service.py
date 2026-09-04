"""Business logic for supplier_ratings.

Delivery/quality metrics are computed on demand from purchase order
history (never stored); the only persisted rows are manual reviews.
Every query is clinic-scoped.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import Date, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contacts.models import Contact
from app.modules.purchase_orders.models import PurchaseOrder, PurchaseReceipt, PurchaseReceiptLine

from .models import SupplierReview
from .schemas import SupplierRatingMetrics, SupplierReviewCreate, SupplierReviewUpdate

RECEIVED = "received"


class SupplierRatingsService:
    """Static methods; no state."""

    @staticmethod
    async def _assert_supplier(db: AsyncSession, clinic_id: UUID, supplier_id: UUID) -> Contact:
        """Suppliers are contacts of type 'supplier' in this clinic (404 otherwise)."""
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
                http_status.HTTP_404_NOT_FOUND,
                "supplier not found in this clinic",
            )
        return contact

    @staticmethod
    async def _metrics_for(
        db: AsyncSession, clinic_id: UUID, supplier_ids: list[UUID]
    ) -> dict[UUID, SupplierRatingMetrics]:
        """Aggregate delivery + quality metrics per supplier id."""
        if not supplier_ids:
            return {}
        ids = list(set(supplier_ids))
        metrics: dict[UUID, SupplierRatingMetrics] = {}

        # --- Delivery / on-time, straight off the PO header ---
        delivery_rows = (
            await db.execute(
                select(
                    PurchaseOrder.supplier_id,
                    func.count().label("po_count"),
                    func.count().filter(PurchaseOrder.status == RECEIVED).label("received_count"),
                    func.count()
                    .filter(
                        PurchaseOrder.status == RECEIVED,
                        PurchaseOrder.expected_date.is_not(None),
                    )
                    .label("received_with_due_date"),
                    func.count()
                    .filter(
                        PurchaseOrder.status == RECEIVED,
                        PurchaseOrder.expected_date.is_not(None),
                        cast(PurchaseOrder.received_at, Date) <= PurchaseOrder.expected_date,
                    )
                    .label("on_time_deliveries"),
                )
                .where(
                    PurchaseOrder.clinic_id == clinic_id,
                    PurchaseOrder.supplier_id.in_(ids),
                )
                .group_by(PurchaseOrder.supplier_id)
            )
        ).all()
        for supplier_id, po_count, received_count, with_due, on_time in delivery_rows:
            metrics[supplier_id] = SupplierRatingMetrics(
                po_count=po_count,
                received_count=received_count,
                received_with_due_date=with_due,
                on_time_deliveries=on_time,
                on_time_rate=(
                    (Decimal(on_time) / Decimal(with_due)).quantize(Decimal("0.01"))
                    if with_due
                    else None
                ),
            )

        # --- Quality, from the receipt-line ledger joined back to POs ---
        quality_rows = (
            await db.execute(
                select(
                    PurchaseOrder.supplier_id,
                    func.coalesce(func.sum(PurchaseReceiptLine.quantity_received), 0).label(
                        "received_quantity"
                    ),
                    func.coalesce(
                        func.sum(PurchaseReceiptLine.quantity_received).filter(
                            PurchaseReceiptLine.quality == "rejected"
                        ),
                        0,
                    ).label("rejected_quantity"),
                )
                .join(
                    PurchaseReceipt,
                    PurchaseReceipt.id == PurchaseReceiptLine.receipt_id,
                )
                .join(PurchaseOrder, PurchaseOrder.id == PurchaseReceipt.purchase_order_id)
                .where(
                    PurchaseOrder.clinic_id == clinic_id,
                    PurchaseOrder.supplier_id.in_(ids),
                )
                .group_by(PurchaseOrder.supplier_id)
            )
        ).all()
        for supplier_id, received_qty, rejected_qty in quality_rows:
            entry = metrics.setdefault(supplier_id, SupplierRatingMetrics())
            entry.received_quantity = received_qty
            entry.rejected_quantity = rejected_qty
            entry.reject_rate = (
                (rejected_qty / received_qty).quantize(Decimal("0.01")) if received_qty else None
            )

        return metrics

    @staticmethod
    async def _review_for(
        db: AsyncSession, clinic_id: UUID, supplier_ids: list[UUID]
    ) -> dict[UUID, SupplierReview]:
        """The review row per supplier (at most one by unique constraint)."""
        if not supplier_ids:
            return {}
        rows = (
            await db.execute(
                select(SupplierReview).where(
                    SupplierReview.clinic_id == clinic_id,
                    SupplierReview.supplier_id.in_(list(set(supplier_ids))),
                )
            )
        ).scalars()
        return {r.supplier_id: r for r in rows}

    @staticmethod
    async def list_ratings(
        db: AsyncSession, clinic_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        """Paginated supplier ratings page: contacts + metrics + review."""
        base = (
            select(Contact)
            .where(
                Contact.clinic_id == clinic_id,
                Contact.contact_type == "supplier",
                Contact.is_active.is_(True),
            )
            .order_by(Contact.name.asc())
        )
        total_stmt = select(func.count()).select_from(base.subquery())
        total = (await db.execute(total_stmt)).scalar_one()

        page_size = min(max(page_size, 1), 100)
        offset = (max(page, 1) - 1) * page_size
        contacts = (await db.execute(base.offset(offset).limit(page_size))).scalars().all()

        supplier_ids = [c.id for c in contacts]
        metrics = await SupplierRatingsService._metrics_for(db, clinic_id, supplier_ids)
        reviews = await SupplierRatingsService._review_for(db, clinic_id, supplier_ids)

        items: list[dict] = []
        for contact in contacts:
            m = metrics.get(contact.id, SupplierRatingMetrics())
            items.append(
                {
                    "supplier_id": contact.id,
                    "supplier_name": contact.name,
                    "metrics": m,
                    "review": reviews.get(contact.id),
                }
            )
        return items, total

    @staticmethod
    async def get_ratings(
        db: AsyncSession, clinic_id: UUID, supplier_id: UUID
    ) -> tuple[dict, Contact]:
        """Full rating detail for one supplier. 404 when not a supplier here."""
        contact = await SupplierRatingsService._assert_supplier(db, clinic_id, supplier_id)

        metrics = await SupplierRatingsService._metrics_for(db, clinic_id, [supplier_id])
        reviews = await SupplierRatingsService._review_for(db, clinic_id, [supplier_id])
        review = reviews.get(supplier_id)
        return (
            {
                "supplier_id": contact.id,
                "supplier_name": contact.name,
                "metrics": metrics.get(supplier_id, SupplierRatingMetrics()),
                "review": review,
            },
            contact,
        )

    @staticmethod
    async def create_review(
        db: AsyncSession,
        clinic_id: UUID,
        payload: SupplierReviewCreate,
        created_by: UUID | None,
    ) -> SupplierReview:
        """Set the manual 1-5 rating for a supplier (one per supplier)."""
        supplier_id = payload.supplier_id
        await SupplierRatingsService._assert_supplier(db, clinic_id, supplier_id)
        existing = (
            await db.execute(
                select(SupplierReview).where(
                    SupplierReview.clinic_id == clinic_id,
                    SupplierReview.supplier_id == supplier_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                "this supplier already has a rating; update it instead",
            )

        review = SupplierReview(
            clinic_id=clinic_id,
            supplier_id=supplier_id,
            score=payload.score,
            comment=payload.comment,
            created_by=created_by,
        )
        db.add(review)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                "this supplier already has a rating; update it instead",
            )
        await db.refresh(review)
        return review

    @staticmethod
    async def get_review(
        db: AsyncSession, clinic_id: UUID, review_id: UUID
    ) -> tuple[SupplierReview, Contact]:
        """Fetch a review with its supplier, scoped to the clinic."""
        review = (
            await db.execute(
                select(SupplierReview).where(
                    SupplierReview.id == review_id, SupplierReview.clinic_id == clinic_id
                )
            )
        ).scalar_one_or_none()
        if review is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "review not found")
        contact = await SupplierRatingsService._assert_supplier(db, clinic_id, review.supplier_id)
        return review, contact

    @staticmethod
    async def update_review(
        db: AsyncSession,
        clinic_id: UUID,
        review_id: UUID,
        payload: SupplierReviewUpdate,
    ) -> SupplierReview:
        """Edit score/comment in place."""
        review, _ = await SupplierRatingsService.get_review(db, clinic_id, review_id)
        if payload.score != review.score:
            review.score = payload.score
        review.comment = payload.comment
        await db.commit()
        await db.refresh(review)
        return review

    @staticmethod
    async def delete_review(db: AsyncSession, clinic_id: UUID, review_id: UUID) -> None:
        """Delete the manual rating row. 204 on success."""
        review, _ = await SupplierRatingsService.get_review(db, clinic_id, review_id)
        await db.delete(review)
        await db.commit()
