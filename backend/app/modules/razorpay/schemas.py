"""razorpay Pydantic schemas — settings only. Secrets are write-only:
the response never echoes ``key_secret``/``webhook_secret``, only
whether one is configured (``has_key_secret``/``has_webhook_secret``)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .constants import MODES

_MODE_PATTERN = "^(" + "|".join(MODES) + ")$"


class RazorpaySettingsUpdate(BaseModel):
    # Copy-pasting key_id/key_secret from the Razorpay dashboard commonly
    # brings along a trailing newline or space; Basic Auth is an exact
    # match, so an unstripped secret silently produces a 401
    # "Authentication failed" that looks identical to a wrong key.
    model_config = ConfigDict(str_strip_whitespace=True)

    mode: str | None = Field(default=None, pattern=_MODE_PATTERN)
    key_id: str | None = Field(default=None, max_length=100)
    key_secret: str | None = Field(default=None, max_length=200)
    webhook_secret: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class RazorpaySettingsResponse(BaseModel):
    mode: str
    key_id: str | None = None
    has_key_secret: bool
    has_webhook_secret: bool
    is_active: bool
    is_verified: bool
    last_verified_at: datetime | None = None
    last_webhook_received_at: datetime | None = None
    last_webhook_processed_at: datetime | None = None
    last_webhook_event_type: str | None = None
    last_webhook_error: str | None = None
    last_webhook_error_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
