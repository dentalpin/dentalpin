"""Purchase order models - PO, lines, and receipt batches."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# PO lifecycle: draft -> sent -> confirmed -> (received|cancelled).
# ``received`` is stamped implicitly when every line fulfils.
PO_STATUSES = frozenset({"draft", "sent", "confirmed", "received", "cancelled"})


class PurchaseOrder(Base):
    """A purchase order placed with a supplier (a Contact of type supplier)."""

    __tablename__ = "purchase_orders"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    supplier_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"), index=True, nullable=False)

    status: Mapped[str] = mapped_column(String(20), index=True, default="draft")
    expected_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PurchaseOrderLine(Base):
    """One inventory item on a PO, with ordered/received quantities."""

    __tablename__ = "purchase_order_lines"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id"), index=True, nullable=False
    )
    inventory_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_items.id"), index=True, nullable=False
    )

    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Accepted (quality='good') units only; rejected units live on the
    # receipt lines and keep the line open for a replacement delivery.
    quantity_received: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=0, server_default="0"
    )
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    __table_args__ = (
        UniqueConstraint("purchase_order_id", "inventory_item_id", name="uq_po_line_item"),
    )


class PurchaseReceipt(Base):
    """A batch received against a PO — partial deliveries supported."""

    __tablename__ = "purchase_receipts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id"), index=True, nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    received_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))


class PurchaseReceiptLine(Base):
    """Per-line received quantity and quality verdict (good/rejected)."""

    __tablename__ = "purchase_receipt_lines"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_receipts.id"), index=True, nullable=False
    )
    purchase_order_line_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_order_lines.id"), index=True, nullable=False
    )
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quality: Mapped[str] = mapped_column(String(20), default="good")
