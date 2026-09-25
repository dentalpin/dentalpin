"""Pure logic: amount conversion + provider-method mapping + payload
parsing. No network, no DB.

Webhook signature verification is tested in
``tests/modules/razorpay/test_settings.py`` against
``RazorpaySettingsService.verify_signature`` — the implementation the
webhook route actually calls. ``RazorpayAdapter`` doesn't implement
``verify_webhook_signature`` (see the comment in ``adapter.py``); it
would have been a second, unused copy of the same HMAC check.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.modules.razorpay.adapter import RazorpayAdapter
from app.modules.razorpay.client import from_paise, to_paise
from app.modules.razorpay.constants import map_provider_method


@pytest.mark.parametrize(
    "amount,expected_paise",
    [
        (Decimal("1.00"), 100),
        (Decimal("99.99"), 9999),
        (Decimal("0.01"), 1),
        (Decimal("1234.56"), 123456),
    ],
)
def test_to_paise(amount, expected_paise):
    assert to_paise(amount) == expected_paise


@pytest.mark.parametrize(
    "paise,expected_amount",
    [(100, Decimal("1.00")), (9999, Decimal("99.99")), (1, Decimal("0.01"))],
)
def test_from_paise_round_trips(paise, expected_amount):
    assert from_paise(paise) == expected_amount


@pytest.mark.parametrize(
    "razorpay_method,expected",
    [
        ("upi", "upi"),
        ("card", "card"),
        ("netbanking", "netbanking"),
        ("wallet", "other"),
        ("emi", "card"),
        ("paylater", "other"),
        ("something_new_razorpay_adds_later", "other"),
        (None, "other"),
    ],
)
def test_map_provider_method(razorpay_method, expected):
    assert map_provider_method(razorpay_method) == expected


class TestParseWebhookEvent:
    adapter = RazorpayAdapter()

    async def test_payment_captured_maps_to_payment_succeeded(self):
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_ABC123",
                        "order_id": "order_XYZ789",
                        "amount": 50000,
                        "currency": "INR",
                        "method": "upi",
                        "captured": True,
                        "created_at": 1700000000,
                    }
                }
            },
        }
        event = await self.adapter.parse_webhook_event(db=None, clinic_id=None, payload=payload)
        assert event is not None
        assert event.event_type == "payment_succeeded"
        assert event.provider_reference == "order_XYZ789"
        assert event.confirmation is not None
        assert event.confirmation.provider_payment_reference == "pay_ABC123"
        assert event.confirmation.confirmed_method == "upi"
        assert event.confirmation.amount == Decimal("500.00")
        assert event.confirmation.captured_at == datetime.fromtimestamp(
            1700000000, tz=event.confirmation.captured_at.tzinfo
        )

    async def test_payment_failed_maps_to_payment_failed(self):
        payload = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_FAIL1",
                        "order_id": "order_XYZ789",
                        "error_code": "BAD_REQUEST_ERROR",
                        "error_description": "card declined",
                    }
                }
            },
        }
        event = await self.adapter.parse_webhook_event(db=None, clinic_id=None, payload=payload)
        assert event is not None
        assert event.event_type == "payment_failed"
        assert event.provider_reference == "order_XYZ789"
        assert event.error_message == "card declined"

    async def test_payment_link_paid_maps_to_payment_succeeded_by_link_id(self):
        payload = {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {"entity": {"id": "plink_LINK1"}},
                "payment": {
                    "entity": {
                        "id": "pay_LINKPAY1",
                        "amount": 25000,
                        "currency": "INR",
                        "method": "card",
                        "created_at": 1700000000,
                    }
                },
            },
        }
        event = await self.adapter.parse_webhook_event(db=None, clinic_id=None, payload=payload)
        assert event is not None
        assert event.event_type == "payment_succeeded"
        assert event.provider_reference == "plink_LINK1"
        assert event.confirmation.confirmed_method == "card"

    async def test_refund_processed_maps_to_refund_completed_by_refund_id(self):
        payload = {
            "event": "refund.processed",
            "payload": {"refund": {"entity": {"id": "rfnd_R1"}}},
        }
        event = await self.adapter.parse_webhook_event(db=None, clinic_id=None, payload=payload)
        assert event is not None
        assert event.event_type == "refund_completed"
        assert event.refund_provider_reference == "rfnd_R1"
        assert event.provider_reference is None  # never the PaymentRequest lookup key

    async def test_unrecognized_event_returns_none(self):
        payload = {"event": "something.we.dont.handle", "payload": {}}
        event = await self.adapter.parse_webhook_event(db=None, clinic_id=None, payload=payload)
        assert event is None

    async def test_authorized_but_not_yet_captured_returns_none(self):
        """payment_capture=1 (auto-capture) means payment.captured follows
        immediately — an authorized-and-already-captured event is
        redundant, not a new state."""
        payload = {
            "event": "payment.authorized",
            "payload": {
                "payment": {"entity": {"id": "pay_X", "order_id": "order_X", "captured": True}}
            },
        }
        event = await self.adapter.parse_webhook_event(db=None, clinic_id=None, payload=payload)
        assert event is None

    async def test_authorized_not_captured_maps_to_payment_authorized(self):
        payload = {
            "event": "payment.authorized",
            "payload": {
                "payment": {"entity": {"id": "pay_X", "order_id": "order_X", "captured": False}}
            },
        }
        event = await self.adapter.parse_webhook_event(db=None, clinic_id=None, payload=payload)
        assert event is not None
        assert event.event_type == "payment_authorized"
        assert event.provider_reference == "order_X"
