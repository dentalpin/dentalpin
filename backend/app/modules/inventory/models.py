"""InventoryItem + InventoryMovement entities.

``InventoryItem`` is the stock-on-hand record (unchanged shape, plus two
new cost columns). ``InventoryMovement`` (new in Phase 12) is an
append-only audit trail of every quantity change — purchases, returns,
donations, manual adjustments, damage/expiry/loss, and usage. The legacy
``/adjust`` endpoint still works: it now records an ``adjustment``
movement under the hood instead of mutating quantity directly.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin

INVENTORY_CATEGORIES = ("consumables", "ppe", "materials", "medication", "other")

# Movement reasons. Direction (in vs. out) is carried by the sign of
# ``quantity_delta``, not by the reason itself — mirrors the existing
# ``InventoryAdjust.delta`` convention (signed) rather than inventing a
# second directionality concept. Typically purchase/return/donation are
# positive and damaged/expired/lost/used are negative; ``adjustment``
# can be either (manual stock-count correction).
INVENTORY_MOVEMENT_REASONS = (
    "purchase",
    "return",
    "donation",
    "adjustment",
    "damaged",
    "expired",
    "lost",
    "used",
)


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
    # Cost of the most recent "purchase" movement. Nullable — items
    # created before Phase 12, or never purchased through a movement,
    # have no known cost yet.
    unit_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Moving average cost across all "purchase" movements (AVCO costing).
    # Recomputed incrementally in InventoryService.record_movement —
    # never touched by non-purchase movements, since those change
    # quantity but not the cost basis of what remains.
    average_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Target stock level for reorder automation (Phase 13e) — "reorder
    # up to this quantity". Nullable: without it, the reorder-suggestion
    # heuristic falls back to average-usage-based sizing instead of a
    # hard target. Optional per item, not required.
    reorder_max_quantity: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    @property
    def is_low_stock(self) -> bool:
        return self.quantity_on_hand <= self.low_stock_threshold


class InventoryMovement(Base, TimestampMixin):
    """Append-only audit trail of a single stock quantity change.

    ``quantity_after`` is a denormalized snapshot of the item's
    quantity-on-hand immediately after this movement, so the audit
    trail is readable without replaying the whole history.
    """

    __tablename__ = "inventory_movements"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(String(20), index=True)
    quantity_delta: Mapped[float] = mapped_column(Numeric(10, 2))
    quantity_after: Mapped[float] = mapped_column(Numeric(10, 2))
    # Only meaningful for "purchase" movements; kept nullable so other
    # reasons don't need a throwaway value.
    unit_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    movement_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    __table_args__ = (
        CheckConstraint(
            "reason IN (" + ", ".join(f"'{r}'" for r in INVENTORY_MOVEMENT_REASONS) + ")",
            name="ck_inventory_movement_reason_valid",
        ),
        Index(
            "ix_inventory_movements_item_movement_date",
            "item_id",
            "movement_date",
        ),
    )
