"""A clinic's SMTP mail goes out from the clinic's own sender (#1052)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.core.auth.models import Clinic
from app.core.email.providers.base import EmailMessage, EmailResult, EmailStatus
from app.core.email.providers.smtp import SMTPProvider
from app.core.email.service import EmailService
from app.modules.notifications.models import ClinicSmtpSettings


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("configured", "explicit", "sent_from"),
    [
        ("recepcion@clinic.example", None, "recepcion@clinic.example"),
        (None, None, "instance@host.example"),
        ("recepcion@clinic.example", "other@clinic.example", "other@clinic.example"),
    ],
)
async def test_clinic_smtp_sender(
    db_session: AsyncSession, test_clinic: Clinic, monkeypatch, configured, explicit, sent_from
) -> None:
    monkeypatch.setattr(app_settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(app_settings, "EMAIL_FROM_ADDRESS", "instance@host.example")
    db_session.add(
        ClinicSmtpSettings(
            clinic_id=test_clinic.id,
            provider="smtp",
            host="smtp.clinic.example",
            port=587,
            from_email=configured,
            from_name="Clinica Sol",
            is_active=True,
        )
    )
    await db_session.commit()

    headers: list[str] = []

    async def send(self, email: EmailMessage) -> EmailResult:
        headers.append(str(self._build_message(email)["From"]))
        return EmailResult(status=EmailStatus.SUCCESS, provider="smtp")

    monkeypatch.setattr(SMTPProvider, "send", send)
    message = EmailMessage(
        to_email="ana@example.com", subject="Cita", body_html="<p>Cita</p>", from_email=explicit
    )
    await EmailService().send(message, db=db_session, clinic_id=test_clinic.id)

    assert headers == [f"Clinica Sol <{sent_from}>"]
