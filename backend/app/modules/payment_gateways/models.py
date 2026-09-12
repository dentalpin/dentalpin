"""payment_gateways database models.

Tables:

* ``payment_requests`` — the pre-payment async lifecycle of one attempt
  to collect money through a gateway. Never a source of financial
  truth by itself: it becomes one only once it links to a real
  ``payments.Payment`` row (``payment_id``, set exactly once, at
  confirmation).
* ``gateway_refund_requests`` — the async lifecycle of one gateway
  refund attempt. Links to a real ``payments.Refund`` row
  (``refund_id``) only once the provider reports completion.

Neither table duplicates anything already on ``payments.Payment`` /
``payments.Refund`` (no provider name, no status, no fees) — this
module is the *only* place that knows a given ``Payment`` was
collected through a gateway at all.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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
    from app.modules.patients.models import Patient


class PaymentRequest(Base, TimestampMixin):
    """One attempt to collect money through a gateway.

    ``allocation_input`` and ``context`` are stored verbatim so
    confirmation can call ``payments.workflow.record_payment`` with
    exactly what the user chose at collection time — this module
    never re-derives an allocation from scratch after the fact.
    """

    __tablename__ = "payment_requests"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)

    provider_key: Mapped[str] = mapped_column(String(50))
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    requested_method: Mapped[str] = mapped_column(String(20))  # upi | qr | card | payment_link

    state: Mapped[str] = mapped_column(String(30), default="pending", index=True)

    # [{target_type, target_id, amount}, ...] — same shape
    # ``payments.workflow.record_payment(allocations=...)`` accepts.
    allocation_input: Mapped[list] = mapped_column(JSONB, default=list)
    # Opaque, echoed into ``record_payment(context=...)`` — e.g.
    # ``{"prefer_invoice_id": "..."}`` when collection started from a
    # specific invoice. This module never reads it.
    context: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Caller-supplied (or server-generated) idempotency key for the
    # *initiate* call — a retried "collect" click must not open a
    # second provider order for the same attempt.
    idempotency_key: Mapped[str] = mapped_column(String(100))

    # Provider's own order/QR/payment-link id, assigned at initiate time.
    provider_reference: Mapped[str | None] = mapped_column(String(100), default=None)
    # Provider's own *payment* id, assigned only once a customer
    # actually pays — the field a duplicate webhook dedups against.
    provider_payment_reference: Mapped[str | None] = mapped_column(String(100), default=None)
    # What we handed the frontend to render checkout (redirect URL / SDK
    # payload / QR image or payload) — none of it secret (a Razorpay
    # order id and public key_id are meant for the browser), stored so a
    # page refresh mid-checkout can re-fetch and re-render via GET
    # instead of only working from the initial POST response.
    checkout_payload_snapshot: Mapped[dict | None] = mapped_column(JSONB, default=None)
    # Non-secret snapshot of the last status payload seen (webhook or
    # poll) — audit trail, never provider secrets.
    raw_status_snapshot: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # Set exactly once, atomically with the state -> succeeded
    # transition (see service.PaymentRequestService.confirm).
    payment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), default=None, index=True
    )

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_code: Mapped[str | None] = mapped_column(String(50), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    clinic: Mapped[Clinic] = relationship(foreign_keys=[clinic_id])
    patient: Mapped[Patient] = relationship()
    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    refund_requests: Mapped[list[GatewayRefundRequest]] = relationship(
        back_populates="payment_request",
        order_by="GatewayRefundRequest.created_at.desc()",
    )

    __table_args__ = (
        CheckConstraint("requested_amount > 0", name="ck_payment_requests_amount_positive"),
        UniqueConstraint(
            "clinic_id", "idempotency_key", name="uq_payment_requests_clinic_idempotency"
        ),
        Index("idx_payment_requests_clinic_patient", "clinic_id", "patient_id"),
        Index("idx_payment_requests_clinic_state", "clinic_id", "state"),
        # Provider reference is unique per provider once assigned.
        Index(
            "uq_payment_requests_provider_reference",
            "provider_key",
            "provider_reference",
            unique=True,
            postgresql_where=text("provider_reference IS NOT NULL"),
        ),
        # The hard idempotency backstop: two rows can never claim the
        # same provider payment id. The primary dedup guard is the
        # service-layer "already succeeded" no-op check under a row
        # lock (see service.PaymentRequestService.confirm); this index
        # is defense-in-depth against a bug or a genuine race bypassing
        # that lock.
        Index(
            "uq_payment_requests_provider_payment_reference",
            "provider_key",
            "provider_payment_reference",
            unique=True,
            postgresql_where=text("provider_payment_reference IS NOT NULL"),
        ),
    )


class GatewayRefundRequest(Base, TimestampMixin):
    """One attempt to refund a gateway-collected payment.

    ``payment_id`` is the core ``payments.Payment`` being refunded;
    ``refund_id`` links to the core ``payments.Refund`` row that
    :class:`GatewayRefundService` creates only once the provider
    reports the refund as completed — never before.
    """

    __tablename__ = "gateway_refund_requests"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), index=True
    )
    payment_request_id: Mapped[UUID] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="RESTRICT"), index=True
    )

    provider_key: Mapped[str] = mapped_column(String(50))
    # Copied from ``payment_request.provider_payment_reference`` at
    # creation time — the adapter needs the *original* provider payment
    # id to call the refund endpoint, and duplicating it here means
    # ``initiate_refund`` never has to lazy-load the ``payment_request``
    # relationship in an async context.
    provider_payment_reference: Mapped[str] = mapped_column(String(100))
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Reuses payments.REFUND_REASON_CODES vocabulary — never a new one.
    reason_code: Mapped[str] = mapped_column(String(30))
    reason_note: Mapped[str | None] = mapped_column(Text, default=None)

    state: Mapped[str] = mapped_column(String(20), default="requested", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    provider_refund_reference: Mapped[str | None] = mapped_column(String(100), default=None)
    raw_status_snapshot: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # Set exactly once, atomically with the state -> completed transition.
    refund_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("refunds.id", ondelete="RESTRICT"), default=None, index=True
    )

    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_code: Mapped[str | None] = mapped_column(String(50), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    clinic: Mapped[Clinic] = relationship(foreign_keys=[clinic_id])
    requester: Mapped[User] = relationship(foreign_keys=[requested_by])
    payment_request: Mapped[PaymentRequest] = relationship(back_populates="refund_requests")

    __table_args__ = (
        CheckConstraint("requested_amount > 0", name="ck_gateway_refunds_amount_positive"),
        UniqueConstraint(
            "clinic_id", "idempotency_key", name="uq_gateway_refunds_clinic_idempotency"
        ),
        Index("idx_gateway_refunds_clinic_payment", "clinic_id", "payment_id"),
        Index(
            "uq_gateway_refunds_provider_reference",
            "provider_key",
            "provider_refund_reference",
            unique=True,
            postgresql_where=text("provider_refund_reference IS NOT NULL"),
        ),
    )
