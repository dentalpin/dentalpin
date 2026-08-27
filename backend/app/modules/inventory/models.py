"""InventoryItem + StockMovement models (#226 core upgrade).

Cost tracking (``unit_cost``), an append-only **stock_movements** ledger
(audit trail: every quantity change is recorded with who/why/reference),
and ``is_active`` so items with history are deactivated instead of
deleted.

Concurrency: ``stock_quantity`` carries a CHECK (>= 0) constraint at the
DB level, and every quantity change goes through a ``SELECT … FOR UPDATE``
row lock (:meth:`InventoryService._apply_movement`) — never
read-modify-write.  PR #153's earlier inventory died on exactly this
race; see roadmap #220.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class InventoryItem(Base, TimestampMixin):
    """A stock item the clinic keeps on hand."""

    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_inventory_items_stock_non_negative"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50), index=True)
    unit: Mapped[str] = mapped_column(String(20), default="units")
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    # Cost tracking (#226): acquisition cost per unit, used by the
    # stock-valuation endpoint. Nullable — legacy/imported rows may not
    # have a known cost yet.
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    # Items with movement history are deactivated instead of deleted so
    # the audit trail stays meaningful.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    @property
    def is_low_stock(self) -> bool:
        """True when current stock has reached the minimum threshold."""
        return self.stock_quantity <= self.min_quantity


class StockMovement(Base):
    """Append-only ledger row: one per quantity change, never edited.

    The audit trail (#226): ``delta`` is the applied change (negative =
    consumption/deduction), ``reason`` says why, ``reference_type``/
    ``reference_id`` point at the triggering business object (e.g. a
    treatment performance) when one exists, and ``created_by`` attributes
    the actor (NULL for system/auto-deduction rows without a user).

    Partial unique index ``uq_stock_movements_consumption_ref`` on
    (reference_type, reference_id, inventory_item_id) WHERE
    reason = 'consumption' enforces idempotency: a duplicate deduction
    for the same treatment is silently ignored via ON CONFLICT DO NOTHING.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        Index("ix_stock_movements_clinic_created", "clinic_id", "created_at"),
        Index("ix_stock_movements_item_created", "inventory_item_id", "created_at"),
        Index(
            "uq_stock_movements_consumption_ref",
            "reference_type",
            "reference_id",
            "inventory_item_id",
            unique=True,
            postgresql_where="reason = 'consumption'",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"))
    inventory_item_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_items.id"))

    delta: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reason: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(200))

    # Business reference (e.g. reference_type='treatment_performance',
    # reference_id=<odontogram treatment id>). Loose link on purpose:
    # the referenced tables belong to other modules.
    reference_type: Mapped[str | None] = mapped_column(String(30))
    reference_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
