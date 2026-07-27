"""SupplierItem — links an inventory item to a supplier contact, with
per-supplier pricing.

Many-to-many between `inventory_items` and `contacts` (filtered to
`contact_type == "supplier"`) — one row per (supplier, item) pair, so
an item can be carried by multiple suppliers at different prices, and
a supplier can carry many items.

Prices are TND only (no currency column) — confirmed with the clinic
owner for Phase 13. If multi-currency is ever needed, add a
`currency` column with a server_default of 'TND' so existing rows
don't need backfilling.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class SupplierItem(Base, TimestampMixin):
    """One row = "supplier X sells item Y at price Z"."""

    __tablename__ = "supplier_items"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    supplier_contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    inventory_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True
    )

    supplier_sku: Mapped[str | None] = mapped_column(String(100))
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))
    is_preferred_supplier: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "supplier_contact_id", "inventory_item_id", name="uq_supplier_item_pair"
        ),
        Index("idx_supplier_items_clinic", "clinic_id"),
    )
