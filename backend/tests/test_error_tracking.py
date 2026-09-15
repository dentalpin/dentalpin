"""Error tracking helper: DSN-gated, never raises, PII-free."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

from app.core.log_context import setup_error_tracking


def test_no_dsn_is_noop() -> None:
    assert setup_error_tracking(dsn="") is False
    assert setup_error_tracking() is False


def test_missing_sdk_is_noop(monkeypatch) -> None:
    """Without sentry_sdk installed, a configured DSN logs and stays off."""
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    assert setup_error_tracking(dsn="https://key@sentry.io/1") is False


def test_successful_init_returns_true(monkeypatch) -> None:
    """With sentry_sdk present and init succeeding, tracking turns on."""
    mock_sdk = MagicMock()
    monkeypatch.setitem(sys.modules, "sentry_sdk", mock_sdk)
    assert setup_error_tracking(dsn="https://key@sentry.io/1") is True
    mock_sdk.init.assert_called_once()
    kwargs = mock_sdk.init.call_args.kwargs
    assert kwargs["send_default_pii"] is False
    assert kwargs["dsn"] == "https://key@sentry.io/1"
