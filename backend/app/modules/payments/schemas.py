"""Payments module Pydantic schemas for API request/response."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PaymentMethod = Literal["cash", "card", "bank_transfer", "direct_debit", "insurance", "razorpay", "other"]
AllocationTarget = Literal["budget", "on_account"]
RefundReason = Literal["duplicate", "overpaid", "treatment_cancelled", "dispute", "other"]


# --- Briefs ---------------------------------------------------------------


class UserBrief(BaseModel):
    id: UUID
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)


class PatientBrief(BaseModel):
    id: UUID
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)


# --- Allocation ----------------------------------------------------------


class AllocationCreate(BaseModel):
    target_type: AllocationTarget
    target_id: UUID | None = None  # required iff target_type == 'budget'
    amount: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def _check_target_id(self) -> "AllocationCreate":
        if self.target_type == "budget" and self.target_id is None:
            raise ValueError("target_id is required when target_type='budget'")
        if self.target_type == "on_account" and self.target_id is not None:
            raise ValueError("target_id must be null when target_type='on_account'")
        return self


class AllocationResponse(BaseModel):
    id: UUID
    target_type: str
    target_id: UUID | None = None
    amount: Decimal
    created_at: datetime
    created_by: UUID
    method: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, alloc) -> "AllocationResponse":
        return cls(
            id=alloc.id,
            target_type=alloc.target_type,
            target_id=alloc.budget_id if alloc.target_type == "budget" else None,
            amount=alloc.amount,
            created_at=alloc.created_at,
            created_by=alloc.created_by,
            method=alloc.payment.method if alloc.payment else None,
        )


# --- Payment -------------------------------------------------------------


class PaymentCreate(BaseModel):
    patient_id: UUID
    amount: Decimal = Field(gt=0)
    method: PaymentMethod
    payment_date: date = Field(default_factory=date.today)
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    allocations: list[AllocationCreate] = Field(min_length=1)

    @field_validator("reference", "notes", mode="before")
    @classmethod
    def _empty_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _check_allocation_sum(self) -> "PaymentCreate":
        allocated = sum(a.amount for a in self.allocations)
        if allocated != self.amount:
            raise ValueError(f"Allocations must sum to amount ({self.amount}); got {allocated}")
        return self


class PaymentReallocate(BaseModel):
    allocations: list[AllocationCreate] = Field(min_length=1)


# --- Razorpay ----------------------------------------------------------


class RazorpayOrderCreate(BaseModel):
    patient_id: UUID
    amount: Decimal = Field(gt=0)
    currency: str = "INR"  # Razorpay is an INR gateway


class RazorpayOrderResponse(BaseModel):
    order_id: str
    amount: int  # paise, per Razorpay convention
    currency: str
    key_id: str


class RazorpayVerifyCreate(BaseModel):
    """Server-side signature verification payload (sent by the client in
    the Razorpay checkout ``handler`` callback)."""

    patient_id: UUID
    amount: Decimal = Field(gt=0)
    payment_date: date = Field(default_factory=date.today)
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
    allocations: list[AllocationCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_allocation_sum(self) -> "RazorpayVerifyCreate":
        allocated = sum(a.amount for a in self.allocations)
        if allocated != self.amount:
            raise ValueError(f"Allocations must sum to amount ({self.amount}); got {allocated}")
        return self


class PaymentResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    amount: Decimal
    currency: str
    method: str
    payment_date: date
    reference: str | None = None
    notes: str | None = None
    recorded_by: UUID
    created_at: datetime
    updated_at: datetime

    allocations: list[AllocationResponse] = []
    refunded_total: Decimal = Decimal("0")  # Σ refund amounts (cached)
    net_amount: Decimal = Decimal("0")  # amount - refunded_total
    recorder: UserBrief | None = None
    patient: PatientBrief | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, payment) -> "PaymentResponse":
        refunded = sum((r.amount for r in (payment.refunds or [])), Decimal("0"))
        return cls(
            id=payment.id,
            clinic_id=payment.clinic_id,
            patient_id=payment.patient_id,
            amount=payment.amount,
            currency=payment.currency,
            method=payment.method,
            payment_date=payment.payment_date,
            reference=payment.reference,
            notes=payment.notes,
            recorded_by=payment.recorded_by,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
            allocations=[AllocationResponse.from_model(a) for a in payment.allocations],
            refunded_total=refunded,
            net_amount=payment.amount - refunded,
            recorder=UserBrief.model_validate(payment.recorder) if payment.recorder else None,
            patient=PatientBrief.model_validate(payment.patient) if payment.patient else None,
        )


# --- Refund --------------------------------------------------------------


class RefundCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    method: PaymentMethod
    reason_code: RefundReason
    reason_note: str | None = None

    @field_validator("reason_note", mode="before")
    @classmethod
    def _empty_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class RefundResponse(BaseModel):
    id: UUID
    payment_id: UUID
    amount: Decimal
    method: str
    reason_code: str
    reason_note: str | None = None
    refunded_at: datetime
    refunded_by: UUID
    refunder: UserBrief | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Ledger --------------------------------------------------------------


class LedgerEntry(BaseModel):
    """A single row in the patient timeline (payment, refund, earned).

    For ``earned`` entries we additionally surface the linked
    treatment's catalog name, lifecycle status and performing
    professional. The clinical context lives on different tables
    (``odontogram.treatments`` ↔ ``catalog.treatment_catalog_items``
    ↔ ``auth.users``), so the timeline aggregator joins them once
    rather than letting the UI fan out a request per row.
    """

    entry_type: Literal["payment", "refund", "earned"]
    occurred_at: datetime
    amount: Decimal  # positive for payment/earned, negative for refund
    reference_id: UUID
    description: str | None = None

    # Earned-only enrichment. None for payment/refund rows.
    treatment_id: UUID | None = None
    treatment_name: str | None = None
    treatment_status: str | None = None  # planned | performed | …
    professional_id: UUID | None = None
    professional_name: str | None = None


class PatientLedger(BaseModel):
    patient_id: UUID
    currency: str
    total_paid: Decimal  # Σ payments − Σ refunds
    total_earned: Decimal  # Σ earned entries
    patient_credit: Decimal  # max(0, total_paid − total_earned)
    clinic_receivable: Decimal  # max(0, total_earned − total_paid)
    on_account_balance: Decimal  # Σ on_account allocations not yet reassigned
    timeline: list[LedgerEntry] = []


# --- Reports -------------------------------------------------------------


class PaymentsSummary(BaseModel):
    period_start: date
    period_end: date
    currency: str
    total_collected: Decimal
    total_refunded: Decimal
    net_collected: Decimal
    patient_credit_total: Decimal
    clinic_receivable_total: Decimal
    refund_ratio: float
    payment_count: int
    refund_count: int


class MethodBreakdown(BaseModel):
    method: str
    total: Decimal
    count: int


class ProfessionalBreakdown(BaseModel):
    professional_id: UUID | None = None
    professional_name: str | None = None
    total_earned: Decimal
    count: int


class AgingBucket(BaseModel):
    label: str  # "0-30", "31-60", "61-90", "90+"
    total: Decimal
    patient_count: int


class AgingBuckets(BaseModel):
    currency: str
    buckets: list[AgingBucket]


class RefundsReport(BaseModel):
    period_start: date
    period_end: date
    currency: str
    total_refunded: Decimal
    refund_ratio: float
    by_reason: list[dict]  # {reason_code, total, count}
    by_method: list[MethodBreakdown]


class TrendPoint(BaseModel):
    bucket_start: date
    collected: Decimal
    refunded: Decimal
    net: Decimal


class PaymentsTrends(BaseModel):
    granularity: Literal["day", "week", "month", "year"]
    currency: str
    points: list[TrendPoint]


# --- Cross-module summary + filter endpoints ------------------------------
#
# These power the `/patients` and `/budgets` list pages without forcing
# those modules to depend on payments. See
# `docs/technical/payments/cross-module-summaries.md` for the contract
# and the off-books invariants the reviewer must verify.


BudgetPaymentStatus = Literal["unpaid", "partial", "paid"]


class BudgetSummaryByIds(BaseModel):
    """Per-budget payment summary (cell rendering on /budgets)."""

    collected: Decimal
    pending: Decimal
    payment_status: BudgetPaymentStatus


class BudgetSummariesByIds(BaseModel):
    summaries: dict[UUID, BudgetSummaryByIds]


class PatientSummaryByIds(BaseModel):
    """Per-patient summary (cell rendering on /patients).

    ``debt`` is computed strictly from ``earned − net_paid`` — pure
    payments axis. Never compared to invoiced totals.
    """

    total_paid: Decimal
    debt: Decimal
    on_account_balance: Decimal


class PatientSummariesByIds(BaseModel):
    summaries: dict[UUID, PatientSummaryByIds]


class BudgetIdsRequest(BaseModel):
    budget_ids: list[UUID] = Field(min_length=1, max_length=100)


class PatientIdsRequest(BaseModel):
    patient_ids: list[UUID] = Field(min_length=1, max_length=100)


class FilterIdsResponse(BaseModel):
    """Result of a cross-module filter resolution.

    Either ``budget_ids`` or ``patient_ids`` is populated depending on
    the endpoint. ``truncated`` is True when the candidate set exceeded
    the cap and the frontend should surface a warning.
    """

    budget_ids: list[UUID] | None = None
    patient_ids: list[UUID] | None = None
    truncated: bool = False
