"""SmsAdapter — delivers the SMS channel via whichever provider is configured.

Implements the notifications ``ChannelAdapter`` contract (the only
cross-module import; legal because ``notifications`` is in this module's
``manifest.depends``). Logs every attempt to ``SmsOutboxLog`` regardless of
outcome, then delegates the actual send to the configured provider.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.core.email.encryption import decrypt_password
from app.modules.notifications.channels import AdapterResult, Channel, OutboundMessage, SendStatus

from .models import SmsGatewaySettings, SmsOutboxLog
from .providers import get_provider

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_STATUS_MAP = {
    "sent": SendStatus.SENT,
    "failed": SendStatus.FAILED,
    "skipped": SendStatus.SKIPPED,
}


async def _active_settings(db: AsyncSession, clinic_id: UUID) -> SmsGatewaySettings | None:
    return (
        await db.execute(
            select(SmsGatewaySettings).where(
                SmsGatewaySettings.clinic_id == clinic_id,
                SmsGatewaySettings.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


class SmsAdapter:
    """SMS delivery via whichever provider the clinic has configured."""

    # NOTE: requires `SMS = "sms"` to exist on notifications' Channel enum —
    # see the Phase 6 install guide for that one-line upstream patch.
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

        body = msg.body_text or msg.subject or ""
        api_key = decrypt_password(settings.api_key_encrypted) if settings.api_key_encrypted else None
        provider = get_provider(settings.provider_name)

        result = await provider.send(
            to=msg.to_address,
            body=body,
            sender_id=settings.sender_id,
            api_key=api_key,
            base_url=settings.base_url,
        )

        db.add(
            SmsOutboxLog(
                clinic_id=msg.clinic_id,
                to_address=msg.to_address,
                body=body,
                provider_name=settings.provider_name,
                status=result.status,
                error_message=result.error_message,
                sent_at=datetime.now(UTC) if result.status == "sent" else None,
            )
        )
        await db.commit()

        return AdapterResult(
            status=_STATUS_MAP.get(result.status, SendStatus.FAILED),
            provider=self.adapter_name,
            provider_message_id=result.provider_message_id,
            error_message=result.error_message,
        )
