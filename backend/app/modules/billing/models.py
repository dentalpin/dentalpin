"""Billing module database models."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic, User
    from app.modules.budget.models import Budget, BudgetItem
    from app.modules.catalog.models import TreatmentCatalogItem, VatType
    from app.modules.patients.models import Patient
    from app.modules.payments.models import Payment


class InvoiceSeries(Base, TimestampMixin):
    """Invoice series for numbering control.

    Supports different series for invoices and credit notes,
    with optional yearly reset and prefix customization.
    """

    __tablename__ = "invoice_series"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    # Series configuration
    prefix: Mapped[str] = mapped_column(String(20))  # "FAC", "RECT"
    series_type: Mapped[str] = mapped_column(String(20))  # "invoice", "credit_note"
    description: Mapped[str | None] = mapped_column(String(200), default=None)

    # Numbering control
    current_number: Mapped[int] = mapped_column(Integer, default=0)
    reset_yearly: Mapped[bool] = mapped_column(Boolean, default=True)
    last_reset_year: Mapped[int | None] = mapped_column(Integer, default=None)

    # Flags
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    clinic: Mapped["Clinic"] = relationship()
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="series")

    __table_args__ = (
        UniqueConstraint("clinic_id", "prefix", name="uq_invoice_series_clinic_prefix"),
        Index("idx_invoice_series_clinic", "clinic_id"),
        Index("idx_invoice_series_clinic_type", "clinic_id", "series_type"),
    )


class Invoice(Base, TimestampMixin):
    """Main invoice entity.

    Supports regular invoices and credit notes (rectificativas).
    Includes generic extensibility fields for country compliance modules.
    """

    __tablename__ = "invoices"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)

    # Identification (assigned on issue, not on creation)
    invoice_number: Mapped[str | None] = mapped_column(
        String(50), default=None
    )  # "FAC-2024-0001" - assigned when issued
    series_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("invoice_series.id"), index=True, default=None
    )
    sequential_number: Mapped[int | None] = mapped_column(
        Integer, default=None
    )  # For gap control - assigned when issued
    fiscal_year: Mapped[int | None] = mapped_column(
        Integer, default=None
    )  # Year the sequential was drawn in (the year in invoice_number) - assigned when issued

    # Links
    budget_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("budgets.id"), index=True, default=None
    )
    credit_note_for_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("invoices.id"), index=True, default=None
    )  # For credit notes

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="draft"
    )  # draft, issued, partial, paid, cancelled, voided

    # Dates
    issue_date: Mapped[date | None] = mapped_column(Date, default=None)
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    payment_term_days: Mapped[int] = mapped_column(Integer, default=30)

    # Billing data (null for drafts, snapshotted when issued)
    billing_name: Mapped[str | None] = mapped_column(
        String(200), default=None
    )  # Nombre/razón social
    billing_tax_id: Mapped[str | None] = mapped_column(String(50), default=None)  # NIF/CIF
    billing_address: Mapped[dict | None] = mapped_column(
        JSONB, default=None
    )  # {street, city, postal_code, country}
    billing_email: Mapped[str | None] = mapped_column(String(255), default=None)

    # Totals (Decimal for money). `total_paid` and `balance_due` are no
    # longer stored — they are computed from ``InvoicePayment`` minus
    # proportional refunds via ``BillingService.invoice_paid_summary``.
    # The Invoice keeps only the gross invoice totals here.
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total_discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total_tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    # Notes
    internal_notes: Mapped[str | None] = mapped_column(Text, default=None)
    public_notes: Mapped[str | None] = mapped_column(Text, default=None)  # Appears in PDF

    # Extensibility for country compliance modules (generic)
    compliance_data: Mapped[dict | None] = mapped_column(
        JSONB, default=None
    )  # {"ES": {...}, "FR": {...}}
    document_hash: Mapped[str | None] = mapped_column(String(64), default=None)  # SHA-256
    previous_hash: Mapped[str | None] = mapped_column(String(64), default=None)  # For hash chain

    # Set when a compliance hook regenerates the fiscal record (e.g.
    # Verifactu Subsanación) so the previously rendered PDF/QR no longer
    # matches the canonical huella. UI surfaces a "PDF desactualizado"
    # badge until the user re-downloads.
    pdf_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Audit
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    issued_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Relationships
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])
    patient: Mapped["Patient"] = relationship()
    series: Mapped["InvoiceSeries | None"] = relationship(back_populates="invoices")
    budget: Mapped["Budget | None"] = relationship()
    credit_note_for: Mapped["Invoice | None"] = relationship(
        remote_side="Invoice.id", foreign_keys=[credit_note_for_id]
    )
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    issuer: Mapped["User | None"] = relationship(foreign_keys=[issued_by])
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceItem.display_order",
    )
    invoice_payments: Mapped[list["InvoicePayment"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoicePayment.created_at",
    )
    history: Mapped[list["InvoiceHistory"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceHistory.changed_at.desc()",
    )

    __table_args__ = (
        Index("idx_invoices_clinic", "clinic_id"),
        Index("idx_invoices_clinic_patient", "clinic_id", "patient_id"),
        Index("idx_invoices_clinic_status", "clinic_id", "status"),
        Index("idx_invoices_clinic_issue_date", "clinic_id", "issue_date"),
        Index("idx_invoices_clinic_due_date", "clinic_id", "due_date"),
        Index("idx_invoices_budget", "budget_id"),
        Index("idx_invoices_credit_note_for", "credit_note_for_id"),
        Index("idx_invoices_series", "series_id"),
        # Fiscal uniqueness backstop (bil_0005, bil_0006). Partial — drafts carry
        # NULL identifiers and must not collide. Enforced at the DB level
        # because number generation being serialized on the series row
        # lock is not, by itself, a guarantee against duplicates.
        Index(
            "ix_invoices_clinic_number_unique",
            "clinic_id",
            "invoice_number",
            unique=True,
            postgresql_where=text("invoice_number IS NOT NULL"),
        ),
        # The sequential restarts each year on a ``reset_yearly`` series,
        # so it is unique per (series, fiscal year) (bil_0006, #689).
        # NULLS NOT DISTINCT keeps a row without a year under the
        # lifetime rule rather than outside the index.
        Index(
            "ix_invoices_series_year_sequential_unique",
            "series_id",
            "fiscal_year",
            "sequential_number",
            unique=True,
            postgresql_where=text("series_id IS NOT NULL AND sequential_number IS NOT NULL"),
            postgresql_nulls_not_distinct=True,
        ),
    )


class InvoiceItem(Base, TimestampMixin):
    """Individual line item in an invoice.

    References budget items and/or catalog items with snapshotted pricing.
    Supports partial invoicing from budgets.
    """

    __tablename__ = "invoice_items"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )

    # Links for traceability
    budget_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("budget_items.id"), index=True, default=None
    )
    catalog_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("treatment_catalog_items.id"), index=True, default=None
    )

    # Description (snapshotted)
    description: Mapped[str] = mapped_column(String(500))  # Treatment name
    internal_code: Mapped[str | None] = mapped_column(String(50), default=None)

    # Pricing and quantity (supports partial invoicing)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    # Discounts
    discount_type: Mapped[str | None] = mapped_column(
        String(20), default=None
    )  # percentage, absolute
    discount_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)

    # VAT
    vat_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vat_types.id"), index=True, default=None
    )
    vat_rate: Mapped[float] = mapped_column(Float, default=0.0)  # Snapshotted
    vat_exempt_reason: Mapped[str | None] = mapped_column(
        String(200), default=None
    )  # For exemptions

    # Calculated totals
    line_subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00")
    )  # unit_price * quantity
    line_discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    line_tax: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))

    # Dental context (optional)
    tooth_number: Mapped[int | None] = mapped_column(Integer, default=None)  # FDI
    surfaces: Mapped[list | None] = mapped_column(JSONB, default=None)  # ["M", "O", "D"]

    # Display
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    clinic: Mapped["Clinic"] = relationship()
    invoice: Mapped["Invoice"] = relationship(back_populates="items")
    budget_item: Mapped["BudgetItem | None"] = relationship()
    catalog_item: Mapped["TreatmentCatalogItem | None"] = relationship()
    vat_type: Mapped["VatType | None"] = relationship()

    __table_args__ = (
        Index("idx_invoice_items_invoice", "invoice_id"),
        Index("idx_invoice_items_budget_item", "budget_item_id"),
        Index("idx_invoice_items_catalog_item", "catalog_item_id"),
    )


class InvoicePayment(Base, TimestampMixin):
    """Link between an Invoice and a Payment from the ``payments`` module.

    Billing owns this link in its own schema so the payments module
    never needs a back-reference to billing. One row per imputation —
    a single Payment can have multiple ``InvoicePayment`` rows when its
    allocations span several invoices, and a single Invoice can collect
    via several Payments. ``Invoice.total_paid`` / ``balance_due`` are
    computed by aggregating amounts here minus proportional refunds on
    the underlying Payment.
    """

    __tablename__ = "invoice_payments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])
    invoice: Mapped["Invoice"] = relationship(back_populates="invoice_payments")
    payment: Mapped["Payment"] = relationship(foreign_keys=[payment_id])
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_invpay_clinic_invoice", "clinic_id", "invoice_id"),
        Index("idx_invpay_payment", "payment_id"),
    )


class InvoiceHistory(Base):
    """Audit log for invoice changes.

    Records all changes to invoices for traceability and compliance.
    """

    __tablename__ = "invoice_history"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )

    # Action performed
    action: Mapped[str] = mapped_column(
        String(50)
    )  # created, updated, issued, voided, payment_recorded, payment_voided, credit_note_created

    # Actor
    changed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # State snapshots
    previous_state: Mapped[dict | None] = mapped_column(JSONB, default=None)
    new_state: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # Additional context
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    # Relationships
    clinic: Mapped["Clinic"] = relationship()
    invoice: Mapped["Invoice"] = relationship(back_populates="history")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_invoice_history_invoice", "invoice_id"),
        Index("idx_invoice_history_clinic", "clinic_id"),
        Index("idx_invoice_history_changed_at", "changed_at"),
    )


class InvoiceSeriesHistory(Base):
    """Audit log for invoice series changes.

    Records all changes to series configuration for compliance tracking.
    """

    __tablename__ = "invoice_series_history"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    series_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoice_series.id", ondelete="CASCADE"), index=True
    )

    # Action performed
    action: Mapped[str] = mapped_column(String(50))  # created, updated, reset

    # Actor
    changed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # State snapshots
    previous_state: Mapped[dict | None] = mapped_column(JSONB, default=None)
    new_state: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # Additional context
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    # Relationships
    clinic: Mapped["Clinic"] = relationship()
    series: Mapped["InvoiceSeries"] = relationship()
    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_invoice_series_history_series", "series_id"),
        Index("idx_invoice_series_history_clinic", "clinic_id"),
        Index("idx_invoice_series_history_changed_at", "changed_at"),
    )
