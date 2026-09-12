"""Thin Razorpay REST client.

Pattern mirrors ``whatsapp_kapso/client.py`` / ``verifactu/services/aeat_client.py``:
one ``httpx.AsyncClient`` call per request with a timeout, mapping
transport/4xx/5xx errors to a single ``RazorpayError``. No SDK
dependency — Razorpay's API is plain REST with HTTP Basic Auth
(``key_id:key_secret``), which httpx already supports natively.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import httpx

from .constants import RAZORPAY_API_BASE

_TIMEOUT = 30.0


class RazorpayError(Exception):
    """Any failure talking to Razorpay (transport error or non-2xx response)."""


def to_paise(amount: Decimal) -> int:
    """Razorpay amounts are integers in the smallest currency unit
    (paise for INR). Always round via Decimal, never float."""
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_paise(paise: int) -> Decimal:
    return (Decimal(paise) / Decimal(100)).quantize(Decimal("0.01"))


async def _request(
    method: str, key_id: str, key_secret: str, path: str, *, json: dict | None = None
) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http_client:
            resp = await http_client.request(
                method,
                f"{RAZORPAY_API_BASE}{path}",
                auth=(key_id, key_secret),
                json=json,
            )
    except httpx.HTTPError as exc:
        raise RazorpayError(f"HTTP error talking to Razorpay: {exc}") from exc
    if resp.status_code >= 400:
        raise RazorpayError(f"Razorpay returned HTTP {resp.status_code}: {resp.text[:500]}")
    return resp.json()


async def create_order(
    key_id: str,
    key_secret: str,
    *,
    amount: Decimal,
    currency: str,
    receipt: str,
    notes: dict | None = None,
) -> dict:
    """Order object backing the UPI-intent / card Checkout.js flow."""
    return await _request(
        "POST",
        key_id,
        key_secret,
        "/orders",
        json={
            "amount": to_paise(amount),
            "currency": currency,
            "receipt": receipt[:40],
            "payment_capture": 1,  # auto-capture — no manual authorize-then-capture step in v1
            "notes": notes or {},
        },
    )


async def fetch_order(key_id: str, key_secret: str, order_id: str) -> dict:
    return await _request("GET", key_id, key_secret, f"/orders/{order_id}")


async def list_order_payments(key_id: str, key_secret: str, order_id: str) -> list[dict]:
    data = await _request("GET", key_id, key_secret, f"/orders/{order_id}/payments")
    return data.get("items", [])


async def fetch_payment_link(key_id: str, key_secret: str, payment_link_id: str) -> dict:
    return await _request("GET", key_id, key_secret, f"/payment_links/{payment_link_id}")


async def list_qr_code_payments(key_id: str, key_secret: str, qr_code_id: str) -> list[dict]:
    data = await _request("GET", key_id, key_secret, f"/payments/qr_codes/{qr_code_id}/payments")
    return data.get("items", [])


async def fetch_payment(key_id: str, key_secret: str, payment_id: str) -> dict:
    return await _request("GET", key_id, key_secret, f"/payments/{payment_id}")


async def create_qr_code(
    key_id: str,
    key_secret: str,
    *,
    amount: Decimal,
    description: str,
    reference_id: str,
    close_by_epoch: int | None = None,
) -> dict:
    payload: dict = {
        "type": "upi_qr",
        "name": description[:100],
        "usage": "single_use",
        "fixed_amount": True,
        "payment_amount": to_paise(amount),
        "description": description[:255],
        "notes": {"reference_id": reference_id},
    }
    if close_by_epoch is not None:
        payload["close_by"] = close_by_epoch
    return await _request("POST", key_id, key_secret, "/payments/qr_codes", json=payload)


async def close_qr_code(key_id: str, key_secret: str, qr_code_id: str) -> dict:
    return await _request("POST", key_id, key_secret, f"/payments/qr_codes/{qr_code_id}/close")


async def create_payment_link(
    key_id: str,
    key_secret: str,
    *,
    amount: Decimal,
    currency: str,
    description: str,
    reference_id: str,
    customer: dict | None = None,
    expire_by_epoch: int | None = None,
) -> dict:
    payload: dict = {
        "amount": to_paise(amount),
        "currency": currency,
        "description": description[:255],
        "reference_id": reference_id[:40],
        "notify": {"sms": False, "email": False},  # this module never sends notifications (v1)
        "reminder_enable": False,
    }
    if customer:
        payload["customer"] = customer
    if expire_by_epoch is not None:
        payload["expire_by"] = expire_by_epoch
    return await _request("POST", key_id, key_secret, "/payment_links", json=payload)


async def cancel_payment_link(key_id: str, key_secret: str, payment_link_id: str) -> dict:
    return await _request("POST", key_id, key_secret, f"/payment_links/{payment_link_id}/cancel")


async def create_refund(
    key_id: str,
    key_secret: str,
    *,
    payment_id: str,
    amount: Decimal,
    receipt: str,
    notes: dict | None = None,
) -> dict:
    return await _request(
        "POST",
        key_id,
        key_secret,
        f"/payments/{payment_id}/refund",
        json={
            "amount": to_paise(amount),
            "receipt": receipt[:40],
            "notes": notes or {},
            "speed": "normal",
        },
    )


async def fetch_refund(key_id: str, key_secret: str, payment_id: str, refund_id: str) -> dict:
    return await _request("GET", key_id, key_secret, f"/payments/{payment_id}/refunds/{refund_id}")
