"""integrations business logic: subscription + API token CRUD. Clinic-scoped.

``target_url`` SSRF validation lives here, not in a Pydantic
validator (schemas.py) — a validator can't ``await``, and the check
needs the event loop's own resolver (url_safety.py).
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import encrypt_password
from app.core.webhooks.url_safety import validate_new_url

from .models import ApiToken, WebhookSubscription

# Server-side generated, shown once, never Fernet-decrypted back out for
# display (only internally, to sign a delivery).
_SECRET_BYTES = 32
# Same generator, same byte length — API tokens and webhook secrets share the
# convention. Hashed with SHA-256 (not Fernet, not bcrypt): never decrypted
# back out, and high-entropy enough that no per-hash salt is needed, only a
# fast indexable lookup by hash — see models.ApiToken docstring.
_TOKEN_BYTES = 32
# Recognizable prefix so secret-scanning tools (and humans skimming a
# leaked log) can recognize a dentalpin API token on sight, same idea
# as Stripe's `sk_`/GitHub's `ghp_`.
_TOKEN_PREFIX = "dp_"

# Per-token fixed-window rate limits (issue #65 §2: "per token, per minute
# + per day, surfaced in headers"), enforced at ``authenticate_token`` so
# every ApiToken consumer (public API, MCP) shares them. In-memory per
# process — a multi-worker deployment shares nothing here; documented
# limitation, same as any other in-process limiter.
RATE_LIMIT_PER_MINUTE = 60
RATE_LIMIT_PER_DAY = 1000
_WINDOW_SECONDS_MINUTE = 60
_WINDOW_SECONDS_DAY = 86400


class RateLimitError(Exception):
    """Raised when a token exceeds its fixed-window allowance."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__()


class _RateWindow:
    __slots__ = ("start", "count")

    def __init__(self) -> None:
        self.start = int(time.time())
        self.count = 0


# token_id -> per-window counters. Bounded by the number of tokens a clinic
# issues; entries are reset (not deleted) on window rollover so this never
# grows unboundedly.
_rate_windows: dict[UUID, dict[str, _RateWindow]] = {}


def _check_rate_limit(token_id: UUID) -> dict[str, str]:
    """Fixed-window check; raises ``RateLimitError`` when over. Returns
    the ``X-RateLimit-*`` header values for the current window."""
    now = int(time.time())
    windows = _rate_windows.setdefault(token_id, {})

    minute = windows.setdefault("minute", _RateWindow())
    day = windows.setdefault("day", _RateWindow())

    if now - minute.start >= _WINDOW_SECONDS_MINUTE:
        minute.start, minute.count = now, 0
    if now - day.start >= _WINDOW_SECONDS_DAY:
        day.start, day.count = now, 0

    minute.count += 1
    day.count += 1

    if minute.count > RATE_LIMIT_PER_MINUTE or day.count > RATE_LIMIT_PER_DAY:
        raise RateLimitError(retry_after_seconds=_WINDOW_SECONDS_MINUTE)

    return {
        "X-RateLimit-Limit-Minute": str(RATE_LIMIT_PER_MINUTE),
        "X-RateLimit-Remaining-Minute": str(RATE_LIMIT_PER_MINUTE - minute.count),
        "X-RateLimit-Limit-Day": str(RATE_LIMIT_PER_DAY),
        "X-RateLimit-Remaining-Day": str(RATE_LIMIT_PER_DAY - day.count),
        "X-RateLimit-Reset": str(minute.start + _WINDOW_SECONDS_MINUTE),
    }


def _hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


@dataclass
class AuthenticatedApiToken:
    """Result of a successful ``authenticate_token``: the token row plus the
    rate-limit headers for the request window."""

    token: ApiToken
    rate_headers: dict[str, str]


class IntegrationsService:
    @staticmethod
    async def list_subscriptions(db: AsyncSession, clinic_id: UUID) -> list[WebhookSubscription]:
        result = await db.execute(
            select(WebhookSubscription)
            .where(WebhookSubscription.clinic_id == clinic_id)
            .order_by(WebhookSubscription.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_subscription(
        db: AsyncSession, clinic_id: UUID, subscription_id: UUID
    ) -> WebhookSubscription | None:
        return (
            await db.execute(
                select(WebhookSubscription).where(
                    WebhookSubscription.id == subscription_id,
                    WebhookSubscription.clinic_id == clinic_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def create_subscription(
        db: AsyncSession, clinic_id: UUID, data: dict
    ) -> tuple[WebhookSubscription, str]:
        """Returns ``(subscription, plaintext_secret)`` — the caller must
        hand the secret to the response and never persist/log it."""
        await validate_new_url(data["target_url"])
        plaintext_secret = secrets.token_urlsafe(_SECRET_BYTES)
        subscription = WebhookSubscription(
            clinic_id=clinic_id,
            description=data.get("description"),
            target_url=data["target_url"],
            event_types=data["event_types"],
            secret_encrypted=encrypt_password(plaintext_secret),
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
        return subscription, plaintext_secret

    @staticmethod
    async def update_subscription(
        db: AsyncSession, subscription: WebhookSubscription, data: dict
    ) -> WebhookSubscription:
        if "target_url" in data and data["target_url"] is not None:
            await validate_new_url(data["target_url"])
        # ``description`` is the only nullable field of the three — it uses
        # ``if field in data`` (not ``data.get(field) is not None``) so it
        # can actually be cleared to null: the router sends
        # `exclude_unset=True`, so a field's *absence* means "leave alone"
        # but its presence as `null` means "clear it", and the old
        # `is not None` check could never distinguish the two.
        # `target_url`/`event_types` are non-nullable columns —
        # `null` for either would violate the DB constraint, not clear
        # anything, so they stay on the narrower "provided and non-null"
        # check.
        if "description" in data:
            subscription.description = data["description"]
        for field in ("target_url", "event_types"):
            if data.get(field) is not None:
                setattr(subscription, field, data[field])
        if data.get("is_active") is True and not subscription.is_active:
            # Re-enabling clears the auto-disable circuit breaker.
            subscription.consecutive_failures = 0
            subscription.disabled_at = None
            subscription.disabled_reason = None
        if "is_active" in data and data["is_active"] is not None:
            subscription.is_active = data["is_active"]
        await db.commit()
        await db.refresh(subscription)
        return subscription

    @staticmethod
    async def delete_subscription(db: AsyncSession, subscription: WebhookSubscription) -> None:
        await db.delete(subscription)
        await db.commit()

    @staticmethod
    async def list_tokens(db: AsyncSession, clinic_id: UUID) -> list[ApiToken]:
        result = await db.execute(
            select(ApiToken)
            .where(ApiToken.clinic_id == clinic_id)
            .order_by(ApiToken.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_token(db: AsyncSession, clinic_id: UUID, token_id: UUID) -> ApiToken | None:
        return (
            await db.execute(
                select(ApiToken).where(
                    ApiToken.id == token_id,
                    ApiToken.clinic_id == clinic_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def create_token(db: AsyncSession, clinic_id: UUID, data: dict) -> tuple[ApiToken, str]:
        """Returns ``(token, plaintext)`` — the caller must hand the
        plaintext to the response and never persist/log it."""
        plaintext = _TOKEN_PREFIX + secrets.token_urlsafe(_TOKEN_BYTES)
        token = ApiToken(
            clinic_id=clinic_id,
            name=data["name"],
            token_hash=_hash_token(plaintext),
            scopes=data.get("scopes") or [],
        )
        db.add(token)
        await db.commit()
        await db.refresh(token)
        return token, plaintext

    @staticmethod
    async def revoke_token(
        db: AsyncSession, token: ApiToken, reason: str | None = None
    ) -> ApiToken:
        token.revoked_at = datetime.now(UTC)
        token.revoked_reason = reason
        await db.commit()
        await db.refresh(token)
        return token

    @staticmethod
    async def authenticate_token(db: AsyncSession, plaintext: str) -> AuthenticatedApiToken | None:
        """Resolve an API-token plaintext to its active token state.

        Returns ``None`` for an unknown prefix, an unknown hash, or a
        revoked token — callers decide how to surface rejection. On
        success the shared per-token fixed-window rate limit is enforced
        (raises ``RateLimitError`` when over) and ``last_used_at`` is
        stamped on the row; the caller owns the commit, so the stamp is
        committed with whichever session/success path the consumer uses.
        Single shared entry point for every token consumer (the public
        data-read API, the mcp module, ...).
        """
        if not isinstance(plaintext, str) or not plaintext.startswith(_TOKEN_PREFIX):
            return None
        token = (
            await db.execute(select(ApiToken).where(ApiToken.token_hash == _hash_token(plaintext)))
        ).scalar_one_or_none()
        if token is None or token.revoked_at is not None:
            return None
        rate_headers = _check_rate_limit(token.id)
        token.last_used_at = datetime.now(UTC)
        return AuthenticatedApiToken(token=token, rate_headers=rate_headers)
