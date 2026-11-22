"""whatsapp_kapso business logic: credentials, template sync, webhook verify."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import decrypt_password, encrypt_password
from app.modules.notifications.service import NotificationService

from . import client
from .models import WhatsappKapsoSettings, WhatsappKapsoTemplate


class PhoneNumberIdTakenError(ValueError):
    """Another clinic already routes this Kapso ``phone_number_id``."""


class KapsoService:
    """All clinic-scoped. Secrets encrypted at rest (Fernet)."""

    @staticmethod
    async def get_settings(db: AsyncSession, clinic_id: UUID) -> WhatsappKapsoSettings | None:
        return (
            await db.execute(
                select(WhatsappKapsoSettings).where(WhatsappKapsoSettings.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def resolve_by_phone_number_id(
        db: AsyncSession, phone_number_id: str
    ) -> list[WhatsappKapsoSettings]:
        """Webhook tenant resolution — NEVER trust a clinic_id in the payload.

        Returns every clinic configured with this ``phone_number_id``; the
        webhook keeps the one whose secret verifies the signature. The
        column is not unique, and a second clinic saving the same id must
        not cut the first one off (#972).
        """
        return list(
            (
                await db.execute(
                    select(WhatsappKapsoSettings)
                    .where(WhatsappKapsoSettings.phone_number_id == phone_number_id)
                    .order_by(WhatsappKapsoSettings.id)
                )
            ).scalars()
        )

    @staticmethod
    async def upsert_settings(
        db: AsyncSession, clinic_id: UUID, data: dict
    ) -> WhatsappKapsoSettings:
        new_number = data.get("phone_number_id")
        if new_number:
            taken = await db.scalar(
                select(WhatsappKapsoSettings.id).where(
                    WhatsappKapsoSettings.phone_number_id == new_number,
                    WhatsappKapsoSettings.clinic_id != clinic_id,
                )
            )
            if taken is not None:
                raise PhoneNumberIdTakenError(
                    "Este phone_number_id ya está configurado en otra clínica."
                )
        settings = await KapsoService.get_settings(db, clinic_id)
        if settings is None:
            settings = WhatsappKapsoSettings(
                clinic_id=clinic_id, api_key_encrypted="", webhook_secret_encrypted=""
            )
            db.add(settings)

        if data.get("api_key"):
            settings.api_key_encrypted = encrypt_password(data["api_key"])
        if data.get("webhook_secret"):
            settings.webhook_secret_encrypted = encrypt_password(data["webhook_secret"])
        for field in ("phone_number_id", "business_account_id", "display_phone_number"):
            if data.get(field) is not None:
                setattr(settings, field, data[field])
        if "is_active" in data and data["is_active"] is not None:
            settings.is_active = data["is_active"]
        # Credential change resets verification.
        if data.get("api_key") or data.get("phone_number_id"):
            settings.is_verified = False
        await db.commit()
        await db.refresh(settings)
        return settings

    @staticmethod
    def verify_signature(settings: WhatsappKapsoSettings, raw_body: bytes, signature: str) -> bool:
        """HMAC-SHA256(raw_body, webhook_secret), constant-time compare."""
        secret = decrypt_password(settings.webhook_secret_encrypted)
        if not secret or not signature:
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    @staticmethod
    async def sync_templates(db: AsyncSession, clinic_id: UUID) -> list[WhatsappKapsoTemplate]:
        settings = await KapsoService.get_settings(db, clinic_id)
        if settings is None or not settings.business_account_id:
            raise ValueError("Kapso no configurado (falta business_account_id).")
        api_key = decrypt_password(settings.api_key_encrypted)
        raw = await client.list_templates(api_key, settings.business_account_id)

        now = datetime.now(UTC)
        out: list[WhatsappKapsoTemplate] = []
        for t in raw:
            name, lang = t.get("name"), t.get("language")
            if not name or not lang:
                continue
            existing = (
                await db.execute(
                    select(WhatsappKapsoTemplate).where(
                        WhatsappKapsoTemplate.clinic_id == clinic_id,
                        WhatsappKapsoTemplate.name == name,
                        WhatsappKapsoTemplate.language == lang,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                existing = WhatsappKapsoTemplate(clinic_id=clinic_id, name=name, language=lang)
                db.add(existing)
            existing.status = (t.get("status") or "").lower()
            existing.category = t.get("category")
            existing.synced_at = now
            out.append(existing)
        settings.last_template_sync_at = now
        await db.commit()
        return out

    @staticmethod
    async def map_template(
        db: AsyncSession,
        clinic_id: UUID,
        *,
        notification_type: str,
        locale: str,
        template_name: str,
    ) -> None:
        """Bind a notification type to a synced template, writing the mapping
        into notifications via its public seam (the gateway resolves it)."""
        tmpl = (
            await db.execute(
                select(WhatsappKapsoTemplate).where(
                    WhatsappKapsoTemplate.clinic_id == clinic_id,
                    WhatsappKapsoTemplate.name == template_name,
                    WhatsappKapsoTemplate.language == locale,
                )
            )
        ).scalar_one_or_none()
        status = tmpl.status if tmpl else "pending"
        await NotificationService.upsert_provider_template(
            db,
            clinic_id,
            template_key=notification_type,
            locale=locale,
            provider_template_name=template_name,
            provider_template_status=status,
            channel="whatsapp",
        )

    @staticmethod
    async def test_connection(
        db: AsyncSession, clinic_id: UUID, to_number: str, template_name: str, language: str = "es"
    ) -> tuple[bool, str | None]:
        settings = await KapsoService.get_settings(db, clinic_id)
        if settings is None:
            return False, "no configurado"
        api_key = decrypt_password(settings.api_key_encrypted)
        payload = client.template_payload(to_number, template_name, language, [])
        try:
            await client.send_message(api_key, settings.phone_number_id, payload)
        except client.KapsoError as exc:
            return False, str(exc)[:300]
        settings.is_verified = True
        settings.last_verified_at = datetime.now(UTC)
        await db.commit()
        return True, None
