"""Deliver booking emails without putting contacts or tokens in application logs."""

import asyncio
import smtplib
import ssl
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.email.providers.base import EmailMessage
from app.core.email.providers.smtp import SMTPProvider
from app.core.email.service import email_service
from app.modules.notifications.models import ClinicSmtpSettings


def _send_smtp(provider: SMTPProvider, message: EmailMessage) -> bool:
    """Use the configured SMTP provider without its recipient-logging path."""
    try:
        if not provider._use_ssl and not provider._use_tls:
            return False
        mime = provider._build_message(message)
        context = ssl.create_default_context()
        if provider._use_ssl:
            server = smtplib.SMTP_SSL(
                provider._host, provider._port, timeout=provider._timeout, context=context
            )
        else:
            server = smtplib.SMTP(provider._host, provider._port, timeout=provider._timeout)
        try:
            if not provider._use_ssl:
                server.starttls(context=context)
            if provider._username and provider._password:
                server.login(provider._username, provider._password)
            refused = server.sendmail(
                message.from_email or provider._default_from_email,
                [message.to_email, *message.cc, *message.bcc],
                mime.as_string(),
            )
            return not refused
        finally:
            try:
                server.quit()
            except Exception:
                server.close()
    except Exception:
        # SMTP errors may contain recipient addresses or token-bearing message text.
        return False


async def deliver(db: AsyncSession, clinic_id: UUID, message: EmailMessage) -> None:
    if settings.TESTING:
        result = await email_service.send(message, db=db, clinic_id=clinic_id)
        if not result.is_success:
            raise HTTPException(503, "Email delivery unavailable")
        return
    if not settings.EMAIL_ENABLED:
        raise HTTPException(503, "Email delivery unavailable")
    clinic_settings = await db.scalar(
        select(ClinicSmtpSettings).where(ClinicSmtpSettings.clinic_id == clinic_id)
    )
    if clinic_settings and clinic_settings.is_active and clinic_settings.provider == "disabled":
        raise HTTPException(503, "Email delivery unavailable")
    provider = await email_service.create_provider_for_clinic(db, clinic_id)
    provider = provider or email_service.provider
    if not isinstance(provider, SMTPProvider):
        raise HTTPException(503, "Email delivery unavailable")
    if not message.from_email:
        message.from_email = settings.EMAIL_FROM_ADDRESS
        message.from_name = message.from_name or settings.EMAIL_FROM_NAME
    if not await asyncio.to_thread(_send_smtp, provider, message):
        raise HTTPException(503, "Email delivery unavailable")
