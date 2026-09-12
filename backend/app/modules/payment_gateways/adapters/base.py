"""Gateway adapter contract — the public surface vendor modules import.

A *gateway* is a way of collecting money electronically (Razorpay today;
PhonePe/Stripe later). ``payment_gateways`` owns the ``PaymentRequest``
lifecycle, the registry, and — once a provider confirms a payment — the
call into ``payments.workflow.record_payment``. An *adapter* only knows
how to talk to one provider's API: build a checkout, verify a webhook
signature, turn a payload into a neutral event, and call the refund
endpoint. No business logic (allocation, Payment/Refund creation)
belongs in an adapter.

Request/response types are named around neutral concepts — provider
key, provider reference, checkout payload, QR payload, webhook event,
refund request/result — not Razorpay vocabulary, so a PhonePe or Stripe
adapter can implement this same contract unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..models import GatewayRefundRequest, PaymentRequest

# What a webhook event turned out to mean, in provider-neutral terms.
WebhookEventType = Literal[
    "payment_succeeded",
    "payment_failed",
    "payment_authorized",  # authorised, awaiting a separate capture step
    "payment_expired",
    "payment_cancelled",
    "refund_processing",
    "refund_completed",
    "refund_failed",
    "unrecognized",  # a real event this adapter doesn't act on (accept-and-ignore)
]


@dataclass
class GatewayCustomerInfo:
    """Optional contact info for checkout prefill / receipts.

    Never persisted by ``payment_gateways`` beyond the lifetime of one
    ``initiate_payment`` call — the adapter uses it to prefill the
    provider's checkout UI (e.g. Razorpay's ``prefill.contact``); the
    patient's own record stays the source of truth.
    """

    name: str | None = None
    email: str | None = None
    phone: str | None = None


@dataclass
class GatewayCheckoutResult:
    """What the adapter hands back after starting a payment attempt."""

    provider_reference: str  # provider's own order/QR/link id
    method: str  # echoes the requested rail: upi | qr | card | payment_link
    redirect_url: str | None = None
    # Opaque payload the frontend hands to the provider's own checkout
    # SDK (e.g. Razorpay Checkout.js options) — never inspected by
    # ``payment_gateways`` beyond passing it through to the client.
    checkout_payload: dict | None = None
    qr_image_url: str | None = None
    qr_payload: str | None = None  # raw UPI-intent string, for a self-rendered QR
    expires_at: datetime | None = None
    raw_provider_status: str | None = None


@dataclass
class GatewayConfirmation:
    """The provider's account of one successfully captured payment."""

    provider_payment_reference: str
    # The instrument the customer actually used (upi | card | netbanking |
    # wallet | ...) — always read from the provider's own report, never
    # assumed from the requested rail (a "UPI intent" checkout can be
    # completed with a saved card).
    confirmed_method: str
    amount: Decimal
    currency: str
    captured_at: datetime


@dataclass
class GatewayStatusResult:
    """Result of an on-demand status check (manual refresh / reconciliation).

    Distinct from the webhook path — this is a pull, used when the UI
    wants to refresh a stuck ``awaiting_customer_action`` request rather
    than wait for the next webhook retry.
    """

    state: str  # a payment_gateways.constants.PaymentRequestState value
    confirmation: GatewayConfirmation | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class GatewayWebhookEvent:
    """A verified webhook payload, normalized to neutral concepts.

    Exactly one of the two reference fields is populated, matching
    which table the router must look the row up in:

    - ``payment_*`` event types populate ``provider_reference`` — the
      *request*-level id (order/QR/link id) that
      ``PaymentRequest.provider_reference`` was stored under at
      ``initiate_payment`` time.
    - ``refund_*`` event types populate ``refund_provider_reference`` —
      the id that ``GatewayRefundRequest.provider_refund_reference``
      was stored under at ``initiate_refund`` time.

    ``provider_event_id`` is the provider's own webhook/event id, used
    as an additional idempotency key alongside our own dedup on
    ``provider_payment_reference`` / ``provider_refund_reference``.
    """

    event_type: WebhookEventType
    provider_reference: str | None = None
    provider_event_id: str | None = None
    confirmation: GatewayConfirmation | None = None
    error_code: str | None = None
    error_message: str | None = None
    # refund_* fields populated for refund_processing/completed/failed.
    refund_provider_reference: str | None = None
    refund_amount: Decimal | None = None


@dataclass
class GatewayRefundInitResult:
    """Result of asking the provider to start a refund.

    Some providers resolve a refund synchronously in the API response
    (``state="completed"`` here); others only acknowledge receipt and
    report completion via webhook later (``state="processing"``) — the
    caller (``GatewayRefundService``) branches on this, never assumes
    either way.
    """

    provider_refund_reference: str | None
    state: str  # a payment_gateways.constants.GatewayRefundState value
    error_code: str | None = None
    error_message: str | None = None


@dataclass
class GatewayRefundStatusResult:
    state: str  # a payment_gateways.constants.GatewayRefundState value
    error_code: str | None = None
    error_message: str | None = None


@runtime_checkable
class GatewayAdapter(Protocol):
    """What a provider module must implement to offer a gateway.

    Adapters are stateless and registered process-wide; per-clinic
    activation is decided by :meth:`supports` (reads the clinic's own
    config table), never by the adapter's mere presence — mirrors
    ``notifications.channels.ChannelAdapter``.
    """

    provider_key: str  # unique, e.g. "razorpay"
    supported_methods: tuple[str, ...]  # subset of constants.GATEWAY_METHODS

    async def supports(self, db: AsyncSession, clinic_id: UUID) -> bool:
        """Is this provider configured and active for the clinic?"""
        ...

    async def initiate_payment(
        self,
        db: AsyncSession,
        *,
        request: PaymentRequest,
        customer: GatewayCustomerInfo,
    ) -> GatewayCheckoutResult:
        """Start a payment attempt at the provider for an already-created,
        still-``pending`` ``PaymentRequest``. Must not raise for ordinary
        provider-side rejections — surface those via a failed result the
        caller can present, reserving exceptions for transport/programmer
        errors."""
        ...

    async def verify_payment_status(
        self, db: AsyncSession, *, request: PaymentRequest
    ) -> GatewayStatusResult:
        """On-demand status pull — manual refresh, never the primary
        confirmation path (that's the webhook)."""
        ...

    def verify_webhook_signature(
        self, *, raw_body: bytes, headers: dict[str, str], secret: str
    ) -> bool:
        """Pure, synchronous signature check — no I/O, no DB."""
        ...

    async def parse_webhook_event(
        self, db: AsyncSession, *, clinic_id: UUID, payload: dict
    ) -> GatewayWebhookEvent | None:
        """Turn an already signature-verified payload into a neutral event.
        Return ``None`` for payloads this adapter has nothing to do with
        (accept-and-ignore, never an error)."""
        ...

    async def initiate_refund(
        self, db: AsyncSession, *, refund_request: GatewayRefundRequest
    ) -> GatewayRefundInitResult:
        """Ask the provider to refund an already-captured payment."""
        ...

    async def refresh_refund_status(
        self, db: AsyncSession, *, refund_request: GatewayRefundRequest
    ) -> GatewayRefundStatusResult:
        """On-demand refund status pull, for providers whose refund is
        asynchronous and whose webhook delivery cannot be relied on
        exclusively."""
        ...
