"""razorpay business logic: credentials, webhook signature verification,
webhook health bookkeeping. Mirrors ``whatsapp_kapso.service.KapsoService``."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import decrypt_password, encrypt_password

from .models import RazorpaySettings


class RazorpaySettingsService:
    """All clinic-scoped. Secrets encrypted at rest (Fernet)."""

    @staticmethod
    async def get_settings(db: AsyncSession, clinic_id: UUID) -> RazorpaySettings | None:
        return (
            await db.execute(
                select(RazorpaySettings).where(RazorpaySettings.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_active_settings(db: AsyncSession, clinic_id: UUID) -> RazorpaySettings | None:
        """Configured *and* active — the gate ``RazorpayAdapter.supports()`` checks."""
        settings = await RazorpaySettingsService.get_settings(db, clinic_id)
        if settings is None or not settings.is_active:
            return None
        if not settings.key_id or not settings.key_secret_encrypted:
            return None
        return settings

    @staticmethod
    async def upsert_settings(db: AsyncSession, clinic_id: UUID, data: dict) -> RazorpaySettings:
        settings = await RazorpaySettingsService.get_settings(db, clinic_id)
        if settings is None:
            settings = RazorpaySettings(
                clinic_id=clinic_id, key_secret_encrypted="", webhook_secret_encrypted=""
            )
            db.add(settings)

        if data.get("mode"):
            settings.mode = data["mode"]
        if data.get("key_id") is not None:
            settings.key_id = data["key_id"] or None
        if data.get("key_secret"):
            settings.key_secret_encrypted = encrypt_password(data["key_secret"])
        if data.get("webhook_secret"):
            settings.webhook_secret_encrypted = encrypt_password(data["webhook_secret"])
        if "is_active" in data and data["is_active"] is not None:
            settings.is_active = data["is_active"]

        # Credential change resets verification — mirrors KapsoService:
        # a new key pair hasn't been proven to work yet.
        if data.get("key_secret") or data.get("key_id") or data.get("mode"):
            settings.is_verified = False

        await db.commit()
        await db.refresh(settings)
        return settings

    @staticmethod
    def decrypt_credentials(settings: RazorpaySettings) -> tuple[str, str] | None:
        """``(key_id, key_secret)`` or ``None`` if either is missing/undecryptable."""
        if not settings.key_id:
            return None
        secret = decrypt_password(settings.key_secret_encrypted)
        if not secret:
            return None
        return settings.key_id, secret

    @staticmethod
    def verify_signature(settings: RazorpaySettings, raw_body: bytes, signature: str) -> bool:
        """HMAC-SHA256(raw_body, webhook_secret), constant-time compare —
        Razorpay's own documented webhook verification scheme."""
        secret = decrypt_password(settings.webhook_secret_encrypted)
        if not secret or not signature:
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    @staticmethod
    async def record_webhook_received(
        db: AsyncSession, settings: RazorpaySettings, event_type: str | None
    ) -> None:
        settings.last_webhook_received_at = datetime.now(UTC)
        settings.last_webhook_event_type = event_type
        await db.flush()

    @staticmethod
    async def record_webhook_processed(db: AsyncSession, settings: RazorpaySettings) -> None:
        settings.last_webhook_processed_at = datetime.now(UTC)
        await db.flush()

    @staticmethod
    async def record_webhook_error(
        db: AsyncSession, settings: RazorpaySettings, message: str
    ) -> None:
        settings.last_webhook_error = message[:500]
        settings.last_webhook_error_at = datetime.now(UTC)
        await db.flush()
