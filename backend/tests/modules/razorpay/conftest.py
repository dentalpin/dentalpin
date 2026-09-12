"""Shared fixtures for razorpay tests."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.email.encryption import encrypt_password
from app.modules.razorpay.models import RazorpaySettings

WEBHOOK_SECRET = "test-webhook-secret-do-not-use-in-prod"


def sign(payload: dict) -> tuple[bytes, str]:
    """Return ``(raw_body, signature)`` for a Razorpay-shaped webhook
    payload, HMAC-signed exactly like the real thing (Razorpay's own
    documented scheme: HMAC-SHA256 of the raw request body)."""
    raw = json.dumps(payload).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, signature


@pytest_asyncio.fixture
async def razorpay_settings(db_session: AsyncSession, test_clinic: Clinic) -> RazorpaySettings:
    settings = RazorpaySettings(
        clinic_id=test_clinic.id,
        mode="test",
        key_id="rzp_test_fixture",
        key_secret_encrypted=encrypt_password("fixture_secret"),
        webhook_secret_encrypted=encrypt_password(WEBHOOK_SECRET),
        is_active=True,
    )
    db_session.add(settings)
    await db_session.commit()
    await db_session.refresh(settings)
    return settings
