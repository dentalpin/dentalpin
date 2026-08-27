"""Budget module Pydantic schemas for API request/response."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .pricing import allocate_global_discount, net_line_total

# ============================================================================
# Budget Status Types (Simplified)
# ============================================================================

BudgetStatus = Literal[
    "draft",  # Initial state, editable
    "sent",  # Sent to patient, awaiting response
    "accepted",  # Patient accepted, ready for treatment/invoicing
    "completed",  # All work done
    "rejected",  # Patient rejected (terminal)
    "expired",  # Validity period passed (terminal)
    "cancelled",  # Cancelled before acceptance (terminal)
]

DiscountType = Literal["percentage", "absolute"]

SignatureType = Literal["full_acceptance", "rejection"]

SignatureMethod = Literal["click_accept", "drawn", "external_provider"]

RelationshipToPatient = Literal["patient", "guardian", "representative"]


# ============================================================================
# Brief Schemas (for nested responses)
# ============================================================================


class PatientBrief(BaseModel):
    """Brief patient info for budget responses."""

    id: UUID
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserBrief(BaseModel):
    """Brief user info for budget responses."""

    id: UUID
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)


class CatalogItemBrief(BaseModel):
    """Brief catalog item info for budget items."""

    id: UUID
    internal_code: str
    names: dict[str, str]
    default_price: Decimal | None

    model_config = ConfigDict(from_attributes=True)


class VatTypeBrief(BaseModel):
    """Brief VAT type info for budget items."""

    id: UUID
    names: dict[str, str]
    rate: float

    model_config = ConfigDict(from_attributes=True)


class TreatmentPlanBrief(BaseModel):
    """Brief treatment plan info for budget responses."""

    id: UUID
    plan_number: str
    title: str | None
    status: str

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Budget Item Schemas
# ============================================================================


class BudgetItemCreate(BaseModel):
    """Schema for creating a budget item."""

    catalog_item_id: UUID
    quantity: int = Field(default=1, ge=1)

    # Optional overrides (if not provided, uses catalog defaults)
    unit_price: Decimal | None = Field(default=None, ge=0)

    # Line discount
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = Field(default=None, ge=0)

    # Dental specifics
    tooth_number: int | None = Field(default=None, ge=11, le=85)
    surfaces: list[str] | None = None  # ["M", "O", "D"]

    # Odontogram integration
    treatment_id: UUID | None = None

    # Display
    display_order: int = 0
    notes: str | None = None


class BudgetItemUpdate(BaseModel):
    """Schema for updating a budget item."""

    quantity: int | None = Field(default=None, ge=1)
    unit_price: Decimal | None = Field(default=None, ge=0)

    # Line discount
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = Field(default=None, ge=0)

    # Dental specifics
    tooth_number: int | None = Field(default=None, ge=11, le=85)
    surfaces: list[str] | None = None

    # Display
    display_order: int | None = None
    notes: str | None = None


class BudgetItemResponse(BaseModel):
    """Schema for budget item response."""

    id: UUID
    budget_id: UUID
    catalog_item_id: UUID

    # Pricing
    unit_price: Decimal
    quantity: int

    # Line discount
    discount_type: str | None
    discount_value: Decimal | None

    # VAT
    vat_type_id: UUID | None
    vat_rate: float

    # Calculated totals
    line_subtotal: Decimal
    line_discount: Decimal
    line_tax: Decimal
    line_total: Decimal
    # Ex-tax share of the budget's global discount for this line. Only
    # populated inside ``BudgetDetailResponse`` (needs the sibling lines);
    # standalone item responses report 0.
    global_discount_share: Decimal = Decimal("0.00")
    # VAT-inclusive price after line + global discount — what the patient
    # pays for this line. Populated like ``global_discount_share``;
    # standalone item responses report ``line_total``.
    net_line_total: Decimal = Decimal("0.00")

    # Dental specifics
    tooth_number: int | None
    surfaces: list[str] | None

    # Odontogram integration
    treatment_id: UUID | None

    # Billing tracking (for partial invoicing)
    invoiced_quantity: int

    # Display
    display_order: int
    notes: str | None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Related
    catalog_item: CatalogItemBrief | None = None
    vat_type: VatTypeBrief | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Budget Signature Schemas
# ============================================================================


class SignatureCreate(BaseModel):
    """Schema for creating a signature."""

    signed_by_name: str = Field(min_length=1, max_length=200)
    signed_by_email: str | None = None
    relationship_to_patient: RelationshipToPatient = "patient"

    # Signature data (for drawn signatures)
    signature_data: dict | None = None


class SignatureResponse(BaseModel):
    """Schema for signature response."""

    id: UUID
    budget_id: UUID
    signature_type: str
    signed_items: list[UUID] | None

    # Signer info
    signed_by_name: str
    signed_by_email: str | None
    relationship_to_patient: str

    # Method
    signature_method: str
    signature_data: dict | None

    # Audit
    ip_address: str | None
    signed_at: datetime

    # External provider
    external_signature_id: str | None
    external_provider: str | None

    # Integrity
    document_hash: str | None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SignatureMetaResponse(BaseModel):
    """Signature metadata without the raw PNG payload.

    Used by staff/public endpoints that surface "this budget has been
    signed" info without shipping the full signature_data blob.
    """

    id: UUID
    budget_id: UUID
    signature_type: str
    signed_by_name: str
    signed_by_email: str | None
    relationship_to_patient: str
    signature_method: str
    ip_address: str | None
    signed_at: datetime
    document_hash: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Budget History Schemas
# ============================================================================


class BudgetHistoryResponse(BaseModel):
    """Schema for budget history response."""

    id: UUID
    budget_id: UUID
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
# Budget Schemas
# ============================================================================


class BudgetCreate(BaseModel):
    """Schema for creating a budget."""

    patient_id: UUID

    # Validity
    valid_from: date = Field(default_factory=date.today)
    valid_until: date | None = None

    # Assignment
    assigned_professional_id: UUID | None = None

    # Global discount
    global_discount_type: DiscountType | None = None
    global_discount_value: Decimal | None = Field(default=None, ge=0)

    # Notes
    internal_notes: str | None = None
    patient_notes: str | None = None

    # Items (optional, can be added later)
    items: list[BudgetItemCreate] = Field(default_factory=list)


class BudgetUpdate(BaseModel):
    """Schema for updating a budget (only allowed in draft status)."""

    # Validity
    valid_from: date | None = None
    valid_until: date | None = None

    # Assignment
    assigned_professional_id: UUID | None = None

    # Global discount
    global_discount_type: DiscountType | None = None
    global_discount_value: Decimal | None = Field(default=None, ge=0)

    # Notes
    internal_notes: str | None = None
    patient_notes: str | None = None


class BudgetResponse(BaseModel):
    """Schema for budget response."""

    id: UUID
    clinic_id: UUID
    patient_id: UUID

    # Identification
    budget_number: str
    version: int
    parent_budget_id: UUID | None

    # Status
    status: str

    # Validity
    valid_from: date
    valid_until: date | None

    # Assignments
    created_by: UUID
    assigned_professional_id: UUID | None

    # Global discount
    global_discount_type: str | None
    global_discount_value: Decimal | None

    # Totals
    subtotal: Decimal
    total_discount: Decimal
    total_tax: Decimal
    total: Decimal

    # Notes
    internal_notes: str | None
    patient_notes: str | None

    # Insurance
    insurance_estimate: Decimal | None

    # Public-link token (ADR 0006). Generated at creation time; the
    # patient-facing URL is rendered client-side as
    # ``${origin}/p/budget/${public_token}``.
    public_token: UUID | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    # Related
    patient: PatientBrief | None = None
    creator: UserBrief | None = None
    assigned_professional: UserBrief | None = None

    model_config = ConfigDict(from_attributes=True)


class BudgetDetailResponse(BudgetResponse):
    """Schema for budget with full details including items."""

    items: list[BudgetItemResponse] = []
    signatures: list[SignatureResponse] = []
    treatment_plan: TreatmentPlanBrief | None = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _fill_global_discount_shares(self) -> "BudgetDetailResponse":
        shares = allocate_global_discount(
            self.global_discount_type, self.global_discount_value, self.items
        )
        for item, share in zip(self.items, shares, strict=True):
            item.global_discount_share = share
            item.net_line_total = net_line_total(item, share)
        return self


class BudgetListResponse(BaseModel):
    """Schema for budget list item (lighter than full response)."""

    id: UUID
    budget_number: str
    version: int
    status: str
    valid_from: date
    valid_until: date | None
    total: Decimal
    created_at: datetime
    # Denormalized plan number when the budget was generated from a
    # treatment plan (ADR 0003) — lets patient-side lists show the link.
    plan_number_snapshot: str | None = None

    # Related (brief)
    patient: PatientBrief | None = None
    creator: UserBrief | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Workflow Schemas
# ============================================================================


class BudgetSendRequest(BaseModel):
    """Schema for sending a budget to patient.

    ``send_method`` picks the wire: ``manual`` (printed/handed — no
    message), ``email`` or ``whatsapp`` (gateway send on that channel).
    The legacy ``send_email`` flag is honoured when ``send_method`` is
    omitted so older clients keep working.
    """

    send_method: Literal["manual", "email", "whatsapp"] | None = None
    send_email: bool = False  # legacy client flag
    custom_message: str | None = None

    @property
    def resolved_send_method(self) -> str:
        if self.send_method is not None:
            return self.send_method
        return "email" if self.send_email else "manual"


class BudgetAcceptRequest(BaseModel):
    """Schema for accepting a budget (full or partial)."""

    signature: SignatureCreate


class BudgetRejectRequest(BaseModel):
    """Schema for rejecting a budget."""

    reason: str | None = None
    signature: SignatureCreate | None = None


class BudgetCancelRequest(BaseModel):
    """Schema for cancelling a budget."""

    reason: str | None = None


# ============================================================================
# Version Schemas
# ============================================================================


class BudgetVersionResponse(BaseModel):
    """Schema for budget version in version history."""

    id: UUID
    version: int
    status: str
    total: Decimal
    created_at: datetime
    is_current: bool = False

    model_config = ConfigDict(from_attributes=True)


class BudgetVersionListResponse(BaseModel):
    """Schema for list of budget versions."""

    budget_number: str
    versions: list[BudgetVersionResponse]
    current_version: int


# ============================================================================
# Search/Filter Schemas
# ============================================================================


class BudgetSearchParams(BaseModel):
    """Search parameters for budgets."""

    patient_id: UUID | None = None
    status: list[BudgetStatus] | None = None
    created_by: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None
    expired: bool | None = None
    search: str | None = None  # budget_number or patient name
