"""The reminder email's check-in button renders in every locale (#1207).

#480 added a ``checkin_url`` button to ``appointment_reminder.html`` but
missed the ``pt-BR`` overlay (which shadows ``pt/`` entirely, so Brazilian
patients got no link) and left the label in English in ``ar``, ``hi``,
``ta`` and ``te``.
"""

from __future__ import annotations

import pytest

from app.core.email.service import TEMPLATES_DIR, EmailService

CHECKIN_URL = "https://clinic.example.com/checkin/tok-1207"
ENGLISH_LABEL = "Check in for my appointment"

LOCALES = sorted(p.name for p in TEMPLATES_DIR.iterdir() if p.is_dir())


def _render(locale: str, **extra: object) -> str:
    service = EmailService()
    service._initialize()
    html = service._render_template(
        "appointment_reminder",
        locale,
        {
            "clinic_name": "Clinic",
            "patient_name": "Ana",
            "appointment_date": "2026-12-01",
            "appointment_time": "10:00",
            **extra,
        },
    )
    assert html is not None
    return html


def test_every_locale_is_covered() -> None:
    assert {"en", "pt", "pt-BR", "ar", "hi", "ta", "te"} <= set(LOCALES)


@pytest.mark.parametrize("locale", LOCALES)
def test_reminder_renders_checkin_button(locale: str) -> None:
    html = _render(locale, checkin_url=CHECKIN_URL)
    assert f'href="{CHECKIN_URL}"' in html, f"{locale}: no check-in link"


@pytest.mark.parametrize("locale", LOCALES)
def test_reminder_without_checkin_url_has_no_button(locale: str) -> None:
    assert "/checkin/" not in _render(locale)


@pytest.mark.parametrize("locale", [loc for loc in LOCALES if loc != "en"])
def test_reminder_checkin_label_is_translated(locale: str) -> None:
    html = _render(locale, checkin_url=CHECKIN_URL)
    assert ENGLISH_LABEL not in html, f"{locale}: check-in button label is in English"
