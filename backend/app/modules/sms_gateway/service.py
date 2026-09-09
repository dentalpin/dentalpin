"""sms_gateway business logic: provider settings (credentials encrypted)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import encrypt_password

from .models import SmsGatewaySettings


class SmsGatewayService:
    """All clinic-scoped. Secrets encrypted at rest (Fernet)."""

    @staticmethod
    async def get_settings(db: AsyncSession, clinic_id: UUID) -> SmsGatewaySettings | None:
        return (
            await db.execute(
                select(SmsGatewaySettings).where(SmsGatewaySettings.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def upsert_settings(db: AsyncSession, clinic_id: UUID, data: dict) -> SmsGatewaySettings:
        settings = await SmsGatewayService.get_settings(db, clinic_id)
        if settings is None:
            settings = SmsGatewaySettings(clinic_id=clinic_id)
            db.add(settings)

        if data.get("provider") is not None:
            settings.provider = data["provider"]
        if data.get("account_sid"):
            settings.account_sid_encrypted = encrypt_password(data["account_sid"])
        if data.get("auth_token"):
            settings.auth_token_encrypted = encrypt_password(data["auth_token"])
        if data.get("from_number") is not None:
            settings.from_number = data["from_number"] or None
        if "is_active" in data and data["is_active"] is not None:
            settings.is_active = data["is_active"]
        await db.commit()
        await db.refresh(settings)
        return settings
