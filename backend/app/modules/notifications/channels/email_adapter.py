"""Built-in email adapter.

Thin wrapper over the existing ``app.core.email.email_service`` — no SMTP
logic moves here; per-clinic provider resolution stays in
``email_service.create_provider_for_clinic``. This makes email "just
another channel" behind :class:`ChannelAdapter` with no behavioural change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.core.email.providers.base import EmailStatus
from app.core.email.service import email_service

from .base import AdapterResult, Channel, OutboundMessage, SendStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_STATUS_MAP = {
    EmailStatus.SUCCESS: SendStatus.SENT,
    EmailStatus.FAILED: SendStatus.FAILED,
    EmailStatus.SKIPPED: SendStatus.SKIPPED,
}


class EmailAdapter:
    """Delivers the ``email`` channel via the core email service."""

    channel = Channel.EMAIL
    adapter_name = "email"

    async def supports(self, db: AsyncSession, clinic_id: UUID) -> bool:
        # ponytail: email is always a viable fallback — a global provider
        # exists even without per-clinic SMTP. Clinic enable/disable is
        # governed by clinic_notification_settings + email_enabled, not here.
        return True

    async def send(self, db: AsyncSession, msg: OutboundMessage) -> AdapterResult:
        result = await email_service.send_templated(
            to_email=msg.to_address,
            template_key=msg.template_key,
            context=msg.context,
            # None: the service uses the file template's localized title (#1204).
            subject=msg.subject,
            locale=msg.locale,
            to_name=msg.to_name,
            template_html=msg.body_html,
            template_text=msg.body_text,
            db=db,
            clinic_id=msg.clinic_id,
        )
        return AdapterResult(
            status=_STATUS_MAP.get(result.status, SendStatus.FAILED),
            provider=result.provider,
            provider_message_id=result.message_id,
            error_message=result.error_message,
            sent_at=result.sent_at,
        )
