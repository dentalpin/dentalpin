"""Razorpay gateway integration for the payments module.

Client-side loads ``checkout.js`` and opens the payment popup; the
backend is responsible for two security-sensitive steps that must never
happen in the browser:

1. Creating the Razorpay **Order** (needs the key secret).
2. Verifying the payment **signature** (needs the key secret) before a
   payment record is written — otherwise a caller could forge a payment
   by hand-crafting the checkout response.

Both endpoints live in ``router.py`` under ``/api/v1/payments/``.
Everything here is server-side; the key secret never leaves the backend.
"""

from __future__ import annotations

import hmac
import hashlib

from app.config import settings


class RazorpayNotConfigured(RuntimeError):
    """Raised when RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are unset."""


def _client():
    """Lazily construct the Razorpay client; raise if not configured.

    The import is deferred so a backend without the ``razorpay`` package
    (or without keys) can still boot — only the Razorpay endpoints need
    it.
    """
    key_id = settings.RAZORPAY_KEY_ID
    key_secret = settings.RAZORPAY_KEY_SECRET
    if not key_id or not key_secret:
        raise RazorpayNotConfigured(
            "Razorpay is not configured (set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)."
        )
    try:
        import razorpay  # local import: optional at boot time
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RazorpayNotConfigured("The 'razorpay' package is not installed.") from exc
    return razorpay.Client(auth=(key_id, key_secret))


def create_order(amount: float, currency: str) -> dict:
    """Create a Razorpay order. ``amount`` is in the major currency unit
    (e.g. rupees); Razorpay wants paise, so we convert with 2-decimal
    rounding."""
    client = _client()
    paise = int(round(amount * 100))
    order = client.order.create(
        {"amount": paise, "currency": currency, "payment_capture": 1}
    )
    return {
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
    }


def verify_signature(
    razorpay_payment_id: str,
    razorpay_order_id: str,
    razorpay_signature: str,
) -> bool:
    """Verify a Razorpay checkout signature (HMAC-SHA256 of
    ``order_id|payment_id`` signed with the key secret)."""
    key_secret = settings.RAZORPAY_KEY_SECRET
    if not key_secret:
        raise RazorpayNotConfigured(
            "Razorpay is not configured (set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)."
        )
    msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
    digest = hmac.new(key_secret.encode(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, razorpay_signature)
