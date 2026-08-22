"""integrations Pydantic schemas.

``secret`` is returned ONLY from ``WebhookSubscriptionCreated`` (the
create response) — never again after, per Ramón's requirement
(secrets.token_urlsafe(32), shown once). Every other response uses
``WebhookSubscriptionResponse``, which carries no secret at all.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .triggers import SUPPORTED_EVENT_TYPES
from .url_safety import UnsafeWebhookURLError, validate_new_url


def _safe_target_url(value: str) -> str:
    """Shared SSRF check for create/update — see url_safety.py."""
    try:
        validate_new_url(value)
    except UnsafeWebhookURLError as exc:
        raise ValueError(str(exc)) from exc
    return value


class WebhookSubscriptionCreate(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    target_url: str = Field(max_length=2048)
    event_types: list[str] = Field(min_length=1)

    @field_validator("target_url")
    @classmethod
    def _target_url_is_safe(cls, value: str) -> str:
        return _safe_target_url(value)

    @field_validator("event_types")
    @classmethod
    def _known_event_types(cls, value: list[str]) -> list[str]:
        unsupported = sorted(set(value) - SUPPORTED_EVENT_TYPES)
        if unsupported:
            raise ValueError(
                f"unsupported event type(s) in Phase 1: {unsupported}. "
                f"Supported: {sorted(SUPPORTED_EVENT_TYPES)}"
            )
        return value


class WebhookSubscriptionUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    target_url: str | None = Field(default=None, max_length=2048)
    event_types: list[str] | None = Field(default=None, min_length=1)
    is_active: bool | None = None

    @field_validator("target_url")
    @classmethod
    def _target_url_is_safe(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _safe_target_url(value)

    @field_validator("event_types")
    @classmethod
    def _known_event_types(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        unsupported = sorted(set(value) - SUPPORTED_EVENT_TYPES)
        if unsupported:
            raise ValueError(
                f"unsupported event type(s) in Phase 1: {unsupported}. "
                f"Supported: {sorted(SUPPORTED_EVENT_TYPES)}"
            )
        return value


class WebhookSubscriptionResponse(BaseModel):
    id: UUID
    description: str | None
    target_url: str
    event_types: list[str]
    is_active: bool
    consecutive_failures: int
    disabled_at: datetime | None
    disabled_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookSubscriptionCreated(WebhookSubscriptionResponse):
    """Create response only — carries the plaintext secret exactly once."""

    secret: str = Field(description="Shown once. Store it now; it cannot be retrieved again.")


class ApiTokenCreate(BaseModel):
    name: str = Field(max_length=255)
    scopes: list[str] = Field(default_factory=list)


class ApiTokenResponse(BaseModel):
    id: UUID
    name: str
    scopes: list[str]
    last_used_at: datetime | None
    revoked_at: datetime | None
    revoked_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiTokenCreated(ApiTokenResponse):
    """Create response only — carries the plaintext token exactly once."""

    token: str = Field(description="Shown once. Store it now; it cannot be retrieved again.")
