"""Locale parity for the email templates (issue #343).

Every locale under ``backend/templates/email/`` must ship the same file
set. The renderer's locale → ``default/`` → bare-key fallback chain
(``app/core/email/service.py``) silently hides a missing translation, so
without this ratchet a new template added in one language degrades to
another language for everyone else — which is exactly how ``en`` lost
the verifactu ``.txt`` bodies and ``es``/``fr``/``pt`` never got
``invoice_sent`` before this test existed.

``pt-BR`` is a host overlay (#509): it may ship only the templates whose
wording differs from European Portuguese. Russian currently overlays only
the translated account-invitation templates. Missing keys use the renderer's
locale fallback chain.
"""

from __future__ import annotations

from pathlib import Path

from app.core.email.service import TEMPLATES_DIR

EXPECTED_LOCALES = {
    "es",
    "en",
    "fr",
    "pt",
    "ta",
    "te",
    "hi",
    "de",
    "hu",
    "pl",
    "it",
    "ar",
}
# Overlay dirs: subset of templates, not subject to full-file parity.
OVERLAY_LOCALES = {"pt-BR", "ru"}
ALL_COMMUNICATION_LOCALES = EXPECTED_LOCALES | {"ru"}

# Country-specific templates a locale deliberately does not ship: Telugu
# targets Indian clinics, which never run Spain's Verifactu (AEAT).
_VERIFACTU_TEMPLATES = {
    "verifactu_cert_expiry.html",
    "verifactu_cert_expiry.txt",
    "verifactu_record_rejected.html",
    "verifactu_record_rejected.txt",
}
COUNTRY_EXEMPT: dict[str, set[str]] = {
    "te": _VERIFACTU_TEMPLATES,
    "hi": _VERIFACTU_TEMPLATES,
}


def _locale_dirs() -> dict[str, Path]:
    return {p.name: p for p in TEMPLATES_DIR.iterdir() if p.is_dir()}


def test_all_communication_locales_present() -> None:
    assert EXPECTED_LOCALES <= set(_locale_dirs())
    # Overlay dirs are optional extras on top of the full set.
    assert set(_locale_dirs()) - OVERLAY_LOCALES == EXPECTED_LOCALES


def test_every_locale_ships_the_same_template_set() -> None:
    dirs = _locale_dirs()
    reference_locale = "es"
    reference = {f.name for f in dirs[reference_locale].iterdir() if f.is_file()}
    assert reference, "reference locale has no templates"

    for locale, path in sorted(dirs.items()):
        if locale in OVERLAY_LOCALES:
            continue
        files = {f.name for f in path.iterdir() if f.is_file()}
        missing = reference - files - COUNTRY_EXEMPT.get(locale, set())
        extra = files - reference
        assert not missing and not extra, (
            f"{locale}/ is out of parity with {reference_locale}/: "
            f"missing={sorted(missing)} extra={sorted(extra)}"
        )


def test_pt_br_overlay_is_a_strict_subset_of_pt() -> None:
    """pt-BR may only override files that exist in pt/; no orphans."""
    dirs = _locale_dirs()
    if "pt-BR" not in dirs:
        return
    pt_files = {f.name for f in dirs["pt"].iterdir() if f.is_file()}
    br_files = {f.name for f in dirs["pt-BR"].iterdir() if f.is_file()}
    assert br_files, "pt-BR/ exists but is empty — remove the directory"
    assert br_files <= pt_files, f"pt-BR/ has files not in pt/: {sorted(br_files - pt_files)}"
    # Every overlay file must differ from pt (otherwise delete it
    # and fall back). Identical copies defeat the overlay design.
    for name in sorted(br_files):
        pt_text = (dirs["pt"] / name).read_text(encoding="utf-8")
        br_text = (dirs["pt-BR"] / name).read_text(encoding="utf-8")
        assert pt_text != br_text, (
            f"pt-BR/{name} is identical to pt/{name} — delete it and let the renderer fall back"
        )


def test_ru_overlay_is_a_strict_subset_of_en() -> None:
    """Russian invite copy is translated; other mail falls back to English."""
    dirs = _locale_dirs()
    ru_files = {f.name for f in dirs["ru"].iterdir() if f.is_file()}
    en_files = {f.name for f in dirs["en"].iterdir() if f.is_file()}
    assert ru_files == {"auth_invite.html", "auth_invite.txt"}
    assert ru_files <= en_files
    for name in sorted(ru_files):
        assert (dirs["ru"] / name).read_text(encoding="utf-8") != (dirs["en"] / name).read_text(
            encoding="utf-8"
        )


def test_language_gate_accepts_every_template_locale() -> None:
    """The SystemSetup / communications-PATCH gate must match the shipped
    template set — a locale with templates but no gate entry (or vice
    versa) is a drift bug."""
    from app.core.auth.router import _CommunicationsSettingsPatch
    from app.core.auth.schemas import SystemSetup

    for locale in sorted(ALL_COMMUNICATION_LOCALES):
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

    from app.core.auth.router import _INVITE_EMAIL_SUBJECTS

    assert set(_INVITE_EMAIL_SUBJECTS) == ALL_COMMUNICATION_LOCALES | {"pt-BR"}


def test_language_gate_accepts_pt_br_overlay() -> None:
    """pt-BR is a host overlay (#509): accepted as a communication language."""
    from app.core.auth.router import _CommunicationsSettingsPatch
    from app.core.auth.schemas import SystemSetup

    assert _CommunicationsSettingsPatch(language="pt-BR").language == "pt-BR"
    setup = SystemSetup(
        admin_first_name="A",
        admin_last_name="B",
        admin_email="admin@example.com",
        admin_password="password12345",
        clinic_name="X",
        clinic_tax_id="B12345678",
        language="pt-BR",
    )
    assert setup.language == "pt-BR"


def test_ru_email_overlay_renders_and_falls_back_to_english() -> None:
    from app.core.email.service import EmailService

    service = EmailService()
    service._initialize()
    invite = service._render_template(
        "auth_invite",
        "ru",
        {
            "first_name": "Анна",
            "clinic_name": "Клиника",
            "invite_url": "https://example.test/invite",
            "expires_days": 7,
        },
    )
    assert invite is not None and "Вас пригласили в Dentum" in invite
    appointment = service._render_template(
        "appointment_confirmation",
        "ru",
        {"clinic_name": "Clinic", "patient_name": "Alex"},
    )
    assert appointment is not None
    assert 'lang="ru"' in appointment
    assert "Appointment" in appointment


def test_invitation_email_renders_html_and_text_for_every_locale() -> None:
    from app.core.email.service import EmailService

    service = EmailService()
    service._initialize()
    context = {
        "first_name": "Alex",
        "clinic_name": "Test clinic",
        "invite_url": "https://example.test/invite-token",
        "expires_days": 7,
    }
    for locale in sorted(ALL_COMMUNICATION_LOCALES | {"pt-BR"}):
        html = service._render_template("auth_invite", locale, context)
        plain = service._render_template("auth_invite", locale, context, extension="txt")
        assert html is not None and "Alex" in html and context["invite_url"] in html, locale
        assert plain is not None and "Alex" in plain and context["invite_url"] in plain, locale
        assert "{{" not in html and "{{" not in plain, locale
        expected_direction = 'dir="rtl"' if locale == "ar" else 'dir="ltr"'
        assert expected_direction in html, locale


def test_pt_br_email_falls_back_to_pt_for_missing_templates() -> None:
    """Templates not overridden in pt-BR, resolve through pt (#509)."""
    from app.core.email.service import EmailService

    service = EmailService()
    service._initialize()
    # appointment_confirmation ships only under pt/ (no BR wording delta).
    rendered = service._render_template(
        "appointment_confirmation",
        "pt-BR",
        {"clinic_name": "Clínica Teste", "patient_name": "Ana"},
    )
    assert rendered is not None
    pt = service._render_template(
        "appointment_confirmation",
        "pt",
        {"clinic_name": "Clínica Teste", "patient_name": "Ana"},
    )
    # The pt template is reused. base.html stamps the requested locale
    # into <html lang>, so the documents differ only by that attribute.
    assert rendered.replace('lang="pt-BR"', 'lang="pt"', 1) == pt


def test_pt_br_email_uses_overlay_when_present() -> None:
    """Templates that exist under pt-BR/ win over the pt/ fallback."""
    from app.core.email.service import EmailService

    service = EmailService()
    service._initialize()
    br = service._render_template(
        "invoice_sent",
        "pt-BR",
        {"clinic_name": "Clínica Teste", "invoice_number": "1", "patient_name": "Ana"},
    )
    pt = service._render_template(
        "invoice_sent",
        "pt",
        {"clinic_name": "Clínica Teste", "invoice_number": "1", "patient_name": "Ana"},
    )
    assert br is not None and pt is not None
    assert br != pt
    assert "entrar em contato" in br
    assert "Enviamos-lhe" not in br


def test_templates_are_nonempty_and_html_extends_base() -> None:
    for locale, path in _locale_dirs().items():
        for f in path.iterdir():
            content = f.read_text(encoding="utf-8")
            assert content.strip(), f"{locale}/{f.name} is empty"
            if f.suffix == ".html":
                assert 'extends "base.html"' in content, (
                    f"{locale}/{f.name} does not extend base.html"
                )


def test_exempt_template_falls_back_to_english() -> None:
    """A country-specific template missing from a locale renders the English one."""
    from app.core.email.service import EmailService

    service = EmailService()
    service._initialize()
    html = service._render_template(
        "verifactu_cert_expiry",
        "hi",
        {"admin_name": "A", "clinic_name": "C", "is_expired": True, "valid_until": "x"},
    )
    assert html is not None and "Verifactu certificate" in html
