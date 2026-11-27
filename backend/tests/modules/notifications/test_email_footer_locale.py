"""Email footer speaks the email's language; welcome hides unknown hours (#1153).

``base.html`` defaulted the footer to the Spanish "Este email fue enviado
por <clinic>" for every locale, and the welcome templates printed an invented
"Monday to Friday, 9:00 - 20:00" whenever ``clinic_hours`` was missing, which
the ``patient.created`` handler never sets.
"""

from __future__ import annotations

import pytest

from app.core.email.providers.base import EmailMessage, EmailResult, EmailStatus
from app.core.email.service import TEMPLATES_DIR, EmailService

# Keys ``NotificationHandlers.on_patient_created`` puts in the context.
HANDLER_CONTEXT = {
    "patient_name": "Ana López",
    "clinic_name": "Clínica Sol",
    "clinic_phone": "+34 600 000 000",
    "clinic_address": {"street": "Calle Mayor 1", "city": "Madrid"},
}

LOCALES = sorted(p.name for p in TEMPLATES_DIR.iterdir() if p.is_dir())
SPANISH_FOOTER = "Este email fue enviado por"


async def _render(
    template_key: str,
    locale: str,
    context: dict,
    template_html: str | None = None,
) -> EmailMessage:
    service = EmailService()
    sent: list[EmailMessage] = []

    async def capture(message, db=None, clinic_id=None):
        sent.append(message)
        return EmailResult(status=EmailStatus.SUCCESS, provider="test")

    service.send = capture  # type: ignore[method-assign]
    await service.send_templated(
        to_email="patient@example.com",
        template_key=template_key,
        context=dict(context),
        subject="s",
        locale=locale,
        template_html=template_html,
    )
    assert len(sent) == 1
    return sent[0]


def _footer(html: str) -> str:
    return html.split('<div class="email-footer">', 1)[1].split("</div>", 1)[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("locale", "sentence"),
    [
        ("en", "This email was sent by Clínica Sol"),
        ("de", "Diese E-Mail wurde von Clínica Sol gesendet"),
        ("es", "Este email fue enviado por Clínica Sol"),
    ],
)
async def test_welcome_footer_is_in_the_email_language(locale: str, sentence: str) -> None:
    message = await _render("welcome", locale, HANDLER_CONTEXT)

    assert sentence in _footer(message.body_html)


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
async def test_no_locale_but_spanish_gets_the_spanish_footer(locale: str) -> None:
    message = await _render("appointment_reminder", locale, HANDLER_CONTEXT)
    footer = _footer(message.body_html)

    assert "Clínica Sol" in footer
    if locale != "es":
        assert SPANISH_FOOTER not in footer


@pytest.mark.asyncio
async def test_footer_sent_by_still_overrides_the_default() -> None:
    message = await _render("welcome", "de", {**HANDLER_CONTEXT, "footer_sent_by": "Custom footer"})

    footer = _footer(message.body_html)
    assert "Custom footer" in footer
    assert "Diese E-Mail" not in footer


@pytest.mark.asyncio
async def test_custom_db_template_gets_the_row_locale_footer() -> None:
    custom = '{% extends "base.html" %}{% block content %}<p>Hi</p>{% endblock %}'
    message = await _render("welcome", "en", HANDLER_CONTEXT, template_html=custom)

    assert "This email was sent by Clínica Sol" in _footer(message.body_html)
    assert '<html lang="en"' in message.body_html


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
async def test_welcome_without_clinic_hours_shows_no_hours_box(locale: str) -> None:
    message = await _render("welcome", locale, HANDLER_CONTEXT)

    assert 'class="info-box"' not in message.body_html
    assert "9:00" not in message.body_html
    assert "9h00" not in message.body_html


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ["es", "de", "hu"])
async def test_welcome_with_clinic_hours_shows_them(locale: str) -> None:
    message = await _render("welcome", locale, {**HANDLER_CONTEXT, "clinic_hours": "Mo 8-14"})

    assert 'class="info-box"' in message.body_html
    assert "Mo 8-14" in message.body_html
