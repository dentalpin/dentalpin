"""SupplierRating — Phase 13e.

Delivery-time and quality metrics are computed on the fly from
existing `purchase_orders`/`purchase_order_receipts` data (see
service.py) — there's nothing to store for those, they're derived.

"Communication" has no event trail anywhere in this app (there's no
way to infer it from data), so it's the one dimension that needs an
actual manual entry — a lightweight periodic rating staff can log
after dealing with a supplier. Price is also shown computed (average
unit price paid), not rated subjectively.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class SupplierRating(Base, TimestampMixin):
    """One manual communication/overall rating entry for a supplier."""

    __tablename__ = "supplier_ratings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    supplier_contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"), index=True)

    communication_score: Mapped[int] = mapped_column(Integer)  # 1-5
    notes: Mapped[str | None] = mapped_column(Text)

    rated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    rated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "communication_score >= 1 AND communication_score <= 5",
            name="ck_supplier_rating_score_range",
        ),
        Index("idx_supplier_ratings_supplier", "supplier_contact_id"),
    )
