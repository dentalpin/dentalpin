"""InventoryItem entity — a simple stock-on-hand list with a low-stock threshold."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin

INVENTORY_CATEGORIES = ("consumables", "ppe", "materials", "medication", "other")


class InventoryItem(Base, TimestampMixin):
    """A stock item tracked by quantity on hand, with a low-stock threshold."""

    __tablename__ = "inventory_items"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(20), index=True, default="other")
    unit: Mapped[str | None] = mapped_column(String(30))
    quantity_on_hand: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    low_stock_threshold: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    @property
    def is_low_stock(self) -> bool:
        return self.quantity_on_hand <= self.low_stock_threshold
