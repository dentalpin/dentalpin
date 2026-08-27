"""Billing module Pydantic schemas for API request/response."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================================
# Invoice Status and Payment Types
# ============================================================================

InvoiceStatus = Literal["draft", "issued", "partial", "paid", "cancelled", "voided"]

# Payment domain literals live in the payments module; billing only
# imports them where it orchestrates Payment+InvoicePayment creation.
from app.modules.budget.schemas import TreatmentPlanBrief  # noqa: E402
from app.modules.payments.schemas import PaymentMethod as PaymentMethodLiteral  # noqa: E402
from app.modules.payments.schemas import PaymentResponse  # noqa: E402

PaymentMethod = PaymentMethodLiteral

SeriesType = Literal["invoice", "credit_note"]

DiscountType = Literal["percentage", "absolute"]


# ============================================================================
# Brief Schemas (for nested responses)
# ============================================================================


class PatientBrief(BaseModel):
    """Brief patient info for invoice responses."""

    id: UUID
    first_name: str
    last_name: str
    email: str | None = None
    # Billing fields for draft invoices (dynamic billing data)
    billing_name: str | None = None
    billing_tax_id: str | None = None
    billing_address: dict | None = None
    billing_email: str | None = None
    has_complete_billing_info: bool = False

    model_config = ConfigDict(from_attributes=True)


class UserBrief(BaseModel):
    """Brief user info for invoice responses."""

    id: UUID
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)


class BudgetBrief(BaseModel):
    """Brief budget info for invoice responses."""

    id: UUID
    budget_number: str
    status: str
    total: Decimal

    model_config = ConfigDict(from_attributes=True)


class CatalogItemBrief(BaseModel):
    """Brief catalog item info for invoice items."""

    id: UUID
    internal_code: str
    names: dict[str, str]
    default_price: Decimal | None

    model_config = ConfigDict(from_attributes=True)


class VatTypeBrief(BaseModel):
    """Brief VAT type info for invoice items."""

    id: UUID
    names: dict[str, str]
    rate: float

    model_config = ConfigDict(from_attributes=True)


class InvoiceBrief(BaseModel):
    """Brief invoice info for credit note references."""

    id: UUID
    invoice_number: str
    status: str
    total: Decimal
    issue_date: date | None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Invoice Series Schemas
# ============================================================================


class InvoiceSeriesCreate(BaseModel):
    """Schema for creating an invoice series."""

    prefix: str = Field(min_length=1, max_length=20)
    series_type: SeriesType
    description: str | None = None
    reset_yearly: bool = True
    is_default: bool = False


class InvoiceSeriesUpdate(BaseModel):
    """Schema for updating an invoice series."""

    prefix: str | None = Field(default=None, min_length=1, max_length=20)
    description: str | None = None
    reset_yearly: bool | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class SeriesResetRequest(BaseModel):
    """Schema for resetting a series counter."""

    new_number: int = Field(ge=1)


class InvoiceSeriesResponse(BaseModel):
    """Schema for invoice series response."""

    id: UUID
    clinic_id: UUID
    prefix: str
    series_type: str
    description: str | None
    current_number: int
    reset_yearly: bool
    last_reset_year: int | None
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Invoice Item Schemas
# ============================================================================


class InvoiceItemCreate(BaseModel):
    """Schema for creating an invoice item."""

    # For manual items
    description: str = Field(min_length=1, max_length=500)
    internal_code: str | None = None
    catalog_item_id: UUID | None = None

    # Pricing
    unit_price: Decimal = Field(ge=0)
    quantity: int = Field(default=1, ge=1)

    # Discounts
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = Field(default=None, ge=0)

    # VAT
    vat_type_id: UUID | None = None
    vat_exempt_reason: str | None = None

    # Dental context
    tooth_number: int | None = Field(default=None, ge=11, le=85)
    surfaces: list[str] | None = None

    # Display
    display_order: int = 0


class InvoiceItemFromBudget(BaseModel):
    """Schema for creating invoice item from budget item."""

    budget_item_id: UUID
    quantity: int | None = Field(default=None, ge=1)  # None = invoice remaining quantity


class InvoiceItemUpdate(BaseModel):
    """Schema for updating an invoice item."""

    description: str | None = Field(default=None, min_length=1, max_length=500)
    unit_price: Decimal | None = Field(default=None, ge=0)
    quantity: int | None = Field(default=None, ge=1)

    # Discounts
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = Field(default=None, ge=0)

    # VAT
    vat_type_id: UUID | None = None
    vat_exempt_reason: str | None = None

    # Display
    display_order: int | None = None


class InvoiceItemResponse(BaseModel):
    """Schema for invoice item response."""

    id: UUID
    invoice_id: UUID
    budget_item_id: UUID | None
    catalog_item_id: UUID | None

    # Description
    description: str
    internal_code: str | None

    # Pricing
    unit_price: Decimal
    quantity: int

    # Discounts
    discount_type: str | None
    discount_value: Decimal | None

    # VAT
    vat_type_id: UUID | None
    vat_rate: float
    vat_exempt_reason: str | None

    # Calculated totals
    line_subtotal: Decimal
    line_discount: Decimal
    line_tax: Decimal
    line_total: Decimal

    # Dental context
    tooth_number: int | None
    surfaces: list[str] | None

    # Display
    display_order: int

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Related
    catalog_item: CatalogItemBrief | None = None
    vat_type: VatTypeBrief | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Payment Schemas
# ============================================================================


class InvoicePaymentApply(BaseModel):
    """Orchestrator payload for ``POST /invoices/{id}/payments``.

    The endpoint creates a Payment via the payments module's workflow,
    creates the ``InvoicePayment`` link, and recomputes invoice status
    — all in one transaction. Use the payments module endpoints
    directly when the cobro is not tied to a specific invoice.
    """

    amount: Decimal = Field(gt=0)
    method: PaymentMethod
    payment_date: date = Field(default_factory=date.today)
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = None

    @field_validator("reference", "notes", mode="before")
    @classmethod
    def _empty_to_none(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
        return v


class InvoicePaymentResponse(BaseModel):
    """Link row between an invoice and a payment."""

    id: UUID
    invoice_id: UUID
    payment_id: UUID
    amount: Decimal
    created_by: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoicePaymentDetailResponse(InvoicePaymentResponse):
    """Link row with the underlying Payment embedded.

    Served by ``GET /invoices/{id}/payments`` so invoice-side views can show
    the payment date/method without a call per row to the payments module.
    """

    payment: PaymentResponse


# ============================================================================
# Invoice History Schemas
# ============================================================================


class InvoiceHistoryResponse(BaseModel):
    """Schema for invoice history response."""

    id: UUID
    invoice_id: UUID
    action: str
    changed_by: UUID
    changed_at: datetime
    previous_state: dict | None
    new_state: dict | None
    notes: str | None

    # Related
    user: UserBrief | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Invoice Schemas
# ============================================================================


class BillingAddress(BaseModel):
    """Schema for billing address."""

    street: str | None = None
    city: str | None = None
    postal_code: str | None = None
    province: str | None = None
    country: str = "ES"


class InvoiceCreate(BaseModel):
    """Schema for creating an invoice manually.

    Billing data is NOT provided here - drafts get billing data from patient dynamically.
    When issued, billing data is snapshotted from patient.
    """

    patient_id: UUID

    # Series (if not provided, uses default)
    series_id: UUID | None = None

    # Payment terms
    payment_term_days: int = Field(default=30, ge=0)
    due_date: date | None = None

    # Notes
    internal_notes: str | None = None
    public_notes: str | None = None

    # Items (optional, can be added later)
    items: list[InvoiceItemCreate] = Field(default_factory=list)


class InvoiceFromBudgetCreate(BaseModel):
    """Schema for creating an invoice from a budget.

    Billing data is NOT provided here - drafts get billing data from patient dynamically.
    When issued, billing data is snapshotted from patient.
    """

    # Items to invoice (supports partial invoicing)
    items: list[InvoiceItemFromBudget]

    # Payment terms
    payment_term_days: int | None = None
    due_date: date | None = None

    # Notes
    internal_notes: str | None = None
    public_notes: str | None = None


class InvoiceUpdate(BaseModel):
    """Schema for updating an invoice (only allowed in draft status)."""

    # Patient (can be changed for drafts)
    patient_id: UUID | None = None

    # Payment terms
    payment_term_days: int | None = Field(default=None, ge=0)
    due_date: date | None = None

    # Notes
    internal_notes: str | None = None
    public_notes: str | None = None


class BillingPartyUpdate(BaseModel):
    """Edit billing-party fields on an issued invoice.

    Allowed only when the country compliance hook says the invoice is in
    a correctable state (e.g. a Verifactu record currently ``rejected``
    so AEAT never registered the original data) — see workflow gate.
    """

    billing_name: str | None = Field(default=None, max_length=200)
    billing_tax_id: str | None = Field(default=None, max_length=50)
    billing_address: dict | None = None
    expected_updated_at: datetime | None = Field(
        default=None,
        description="Echo of Invoice.updated_at — optimistic lock; 409 on mismatch.",
    )


class InvoiceResponse(BaseModel):
    """Schema for invoice response."""

    id: UUID
    clinic_id: UUID
    patient_id: UUID

    # Identification (null for drafts, assigned when issued)
    invoice_number: str | None
    sequential_number: int | None
    series_id: UUID | None

    # Links
    budget_id: UUID | None
    credit_note_for_id: UUID | None

    # Status
    status: str

    # Dates
    issue_date: date | None
    due_date: date | None
    payment_term_days: int

    # Billing data (null for drafts, populated from patient; snapshotted for issued)
    billing_name: str | None
    billing_tax_id: str | None
    billing_address: dict | None
    billing_email: str | None

    # Totals. ``total_paid`` / ``balance_due`` are computed from
    # ``invoice_payments`` at response build time — the router populates
    # them from ``compute_paid_summary`` rather than reading model
    # attributes.
    subtotal: Decimal
    total_discount: Decimal
    total_tax: Decimal
    total: Decimal
    total_paid: Decimal = Decimal("0")
    balance_due: Decimal = Decimal("0")

    # Notes
    internal_notes: str | None
    public_notes: str | None

    # Extensibility
    compliance_data: dict | None
    document_hash: str | None
    pdf_stale: bool = False

    # Audit
    created_by: UUID
    issued_by: UUID | None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    # Related
    patient: PatientBrief | None = None
    creator: UserBrief | None = None
    issuer: UserBrief | None = None
    budget: BudgetBrief | None = None
    # Plan behind the quote, resolved at read time (billing has no FK to
    # treatment_plan — it is not in ``depends``; issue #181).
    treatment_plan: TreatmentPlanBrief | None = None
    credit_note_for: InvoiceBrief | None = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceDetailResponse(InvoiceResponse):
    """Schema for invoice with full details including items and payment links."""

    items: list[InvoiceItemResponse] = []
    invoice_payments: list[InvoicePaymentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class InvoiceListResponse(BaseModel):
    """Schema for invoice list item (lighter than full response)."""

    id: UUID
    invoice_number: str | None  # Null for drafts (assigned when issued)
    status: str
    issue_date: date | None
    due_date: date | None
    total: Decimal
    total_paid: Decimal = Decimal("0")
    balance_due: Decimal = Decimal("0")
    created_at: datetime

    # Generic compliance summary — shape is country-keyed
    # ({"ES": {state, severity, error_message, ...}}) and entirely owned
    # by compliance modules (verifactu et al.). Billing exposes it raw
    # so country-specific UI slots can render badges without a second
    # round-trip.
    compliance_data: dict | None = None

    # Related (brief)
    patient: PatientBrief | None = None
    creator: UserBrief | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Workflow Schemas
# ============================================================================


class InvoiceIssueRequest(BaseModel):
    """Schema for issuing an invoice."""

    issue_date: date = Field(default_factory=date.today)


class CreditNoteItemSelect(BaseModel):
    """Schema for selecting items for a credit note."""

    invoice_item_id: UUID
    quantity: int | None = Field(default=None, ge=1)  # None = full quantity of original item


class CreditNoteCreate(BaseModel):
    """Schema for creating a credit note."""

    reason: str = Field(min_length=1, max_length=500)

    # Partial credit note: specify items to rectify
    # If empty, creates full credit note for entire invoice
    items: list[CreditNoteItemSelect] = Field(default_factory=list)

    # Notes
    internal_notes: str | None = None
    public_notes: str | None = None


class InvoiceSendRequest(BaseModel):
    """Schema for sending an invoice to the patient.

    ``send_method`` picks the wire: ``manual`` (just mark as sent),
    ``email`` or ``whatsapp`` (gateway send on that channel). The legacy
    ``send_email`` flag is honoured when ``send_method`` is omitted so
    older clients keep working.
    """

    send_method: Literal["manual", "email", "whatsapp"] | None = None
    send_email: bool = True  # legacy client flag; if false, marks as "sent" manually
    custom_message: str | None = None

    @property
    def resolved_send_method(self) -> str:
        if self.send_method is not None:
            return self.send_method
        return "email" if self.send_email else "manual"


# ============================================================================
# Settings Schemas
# ============================================================================


class BillingSettingsResponse(BaseModel):
    """Schema for clinic billing settings."""

    default_payment_term_days: int
    invoice_footer_text: str | None
    bank_account_info: str | None


class BillingSettingsUpdate(BaseModel):
    """Schema for updating clinic billing settings."""

    default_payment_term_days: int | None = Field(default=None, ge=0, le=365)
    invoice_footer_text: str | None = None
    bank_account_info: str | None = None


# ============================================================================
# Search/Filter Schemas
# ============================================================================


class PatientBillingSummary(BaseModel):
    """Schema for patient billing summary in profile."""

    patient_id: UUID

    # Budget metrics
    total_budgeted: Decimal
    total_discount: Decimal = Decimal("0.00")
    work_in_progress: Decimal
    work_completed: Decimal

    # Invoice metrics
    total_invoiced: Decimal
    total_paid: Decimal
    balance_pending: Decimal


class InvoiceSearchParams(BaseModel):
    """Search parameters for invoices."""

    patient_id: UUID | None = None
    status: list[InvoiceStatus] | None = None
    date_from: date | None = None
    date_to: date | None = None
    due_from: date | None = None
    due_to: date | None = None
    overdue: bool | None = None
    search: str | None = None  # invoice_number or patient name
    budget_id: UUID | None = None
    is_credit_note: bool | None = None
