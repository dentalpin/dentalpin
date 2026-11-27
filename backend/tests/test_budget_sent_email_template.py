"""Every locale's ``budget_sent`` email carries the custom message and the
public quote link (#1205, #1206).

``on_budget_sent`` puts the Send dialog's ``custom_message`` and the
``/p/budget/{token}`` ``public_url`` into the context, but eight locales
dropped the message and no locale linked the public page, so the patient
could neither read the note nor open, accept or sign the quote from the
email.
"""

from __future__ import annotations

import pytest

from app.core.email.providers.base import EmailMessage, EmailResult, EmailStatus
from app.core.email.service import TEMPLATES_DIR, EmailService

LOCALES = sorted(
    p.name for p in TEMPLATES_DIR.iterdir() if p.is_dir() and (p / "budget_sent.html").exists()
)

MESSAGE = "CUSTOM-MESSAGE-MARKER-1205"
PUBLIC_URL = "https://clinic.example/p/budget/0b6f2c1e-1206-4c1b-9d2a-5f3e8a7b1c2d"


async def _render(locale: str, context: dict) -> EmailMessage:
    service = EmailService()
    sent: list[EmailMessage] = []

    async def capture(message, db=None, clinic_id=None):
        sent.append(message)
        return EmailResult(status=EmailStatus.SUCCESS, provider="test")

    service.send = capture  # type: ignore[method-assign]
    await service.send_templated(
        to_email="patient@example.com",
        template_key="budget_sent",
        context=context,
        subject="Quote",
        locale=locale,
    )
    assert len(sent) == 1
    return sent[0]


def _context(**overrides) -> dict:
    return {
        "patient_name": "Ana García",
        "budget_number": "P-2026-0001",
        "budget_date": "01/11/2026",
        "treatments": [{"name": "Empaste", "tooth": "16", "price": "60,00 €"}],
        "subtotal": "60,00 €",
        "discount_amount": None,
        "total": "60,00 €",
        "validity_days": 30,
        "notes": None,
        "clinic_name": "Clínica Demo",
        "clinic_phone": None,
        **overrides,
    }


def test_every_communication_locale_ships_budget_sent() -> None:
    assert len(LOCALES) == 13, LOCALES


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
async def test_budget_sent_renders_custom_message_and_public_link(locale: str) -> None:
    message = await _render(locale, _context(custom_message=MESSAGE, public_url=PUBLIC_URL))

    assert MESSAGE in message.body_html, f"{locale}/budget_sent.html drops custom_message"
    assert f'href="{PUBLIC_URL}"' in message.body_html, (
        f"{locale}/budget_sent.html has no link to public_url"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
async def test_budget_sent_without_link_renders_no_empty_href(locale: str) -> None:
    message = await _render(locale, _context(custom_message=None, public_url=None))

    assert 'href=""' not in message.body_html
    assert "/p/budget/" not in message.body_html
