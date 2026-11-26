"""Email subjects come from the file template, never the raw key (#1204).

Core notification types have no ``notification_templates`` email row, so
the email adapter fell back to ``f"Notificación: {template_key}"``: every
patient got ``Notificación: appointment_reminder``, in every language.
With no clinic override, the subject is now the localized ``title`` block
of the file template the body renders from. A clinic row's subject still
wins.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.email.providers.base import EmailMessage, EmailResult, EmailStatus
from app.core.email.service import TEMPLATES_DIR, EmailService, email_service
from app.modules.notifications.channels import Channel, OutboundMessage
from app.modules.notifications.channels.email_adapter import EmailAdapter

CONTEXT = {"clinic_name": "O'Brien & Sons", "patient_name": "Ana", "is_expired": False}

TEMPLATE_FILES = sorted(
    (d.name, f.stem) for d in TEMPLATES_DIR.iterdir() if d.is_dir() for f in d.glob("*.html")
)


def _capture(sent: list[EmailMessage]):
    async def capture(message, db=None, clinic_id=None):
        sent.append(message)
        return EmailResult(status=EmailStatus.SUCCESS, provider="test")

    return capture


async def _adapter_subject(monkeypatch, subject: str | None, locale: str = "en") -> str:
    sent: list[EmailMessage] = []
    monkeypatch.setattr(email_service, "send", _capture(sent))
    await EmailAdapter().send(
        None,  # type: ignore[arg-type]
        OutboundMessage(
            channel=Channel.EMAIL,
            to_address="ana@example.com",
            clinic_id=uuid4(),
            template_key="appointment_reminder",
            locale=locale,
            context={**CONTEXT, "appointment_date": "1 Dec", "appointment_time": "10:00"},
            subject=subject,
        ),
    )
    assert len(sent) == 1
    return sent[0].subject


@pytest.mark.asyncio
async def test_no_override_uses_the_localized_file_subject(monkeypatch) -> None:
    subject = await _adapter_subject(monkeypatch, None, locale="en")
    assert subject == "Appointment reminder - O'Brien & Sons"

    subject = await _adapter_subject(monkeypatch, None, locale="de")
    assert subject == "Terminerinnerung - O'Brien & Sons"


@pytest.mark.asyncio
async def test_clinic_override_subject_wins(monkeypatch) -> None:
    subject = await _adapter_subject(monkeypatch, "Custom for {{ clinic_name }}")
    assert subject == "Custom for O'Brien & Sons"


def test_every_locale_dir_is_covered() -> None:
    assert len({locale for locale, _ in TEMPLATE_FILES}) == 13


@pytest.mark.asyncio
@pytest.mark.parametrize(("locale", "template_key"), TEMPLATE_FILES)
async def test_every_template_yields_a_subject(locale: str, template_key: str) -> None:
    service = EmailService()
    sent: list[EmailMessage] = []
    service.send = _capture(sent)  # type: ignore[method-assign]

    await service.send_templated(
        to_email="ana@example.com",
        template_key=template_key,
        context=dict(CONTEXT),
        subject=None,
        locale=locale,
    )

    assert len(sent) == 1
    subject = sent[0].subject
    assert subject.strip()
    assert template_key not in subject
    assert not subject.startswith("Notificación")
    # Plain text: no HTML escaping, no markup.
    assert "&amp;" not in subject and "&#39;" not in subject and "<" not in subject
