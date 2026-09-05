"""Locale parity for the email templates (issue #343).

Every locale under ``backend/templates/email/`` must ship the same file
set. The renderer's locale → ``default/`` → bare-key fallback chain
(``app/core/email/service.py``) silently hides a missing translation, so
without this ratchet a new template added in one language degrades to
another language for everyone else — which is exactly how ``en`` lost
the verifactu ``.txt`` bodies and ``es``/``fr``/``pt`` never got
``invoice_sent`` before this test existed.
"""

from __future__ import annotations

from pathlib import Path

from app.core.email.service import TEMPLATES_DIR

EXPECTED_LOCALES = {"es", "en", "fr", "pt", "ta", "de", "hu", "pl", "it"}


def _locale_dirs() -> dict[str, Path]:
    return {p.name: p for p in TEMPLATES_DIR.iterdir() if p.is_dir()}


def test_all_communication_locales_present() -> None:
    assert set(_locale_dirs()) == EXPECTED_LOCALES


def test_every_locale_ships_the_same_template_set() -> None:
    dirs = _locale_dirs()
    reference_locale = "es"
    reference = {f.name for f in dirs[reference_locale].iterdir() if f.is_file()}
    assert reference, "reference locale has no templates"

    for locale, path in sorted(dirs.items()):
        files = {f.name for f in path.iterdir() if f.is_file()}
        missing = reference - files
        extra = files - reference
        assert not missing and not extra, (
            f"{locale}/ is out of parity with {reference_locale}/: "
            f"missing={sorted(missing)} extra={sorted(extra)}"
        )


def test_language_gate_accepts_every_template_locale() -> None:
    """The SystemSetup / communications-PATCH gate must match the shipped
    template set — a locale with templates but no gate entry (or vice
    versa) is a drift bug."""
    from app.core.auth.router import _CommunicationsSettingsPatch
    from app.core.auth.schemas import SystemSetup

    for locale in sorted(EXPECTED_LOCALES):
        assert _CommunicationsSettingsPatch(language=locale).language == locale
        setup = SystemSetup(
            admin_first_name="A",
            admin_last_name="B",
            admin_email="admin@example.com",
            admin_password="password12345",
            clinic_name="X",
            clinic_tax_id="B12345678",
            language=locale,
        )
        assert setup.language == locale


def test_templates_are_nonempty_and_html_extends_base() -> None:
    for locale, path in _locale_dirs().items():
        for f in path.iterdir():
            content = f.read_text(encoding="utf-8")
            assert content.strip(), f"{locale}/{f.name} is empty"
            if f.suffix == ".html":
                assert 'extends "base.html"' in content, (
                    f"{locale}/{f.name} does not extend base.html"
                )
