"""Supplier rating models - the manual 1-5 communication review."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.contacts.models import Contact


class SupplierReview(Base, TimestampMixin):
    """A manual 1-5 communication rating for one supplier in a clinic.

    One review row per (clinic, supplier) - the current communication
    score, edited in place. Delivery/quality metrics are NOT stored: they
    are computed on demand from purchase order history.
    """

    __tablename__ = "supplier_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    supplier_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"), index=True, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    __table_args__ = (
        UniqueConstraint("clinic_id", "supplier_id", name="uq_supplier_reviews_clinic_supplier"),
        CheckConstraint("score >= 1 AND score <= 5", name="ck_supplier_reviews_score_range"),
        Index("ix_supplier_reviews_supplier_clinic", "supplier_id", "clinic_id"),
    )

    contact: Mapped[Contact] = relationship(foreign_keys=[supplier_id])
