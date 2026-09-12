"""payment_gateways Pydantic schemas.

Allocation input reuses ``payments.schemas.AllocationCreate`` verbatim
— this module never re-validates the budget/on_account vocabulary
independently of the module that owns it.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.payments.schemas import AllocationCreate, PaymentMethod, RefundReason

from .constants import GATEWAY_METHODS

GatewayMethod = str  # validated against GATEWAY_METHODS in the router/service, not a Literal,
# so a future provider can register a rail this module doesn't know about yet.


class PaymentRequestCreate(BaseModel):
    patient_id: UUID
    provider_key: str = Field(min_length=1, max_length=50)
    amount: Decimal = Field(gt=0)
    method: str = Field(min_length=1, max_length=20)
    allocations: list[AllocationCreate] = Field(min_length=1)
    context: dict | None = None
    idempotency_key: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _check_allocation_sum(self) -> PaymentRequestCreate:
        allocated = sum(a.amount for a in self.allocations)
        if allocated != self.amount:
            raise ValueError(f"Allocations must sum to amount ({self.amount}); got {allocated}")
        return self

    @model_validator(mode="after")
    def _check_method(self) -> PaymentRequestCreate:
        if self.method not in GATEWAY_METHODS:
            raise ValueError(
                f"Unsupported method {self.method!r}; expected one of {GATEWAY_METHODS}"
            )
        return self


class CheckoutInfo(BaseModel):
    redirect_url: str | None = None
    checkout_payload: dict | None = None
    qr_image_url: str | None = None
    qr_payload: str | None = None


class PaymentRequestResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    provider_key: str
    requested_amount: Decimal
    currency: str
    requested_method: str
    state: str
    provider_reference: str | None = None
    provider_payment_reference: str | None = None
    checkout: CheckoutInfo | None = None
    expires_at: datetime | None = None
    confirmed_at: datetime | None = None
    failed_at: datetime | None = None
    cancelled_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    payment_id: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, request) -> PaymentRequestResponse:
        snap = request.checkout_payload_snapshot or {}
        return cls(
            id=request.id,
            clinic_id=request.clinic_id,
            patient_id=request.patient_id,
            provider_key=request.provider_key,
            requested_amount=request.requested_amount,
            currency=request.currency,
            requested_method=request.requested_method,
            state=request.state,
            provider_reference=request.provider_reference,
            provider_payment_reference=request.provider_payment_reference,
            checkout=CheckoutInfo(**snap) if snap else None,
            expires_at=request.expires_at,
            confirmed_at=request.confirmed_at,
            failed_at=request.failed_at,
            cancelled_at=request.cancelled_at,
            error_code=request.error_code,
            error_message=request.error_message,
            payment_id=request.payment_id,
            created_at=request.created_at,
        )


class GatewayRefundRequestCreate(BaseModel):
    payment_id: UUID
    amount: Decimal = Field(gt=0)
    method: PaymentMethod | None = None  # unused by gateway refunds; accepted for UI symmetry
    reason_code: RefundReason
    reason_note: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=100)


class GatewayRefundRequestResponse(BaseModel):
    id: UUID
    payment_id: UUID
    payment_request_id: UUID
    provider_key: str
    requested_amount: Decimal
    reason_code: str
    reason_note: str | None = None
    state: str
    provider_refund_reference: str | None = None
    refund_id: UUID | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GatewayInfoResponse(BaseModel):
    """Powers the transaction-detail panel: which provider collected
    this payment, its checkout/settlement trail, and its refund
    history — or ``None`` fields throughout when the payment was not
    gateway-collected (the frontend renders nothing in that case)."""

    request: PaymentRequestResponse | None = None
    refund_requests: list[GatewayRefundRequestResponse] = []
