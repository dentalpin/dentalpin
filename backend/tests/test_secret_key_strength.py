"""Regression for GHSA-hcg9-cm67-2g8f: unvalidated weak SECRET_KEY.

SECRET_KEY signs JWTs (auth/service.py) and derives the Fernet key used
to encrypt SMTP passwords and Veri*Factu tax certificates at rest
(core/email/encryption.py's ``_get_fernet``). Before this fix, Pydantic
only required SECRET_KEY to be a non-empty string — a 1-character key
booted with no error and no warning.

The fix must fail hard only when ENVIRONMENT=production (an operator
mistake in the deploy that matters), and warn everywhere else, so dev/CI
setups using short stub keys keep working.
"""

from __future__ import annotations

import pytest

from app.config import MIN_SECRET_KEY_LENGTH, Settings

SHORT_KEY = "a" * (MIN_SECRET_KEY_LENGTH - 1)
STRONG_KEY = "a" * MIN_SECRET_KEY_LENGTH


def _make_settings(**overrides):
    kwargs = {
        "DATABASE_URL": "postgresql://user:pass@localhost/db",
        "SECRET_KEY": STRONG_KEY,
        "ENVIRONMENT": "development",
    }
    kwargs.update(overrides)
    return Settings(**kwargs)


def test_short_key_in_production_raises():
    with pytest.raises(ValueError, match="SECRET_KEY must be at least"):
        _make_settings(
            SECRET_KEY=SHORT_KEY,
            ENVIRONMENT="production",
            BUDGET_PUBLIC_SECRET_KEY=STRONG_KEY,
            AGENDA_PUBLIC_SECRET_KEY=STRONG_KEY,
        )


def test_short_key_outside_production_warns_but_boots():
    with pytest.warns(UserWarning, match="SECRET_KEY must be at least"):
        settings = _make_settings(SECRET_KEY=SHORT_KEY, ENVIRONMENT="development")
    assert settings.SECRET_KEY == SHORT_KEY


def test_short_key_in_test_environment_warns_but_boots():
    """CI's stub keys (e.g. ``ci-stub``) use ENVIRONMENT=test, not production."""
    with pytest.warns(UserWarning, match="SECRET_KEY must be at least"):
        settings = _make_settings(SECRET_KEY="ci-stub", ENVIRONMENT="test")
    assert settings.SECRET_KEY == "ci-stub"


def test_strong_key_in_production_boots_clean():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        settings = _make_settings(
            SECRET_KEY=STRONG_KEY,
            ENVIRONMENT="production",
            BUDGET_PUBLIC_SECRET_KEY=STRONG_KEY,
            AGENDA_PUBLIC_SECRET_KEY=STRONG_KEY,
        )
    assert settings.SECRET_KEY == STRONG_KEY


def test_missing_public_key_in_production_raises():
    """Production refuses to boot without the public-link key (#538)."""
    with pytest.raises(ValueError, match="BUDGET_PUBLIC_SECRET_KEY is required"):
        _make_settings(SECRET_KEY=STRONG_KEY, ENVIRONMENT="production")


def test_short_public_key_in_production_raises():
    with pytest.raises(ValueError, match="BUDGET_PUBLIC_SECRET_KEY must be at least"):
        _make_settings(
            SECRET_KEY=STRONG_KEY,
            ENVIRONMENT="production",
            BUDGET_PUBLIC_SECRET_KEY=SHORT_KEY,
            AGENDA_PUBLIC_SECRET_KEY=STRONG_KEY,
        )


def test_whitespace_public_key_in_production_raises():
    """Whitespace is not entropy for a production signing key (#538)."""
    with pytest.raises(ValueError, match="must not be blank or whitespace"):
        _make_settings(
            SECRET_KEY=STRONG_KEY,
            ENVIRONMENT="production",
            BUDGET_PUBLIC_SECRET_KEY=" " * MIN_SECRET_KEY_LENGTH,
            AGENDA_PUBLIC_SECRET_KEY=STRONG_KEY,
        )


@pytest.mark.parametrize(
    "value",
    [" " + STRONG_KEY, STRONG_KEY + " ", STRONG_KEY + "\n"],
)
def test_padded_public_key_in_production_raises(value: str):
    """Validation and signing must see the same production key (#538)."""
    with pytest.raises(ValueError, match="leading or trailing whitespace"):
        _make_settings(
            SECRET_KEY=STRONG_KEY,
            ENVIRONMENT="production",
            BUDGET_PUBLIC_SECRET_KEY=value,
            AGENDA_PUBLIC_SECRET_KEY=STRONG_KEY,
        )


def test_missing_public_key_outside_production_boots():
    settings = _make_settings(SECRET_KEY=STRONG_KEY, ENVIRONMENT="development")
    assert settings.BUDGET_PUBLIC_SECRET_KEY == ""
    assert settings.AGENDA_PUBLIC_SECRET_KEY == ""


def test_strong_key_outside_production_boots_clean():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        settings = _make_settings(SECRET_KEY=STRONG_KEY, ENVIRONMENT="development")
    assert settings.SECRET_KEY == STRONG_KEY


def test_agenda_key_missing_in_production_raises():
    """Production refuses to boot without the check-in key (#538)."""
    with pytest.raises(ValueError, match="AGENDA_PUBLIC_SECRET_KEY is required"):
        _make_settings(
            SECRET_KEY=STRONG_KEY,
            ENVIRONMENT="production",
            BUDGET_PUBLIC_SECRET_KEY=STRONG_KEY,
        )


def test_agenda_key_short_in_production_raises():
    with pytest.raises(ValueError, match="AGENDA_PUBLIC_SECRET_KEY must be at least"):
        _make_settings(
            SECRET_KEY=STRONG_KEY,
            ENVIRONMENT="production",
            BUDGET_PUBLIC_SECRET_KEY=STRONG_KEY,
            AGENDA_PUBLIC_SECRET_KEY=SHORT_KEY,
        )


def test_agenda_key_whitespace_in_production_raises():
    """Whitespace is not entropy for a production signing key (#538)."""
    with pytest.raises(ValueError, match="must not be blank or whitespace"):
        _make_settings(
            SECRET_KEY=STRONG_KEY,
            ENVIRONMENT="production",
            BUDGET_PUBLIC_SECRET_KEY=STRONG_KEY,
            AGENDA_PUBLIC_SECRET_KEY=" " * MIN_SECRET_KEY_LENGTH,
        )


@pytest.mark.parametrize(
    "value",
    [" " + STRONG_KEY, STRONG_KEY + " ", STRONG_KEY + "\n"],
)
def test_agenda_key_padded_in_production_raises(value: str):
    """Validation and signing must see the same production key (#538)."""
    with pytest.raises(ValueError, match="leading or trailing whitespace"):
        _make_settings(
            SECRET_KEY=STRONG_KEY,
            ENVIRONMENT="production",
            BUDGET_PUBLIC_SECRET_KEY=STRONG_KEY,
            AGENDA_PUBLIC_SECRET_KEY=value,
        )
