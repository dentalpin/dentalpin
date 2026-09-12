"""Razorpay-specific constants — provider vocabulary never leaks past
this module (``payment_gateways`` and core ``payments`` never see it)."""

from __future__ import annotations

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"

# Checkout flows this adapter offers. Subset of
# payment_gateways.constants.GATEWAY_METHODS.
SUPPORTED_METHODS = ("upi", "qr", "card", "payment_link")

MODES = ("test", "live")

# Razorpay's own `payment.entity.method` values -> our core
# payments.PAYMENT_METHODS vocabulary. Always read from what Razorpay
# reports as *actually used*, never assumed from the checkout flow the
# customer started (a "UPI intent" checkout can be completed with a
# saved card). Anything not listed here (rare/future Razorpay methods)
# falls back to "other" rather than raising.
RAZORPAY_METHOD_MAP: dict[str, str] = {
    "upi": "upi",
    "card": "card",
    "netbanking": "netbanking",
    "wallet": "other",
    "emi": "card",
    "paylater": "other",
}


def map_provider_method(razorpay_method: str | None) -> str:
    return RAZORPAY_METHOD_MAP.get(razorpay_method or "", "other")


# Razorpay payment.entity.status values we act on.
RAZORPAY_PAYMENT_CAPTURED = "captured"
RAZORPAY_PAYMENT_AUTHORIZED = "authorized"
RAZORPAY_PAYMENT_FAILED = "failed"

# Razorpay webhook event names this adapter recognizes. Anything else
# is accepted-and-ignored (see adapter.parse_webhook_event).
EVENT_PAYMENT_CAPTURED = "payment.captured"
EVENT_PAYMENT_FAILED = "payment.failed"
EVENT_PAYMENT_AUTHORIZED = "payment.authorized"
EVENT_ORDER_PAID = "order.paid"
EVENT_REFUND_PROCESSED = "refund.processed"
EVENT_REFUND_FAILED = "refund.failed"
EVENT_PAYMENT_LINK_PAID = "payment_link.paid"
EVENT_PAYMENT_LINK_EXPIRED = "payment_link.expired"
EVENT_PAYMENT_LINK_CANCELLED = "payment_link.cancelled"
EVENT_QR_CODE_CREDITED = "qr_code.credited"
