"""PurchaseOrder + PurchaseOrderItem — Phase 13c.

Mirrors the shape of `billing.Invoice`/`InvoiceItem` (header + line
items + snapshotted pricing + totals) but deliberately simpler: no
per-line VAT/fiscal-compliance machinery — that's invoicing-specific,
not needed for an internal procurement document to a supplier.

``quantity_received`` lives on the line item now (default 0) even
though nothing in this sub-delivery writes to it — Phase 13d
(Receiving) will update it in place rather than needing a second
migration to add the column later.

Status lifecycle: draft → sent → confirmed → partially_received →
fully_received, with cancelled reachable from draft/sent/confirmed.
This module's service only drives draft→sent→confirmed→cancelled;
partially_received/fully_received are set exclusively by the Phase 13d
receiving flow (never directly via this API) — see service.py.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

PURCHASE_ORDER_STATUSES = (
    "draft",
    "sent",
    "confirmed",
    "partially_received",
    "fully_received",
    "cancelled",
)

# Quality outcome per received line. "good" is the only status that
# results in an InventoryMovement (usable stock) — damaged/expired/
# wrong_item are logged for accountability (and future supplier
# ratings, Phase 13e) but never added to quantity_on_hand.
RECEIPT_LINE_QUALITY_STATUSES = ("good", "damaged", "expired", "wrong_item")


class PurchaseOrder(Base, TimestampMixin):
    """Header: supplier, dates, shipping/tax, computed totals, status."""

    __tablename__ = "purchase_orders"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    po_number: Mapped[str] = mapped_column(String(50))  # "PO-2026-0001"
    supplier_contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("contacts.id"), index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)

    order_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    shipping_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    # Sum of line_total across items — kept denormalized (recomputed by
    # the service on every line-item add/edit/remove) so the list view
    # doesn't need to aggregate items per row.
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    notes: Mapped[str | None] = mapped_column(Text)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderItem.display_order",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in PURCHASE_ORDER_STATUSES) + ")",
            name="ck_purchase_order_status_valid",
        ),
        UniqueConstraint("clinic_id", "po_number", name="uq_purchase_order_clinic_number"),
        Index("idx_purchase_orders_clinic_status", "clinic_id", "status"),
        Index("idx_purchase_orders_supplier", "supplier_contact_id"),
    )


class PurchaseOrderItem(Base, TimestampMixin):
    """One line item — an inventory item, ordered quantity, snapshotted price."""

    __tablename__ = "purchase_order_items"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    inventory_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_items.id"), index=True
    )

    # Snapshotted at add-time so later renames/price changes on
    # InventoryItem don't retroactively alter a historical PO.
    description: Mapped[str] = mapped_column(String(200))
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))

    quantity_ordered: Mapped[float] = mapped_column(Numeric(10, 2), default=1)
    # Written only by Phase 13d (Receiving) — present now so that
    # phase doesn't need its own migration on this table.
    quantity_received: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    line_total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")

    __table_args__ = (
        Index("idx_po_items_purchase_order", "purchase_order_id"),
        Index("idx_po_items_inventory_item", "inventory_item_id"),
    )


class PurchaseOrderReceipt(Base, TimestampMixin):
    """One delivery event against a PO — may cover some or all line
    items, partial quantities. A PO can have several receipts
    (partial deliveries arriving over time)."""

    __tablename__ = "purchase_order_receipts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    received_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    received_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["PurchaseOrderReceiptLine"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_po_receipts_purchase_order", "purchase_order_id"),)


class PurchaseOrderReceiptLine(Base, TimestampMixin):
    """One line-item's outcome within a receipt: quantity + quality.

    ``quantity_received`` here is the delta for THIS receipt event —
    the running total lives on ``PurchaseOrderItem.quantity_received``,
    incremented by the service when the receipt is recorded.
    """

    __tablename__ = "purchase_order_receipt_lines"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_order_receipts.id", ondelete="CASCADE"), index=True
    )
    purchase_order_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_order_items.id", ondelete="CASCADE"), index=True
    )
    quantity_received: Mapped[float] = mapped_column(Numeric(10, 2))
    quality_status: Mapped[str] = mapped_column(String(20), default="good")
    notes: Mapped[str | None] = mapped_column(Text)

    receipt: Mapped[PurchaseOrderReceipt] = relationship(back_populates="lines")

    __table_args__ = (
        CheckConstraint(
            "quality_status IN ("
            + ", ".join(f"'{s}'" for s in RECEIPT_LINE_QUALITY_STATUSES)
            + ")",
            name="ck_po_receipt_line_quality_valid",
        ),
        Index("idx_po_receipt_lines_receipt", "receipt_id"),
        Index("idx_po_receipt_lines_po_item", "purchase_order_item_id"),
    )
