"""integrations business logic: subscription + API token CRUD. Clinic-scoped."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import encrypt_password

from .models import ApiToken, WebhookSubscription

# Ramón 2026-08-21: server-side generated, shown once, never Fernet-decrypted
# back out for display (only internally, to sign a delivery).
_SECRET_BYTES = 32
# Same generator, same byte length — API tokens and webhook secrets share the
# convention. Hashed with SHA-256 (not Fernet, not bcrypt): never decrypted
# back out, and high-entropy enough that no per-hash salt is needed, only a
# fast indexable lookup by hash — see models.ApiToken docstring.
_TOKEN_BYTES = 32


def _hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


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
        for field in ("description", "target_url", "event_types"):
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
        plaintext = secrets.token_urlsafe(_TOKEN_BYTES)
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
