"""Email rendering formats the clinic address and leaves subjects unescaped (#1043).

``clinic_address`` reaches the email context as the raw ``Clinic.address``
JSONB dict, and ``base.html`` printed it as a Python dict. Subjects are
plain text, yet were rendered with the HTML-autoescaping environment, so
``O'Brien & Sons`` became ``O&#39;Brien &amp; Sons``.
"""

from __future__ import annotations

import pytest

from app.core.email.providers.base import EmailMessage, EmailResult, EmailStatus
from app.core.email.service import EmailService

ADDRESS = {
    "street": "Calle Mayor 1",
    "city": "Madrid",
    "postal_code": "28013",
    "country": "ES",
}


async def _render(context: dict, subject: str) -> EmailMessage:
    service = EmailService()
    sent: list[EmailMessage] = []

    async def capture(message, db=None, clinic_id=None):
        sent.append(message)
        return EmailResult(status=EmailStatus.SUCCESS, provider="test")

    service.send = capture  # type: ignore[method-assign]
    await service.send_templated(
        to_email="patient@example.com",
        template_key="appointment_confirmation",
        context=context,
        subject=subject,
        locale="es",
    )
    assert len(sent) == 1
    return sent[0]


@pytest.mark.asyncio
async def test_footer_prints_a_formatted_address_line() -> None:
    message = await _render(
        {"clinic_name": "Clínica Demo", "clinic_address": dict(ADDRESS)},
        subject="Cita",
    )

    assert "Calle Mayor 1, 28013 Madrid, ES" in message.body_html
    assert "'street'" not in message.body_html
    assert "&#39;street&#39;" not in message.body_html


@pytest.mark.asyncio
async def test_partial_and_empty_addresses() -> None:
    partial = await _render({"clinic_address": {"city": "Madrid", "country": None}}, "Cita")
    assert '<p class="clinic-info">Madrid</p>' in partial.body_html

    empty = await _render({"clinic_address": {}}, "Cita")
    assert 'class="clinic-info"' not in empty.body_html


@pytest.mark.asyncio
async def test_caller_context_is_not_mutated() -> None:
    context = {"clinic_address": dict(ADDRESS)}
    await _render(context, "Cita")
    assert context["clinic_address"] == ADDRESS


@pytest.mark.asyncio
async def test_subject_is_not_html_escaped() -> None:
    message = await _render(
        {"clinic_name": "O'Brien & Sons", "clinic_address": dict(ADDRESS)},
        subject="Confirma tu solicitud de cita en {{ clinic_name }}",
    )

    assert message.subject == "Confirma tu solicitud de cita en O'Brien & Sons"
    # The HTML body still escapes the same value.
    assert "O&#39;Brien &amp; Sons" in message.body_html
