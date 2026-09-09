"""SmsGatewayAdapter - delivers the SMS channel via pluggable providers.

Implements the notifications ``ChannelAdapter`` contract (the only
cross-module import; legal because ``notifications`` is in this
module's ``depends``). Pure wire: resolve the clinic's provider
backend, hand it the rendered text, map the outcome to an
``AdapterResult``. No business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.notifications.channels import (
    AdapterResult,
    Channel,
    OutboundMessage,
    SendStatus,
)

from . import providers
from .models import SmsGatewaySettings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _active_settings(db: AsyncSession, clinic_id: UUID) -> SmsGatewaySettings | None:
    return (
        await db.execute(
            select(SmsGatewaySettings).where(
                SmsGatewaySettings.clinic_id == clinic_id,
                SmsGatewaySettings.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


class SmsGatewayAdapter:
    """SMS delivery via the clinic's configured provider backend."""

    channel = Channel.SMS
    adapter_name = "sms_gateway"

    async def supports(self, db: AsyncSession, clinic_id: UUID) -> bool:
        return await _active_settings(db, clinic_id) is not None

    async def send(self, db: AsyncSession, msg: OutboundMessage) -> AdapterResult:
        settings = await _active_settings(db, msg.clinic_id)
        if settings is None:
            return AdapterResult(
                status=SendStatus.FAILED,
                provider=self.adapter_name,
                error_message="sms_gateway not configured for this clinic",
            )
        backend = providers.get_provider(settings.provider)
        if backend is None:
            return AdapterResult(
                status=SendStatus.FAILED,
                provider=self.adapter_name,
                error_message=(
                    f"sms provider '{settings.provider}' is not implemented in v1 "
                    "(log placeholder only)"
                ),
            )
        ok, provider_message_id, error_message = await backend.send(db, msg.clinic_id, msg)
        if not ok:
            return AdapterResult(
                status=SendStatus.FAILED,
                provider=self.adapter_name,
                error_message=error_message or "sms provider failed",
            )
        return AdapterResult(
            status=SendStatus.SENT,
            provider=self.adapter_name,
            provider_message_id=provider_message_id,
        )
