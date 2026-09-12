"""State machines for the provider-neutral gateway lifecycle.

Two independent state machines live here:

- ``PaymentRequestState`` — the pre-payment async lifecycle of one
  attempt to collect money through a gateway. Terminal states are
  ``succeeded``, ``failed``, ``expired``, ``cancelled``.
- ``GatewayRefundState`` — the async lifecycle of one gateway refund
  attempt. Terminal states are ``completed``, ``failed``.

Both are validated centrally (:func:`validate_payment_request_transition`,
:func:`validate_refund_transition`) so a provider adapter can never push
an invalid transition — e.g. resurrecting a ``succeeded`` request, or
completing a refund that was never ``requested``.
"""

from __future__ import annotations

from enum import StrEnum


class PaymentRequestState(StrEnum):
    PENDING = "pending"
    AWAITING_CUSTOMER_ACTION = "awaiting_customer_action"
    AUTHORISED_AWAITING_CAPTURE = "authorised_awaiting_capture"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


TERMINAL_REQUEST_STATES = frozenset(
    {
        PaymentRequestState.SUCCEEDED,
        PaymentRequestState.FAILED,
        PaymentRequestState.EXPIRED,
        PaymentRequestState.CANCELLED,
    }
)

# Explicit transition table. A state maps to the set of states it may
# move to next; anything not listed here is rejected.
_REQUEST_TRANSITIONS: dict[PaymentRequestState, frozenset[PaymentRequestState]] = {
    PaymentRequestState.PENDING: frozenset(
        {
            PaymentRequestState.AWAITING_CUSTOMER_ACTION,
            PaymentRequestState.AUTHORISED_AWAITING_CAPTURE,
            PaymentRequestState.SUCCEEDED,
            PaymentRequestState.FAILED,
            PaymentRequestState.EXPIRED,
            PaymentRequestState.CANCELLED,
        }
    ),
    PaymentRequestState.AWAITING_CUSTOMER_ACTION: frozenset(
        {
            PaymentRequestState.AUTHORISED_AWAITING_CAPTURE,
            PaymentRequestState.SUCCEEDED,
            PaymentRequestState.FAILED,
            PaymentRequestState.EXPIRED,
            PaymentRequestState.CANCELLED,
        }
    ),
    PaymentRequestState.AUTHORISED_AWAITING_CAPTURE: frozenset(
        {
            PaymentRequestState.SUCCEEDED,
            PaymentRequestState.FAILED,
            PaymentRequestState.EXPIRED,
            PaymentRequestState.CANCELLED,
        }
    ),
    # Terminal states: no outgoing transitions.
    PaymentRequestState.SUCCEEDED: frozenset(),
    PaymentRequestState.FAILED: frozenset(),
    PaymentRequestState.EXPIRED: frozenset(),
    PaymentRequestState.CANCELLED: frozenset(),
}


class PaymentRequestTransitionError(ValueError):
    """Raised when a caller attempts an illegal ``PaymentRequest`` transition."""


def validate_payment_request_transition(
    current: PaymentRequestState, target: PaymentRequestState
) -> None:
    """Raise :class:`PaymentRequestTransitionError` unless ``current -> target``
    is a legal move. Re-entering the same state is always rejected — callers
    (webhook retries) must check for that idempotency case themselves
    *before* calling this, since "already there" and "illegal jump" need
    different handling (no-op vs. hard error).
    """
    allowed = _REQUEST_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise PaymentRequestTransitionError(
            f"Cannot transition PaymentRequest from {current!r} to {target!r}"
        )


class GatewayRefundState(StrEnum):
    REQUESTED = "requested"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_REFUND_STATES = frozenset({GatewayRefundState.COMPLETED, GatewayRefundState.FAILED})

_REFUND_TRANSITIONS: dict[GatewayRefundState, frozenset[GatewayRefundState]] = {
    GatewayRefundState.REQUESTED: frozenset(
        {GatewayRefundState.PROCESSING, GatewayRefundState.COMPLETED, GatewayRefundState.FAILED}
    ),
    GatewayRefundState.PROCESSING: frozenset(
        {GatewayRefundState.COMPLETED, GatewayRefundState.FAILED}
    ),
    GatewayRefundState.COMPLETED: frozenset(),
    GatewayRefundState.FAILED: frozenset(),
}


class RefundTransitionError(ValueError):
    """Raised when a caller attempts an illegal ``GatewayRefundRequest`` transition."""


def validate_refund_transition(current: GatewayRefundState, target: GatewayRefundState) -> None:
    allowed = _REFUND_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise RefundTransitionError(
            f"Cannot transition GatewayRefundRequest from {current!r} to {target!r}"
        )


# Requested collection method/rail — a hint to the adapter about which
# checkout flow to start (which Razorpay API to call). This is NOT the
# same as the confirmed core ``payments.Payment.method`` — that is
# always derived from what the provider reports at confirmation time
# (see ``razorpay.constants.map_provider_method``), never from this hint,
# since a customer can complete a "UPI intent" checkout with a saved
# card and similar cross-overs.
GATEWAY_METHODS = ("upi", "qr", "card", "payment_link")

# Allocation targets a PaymentRequest may resolve to once confirmed —
# the exact vocabulary payments.PaymentAllocation already uses (never
# invented here).
ALLOCATION_TARGET_TYPES = ("budget", "on_account")
