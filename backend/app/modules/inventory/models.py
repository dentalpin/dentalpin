"""Inventory module — stock list with low-stock alerts.

Issue #220. Standalone, optional, removable. No module dependencies.

Two tables:

* ``inventory_categories`` — per-clinic item grouping.
* ``inventory_items`` — individual stock items with quantity tracking.

Base version only — cost tracking, stock movements and auto-deduction
come later in the inventory core upgrade (issue #226).

Race condition guard (from #153): the service layer uses an atomic
``UPDATE … SET quantity = quantity + :delta WHERE quantity + :delta >= 0``
so concurrent stock adjustments serialize at the DB level, not in
application code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class InventoryCategory(Base, TimestampMixin):
    """Per-clinic grouping for inventory items (e.g. 'Consumibles', 'Medicamentos')."""

    __tablename__ = "inventory_categories"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_inventory_categories_clinic_name", "clinic_id", "name", unique=True),
    )


class InventoryItem(Base, TimestampMixin):
    """Individual stock item with quantity tracking.

    ``quantity`` is updated via atomic SQL (``quantity + :delta >= 0``)
    to prevent the race condition documented in issue #153.  The service
    layer enforces this; application-level locking is intentionally
    avoided.
    """

    __tablename__ = "inventory_items"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )
    category_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_categories.id")
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="units")

    location: Mapped[str | None] = mapped_column(String(200))
    supplier: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    is_low_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    __table_args__ = (
        Index("ix_inventory_items_clinic_code", "clinic_id", "code", unique=True),
        Index("ix_inventory_items_clinic_category", "clinic_id", "category_id"),
    )
