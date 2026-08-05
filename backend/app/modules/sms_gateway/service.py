"""SmsGatewayService — settings management and outbox log listing."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import encrypt_password

from .models import SmsGatewaySettings, SmsOutboxLog
from .providers import available_providers
from .schemas import SmsSettingsUpdate


class SmsGatewayService:
    @staticmethod
    async def get_or_create_settings(db: AsyncSession, clinic_id: UUID) -> SmsGatewaySettings:
        stmt = select(SmsGatewaySettings).where(SmsGatewaySettings.clinic_id == clinic_id)
        settings = (await db.execute(stmt)).scalar_one_or_none()
        if settings is None:
            settings = SmsGatewaySettings(clinic_id=clinic_id, provider_name="placeholder")
            db.add(settings)
            await db.commit()
            await db.refresh(settings)
        return settings

    @staticmethod
    async def update_settings(
        db: AsyncSession, clinic_id: UUID, payload: SmsSettingsUpdate
    ) -> SmsGatewaySettings:
        settings = await SmsGatewayService.get_or_create_settings(db, clinic_id)
        data = payload.model_dump(exclude_unset=True)
        if "api_key" in data:
            api_key = data.pop("api_key")
            if api_key:
                settings.api_key_encrypted = encrypt_password(api_key)
        for field, value in data.items():
            setattr(settings, field, value)
        await db.commit()
        await db.refresh(settings)
        return settings

    @staticmethod
    def list_available_providers() -> list[str]:
        return available_providers()

    @staticmethod
    async def list_outbox(
        db: AsyncSession, clinic_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[SmsOutboxLog], int]:
        from sqlalchemy import func

        stmt = select(SmsOutboxLog).where(SmsOutboxLog.clinic_id == clinic_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()
        stmt = (
            stmt.order_by(SmsOutboxLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total
