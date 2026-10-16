"""Console email provider must be loud in production (#614).

`EMAIL_PROVIDER` defaults to `console`, which is reached by omission,
not choice. In production the console provider is metadata-only and
reports FAILED (so the UI and the outbox stop claiming delivery), and
resolving the provider logs an ERROR naming the remedy (resolution is
lazy, so on the first email). Per the maintainer decision, production
boots normally — no refusal.
"""

from __future__ import annotations

import logging

import pytest

from app.core.email.service import EmailService


def _resolve(monkeypatch, caplog, *, environment: str, provider: str = "console"):
    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "ENVIRONMENT", environment)
    monkeypatch.setattr(app_settings, "EMAIL_PROVIDER", provider)
    monkeypatch.setattr(app_settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(app_settings, "TESTING", False)
    service = EmailService()
    with caplog.at_level(logging.INFO, logger="app.core.email.service"):
        service._initialize()
    return caplog.text


def test_console_in_production_logs_an_error(monkeypatch, caplog) -> None:
    text = _resolve(monkeypatch, caplog, environment="production")
    assert "Email is not configured" in text
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_console_in_development_stays_quiet(monkeypatch, caplog) -> None:
    text = _resolve(monkeypatch, caplog, environment="development")
    assert "in production" not in text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_smtp_in_production_does_not_warn(monkeypatch, caplog) -> None:
    text = _resolve(monkeypatch, caplog, environment="production", provider="smtp")
    assert "Email is not configured" not in text


def test_unknown_provider_in_production_logs_an_error(monkeypatch, caplog) -> None:
    """Unknown falls back to console, so production stays just as loud (#614)."""
    text = _resolve(monkeypatch, caplog, environment="production", provider="carrier-pigeon")
    assert "Unknown email provider 'carrier-pigeon'" in text
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_unknown_provider_outside_production_stays_a_warning(monkeypatch, caplog) -> None:
    text = _resolve(monkeypatch, caplog, environment="development", provider="carrier-pigeon")
    assert "falling back to console" in text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_env_example_documents_the_setting() -> None:
    """An operator cannot set what the example never mentions."""
    from pathlib import Path

    example = Path(__file__).resolve().parents[2] / ".env.example"
    body = example.read_text(encoding="utf-8")
    for key in ("EMAIL_PROVIDER", "EMAIL_ENABLED", "EMAIL_SMTP_HOST"):
        assert key in body, key


def _compose_env(path) -> set[str]:
    """Keys the backend service passes through, from a compose file."""
    import re

    body = path.read_text(encoding="utf-8")
    after = body.split("\n  backend:", 1)[1]
    # The next service starts at exactly two spaces + a name; anything more
    # indented still belongs to backend.
    nxt = re.search(r"^  \S", after, re.M)
    backend = after[: nxt.start()] if nxt else after
    return set(re.findall(r"^\s{6}([A-Z][A-Z0-9_]*):", backend, re.M))


@pytest.mark.parametrize("compose", ["docker-compose.prod.yml", "docker-compose.coolify.yml"])
def test_production_compose_forwards_every_email_setting(compose: str) -> None:
    """The remedy we print must be applicable where we print it.

    Neither prod compose file declares `env_file`, so a setting that is not
    listed under `environment:` never reaches the container. Telling an
    operator to set `EMAIL_PROVIDER=smtp` while the SMTP host, user and
    password stay at their defaults hands them a broken remedy (#614).
    """
    from pathlib import Path

    from app.config import Settings

    declared = {n for n in Settings.model_fields if n.startswith("EMAIL_")}
    forwarded = _compose_env(Path(__file__).resolve().parents[2] / compose)
    missing = sorted(declared - forwarded)
    assert not missing, f"{compose} does not forward: {missing}"


@pytest.mark.parametrize("compose", ["docker-compose.prod.yml", "docker-compose.coolify.yml"])
def test_boolean_email_settings_have_a_real_default(compose: str) -> None:
    """``${X:-}`` resolves to an empty string, which fails bool parsing at boot."""
    import re
    from pathlib import Path

    from app.config import Settings

    body = (Path(__file__).resolve().parents[2] / compose).read_text(encoding="utf-8")
    bools = {
        n
        for n, f in Settings.model_fields.items()
        if n.startswith("EMAIL_") and f.annotation is bool
    }
    for name in sorted(bools):
        m = re.search(rf"^\s+{name}: \$\{{{name}:-(.*?)\}}", body, re.M)
        assert m, f"{compose}: {name} not forwarded with a default"
        assert m.group(1) != "", f"{compose}: {name} defaults to empty, which fails bool parsing"


def _make_settings(**overrides):
    from app.config import MIN_SECRET_KEY_LENGTH, Settings

    kwargs = {
        "DATABASE_URL": "postgresql://user:pass@localhost/db",
        "SECRET_KEY": "a" * MIN_SECRET_KEY_LENGTH,
        "BUDGET_PUBLIC_SECRET_KEY": "a" * MIN_SECRET_KEY_LENGTH,
        "AGENDA_PUBLIC_SECRET_KEY": "a" * MIN_SECRET_KEY_LENGTH,
        "ENVIRONMENT": "development",
    }
    kwargs.update(overrides)
    return Settings(**kwargs)


def test_console_provider_in_production_boots():
    """No boot refusal (maintainer decision): production boots, loud."""
    settings = _make_settings(ENVIRONMENT="production", EMAIL_PROVIDER="console")
    assert settings.EMAIL_PROVIDER == "console"


def test_console_send_in_production_is_metadata_only_and_failed(monkeypatch, caplog) -> None:
    """Production console sends log metadata only and report FAILED (#614)."""
    import asyncio

    from app.config import settings as app_settings
    from app.core.email.providers.base import EmailMessage, EmailStatus
    from app.core.email.providers.console import ConsoleProvider, _mask_address

    monkeypatch.setattr(app_settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(app_settings, "TESTING", False)
    message = EmailMessage(
        to_email="ana.garcia@example.com",
        to_name="Ana Garcia",
        subject="Recordatorio de cita - Endodoncia 180,00",
        body_html="<p>Endodoncia 180,00</p>",
        body_text="Endodoncia 180,00",
    )
    with caplog.at_level(logging.INFO, logger="app.core.email.providers.console"):
        result = asyncio.run(ConsoleProvider().send(message))
    assert result.status == EmailStatus.FAILED
    assert not result.is_success
    assert "not configured" in (result.error_message or "")
    logged = caplog.text
    assert "ana.garcia@example.com" not in logged
    assert "Ana Garcia" not in logged
    assert "Endodoncia" not in logged
    assert "180,00" not in logged
    assert "a***@example.com" in logged
    assert _mask_address("ana.garcia@example.com") == "a***@example.com"
    assert _mask_address(None) == "unknown"


@pytest.mark.asyncio
async def test_console_send_in_development_logs_full_body_and_succeeds(monkeypatch, caplog) -> None:
    """Dev keeps the full-content log and SUCCESS (unchanged behavior)."""
    from app.config import settings as app_settings
    from app.core.email.providers.base import EmailMessage, EmailStatus
    from app.core.email.providers.console import ConsoleProvider

    monkeypatch.setattr(app_settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(app_settings, "TESTING", False)
    message = EmailMessage(
        to_email="dev@example.com",
        subject="Hello",
        body_html="<p>Hello</p>",
        body_text="Hello",
    )
    with caplog.at_level(logging.INFO, logger="app.core.email.providers.console"):
        result = await ConsoleProvider().send(message)
    assert result.status == EmailStatus.SUCCESS
    assert "Hello" in caplog.text


def test_disabled_email_in_production_boots():
    """EMAIL_ENABLED=false is the legitimate no-mail opt-out."""
    settings = _make_settings(ENVIRONMENT="production", EMAIL_ENABLED=False)
    assert settings.EMAIL_ENABLED is False


def test_smtp_provider_in_production_boots_clean():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        settings = _make_settings(ENVIRONMENT="production", EMAIL_PROVIDER="smtp")
    assert settings.EMAIL_PROVIDER == "smtp"


def test_console_provider_outside_production_boots_silently():
    """Console is the documented dev default — no warning noise on every boot."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        settings = _make_settings(ENVIRONMENT="development")
    assert settings.EMAIL_PROVIDER == "console"
