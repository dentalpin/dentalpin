"""SupplierProfile — one-to-one procurement extension of a `Contact`
row where `contact_type == "supplier"`.

Kept as its own table rather than new columns on `Contact` (Phase 13
§5's "either/or") because `Contact` is shared by labs/delegates/other
contact types with no use for website/payment_terms/lead_time — adding
them directly would mean every non-supplier row carries dead nulls.

Read/write relationship to `contacts` (`Contact`) — declared as a
dependency in this module's manifest. Never modifies `Contact` itself;
only reads it to validate `contact_type == "supplier"` before writing
to this table.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class SupplierProfile(Base, TimestampMixin):
    """Procurement-specific fields for a supplier contact.

    ``contact_id`` is both the primary key and the FK — this is a
    strict 1:1 extension, not a many-relationship.
    """

    __tablename__ = "supplier_profiles"

    contact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True
    )
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    website: Mapped[str | None] = mapped_column(String(255))
    payment_terms: Mapped[str | None] = mapped_column(String(100))
    # Used by Phase 13's later reorder-automation sub-delivery to factor
    # supplier lead time into suggested reorder timing. Not consumed
    # anywhere yet in this sub-delivery.
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)
