"""integrations module database models.

``WebhookSubscription`` is the clinic-owned config row (target URL,
event types, signing secret). ``WebhookDelivery`` is BOTH the outbox
queue row and the audit record for one delivery attempt — same split
as ``notifications.models.CommunicationMessage`` (see
[[../../../../../notes/dentalpin/CLAUDE.md]] "Outbox/retry/DLQ
precedent" for the shape this mirrors).
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic


class WebhookSubscription(Base, TimestampMixin):
    """A clinic's subscription to one or more event types.

    ``secret_encrypted`` is Fernet-derived-from-``SECRET_KEY`` (5th
    consumer of ``app.core.email.encryption._get_fernet`` — Ramón
    2026-08-21, see notes/dentalpin/65-integrations-api.md "Resolved
    (was Genuinely open)"). The plaintext secret is generated
    server-side and shown once on creation; it is never returned again,
    only decrypted internally to sign a delivery.

    Auto-disabled after ``MAX_CONSECUTIVE_FAILURES`` (issue #65 §1) —
    a per-subscription concept ``CommunicationMessage`` has no
    equivalent of, since that outbox has no notion of a "subscriber"
    to disable, only a per-message terminal state.
    """

    __tablename__ = "webhook_subscriptions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    description: Mapped[str | None] = mapped_column(String(255), default=None)
    target_url: Mapped[str] = mapped_column(String(2048))
    # Ordered list of EventType strings this subscription wants delivered.
    event_types: Mapped[list[str]] = mapped_column(JSONB)
    secret_encrypted: Mapped[str] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    disabled_reason: Mapped[str | None] = mapped_column(String(255), default=None)

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])


class WebhookDelivery(Base, TimestampMixin):
    """Outbox queue row AND audit record for one webhook delivery attempt.

    Lifecycle: ``queued`` -> ``sending`` -> ``sent`` or ``failed``
    (retried up to ``max_attempts``, same backoff formula as
    ``CommunicationMessage``: ``min(60 * 2**(attempts-1), 3600)``).
    """

    __tablename__ = "webhook_deliveries"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    subscription_id: Mapped[UUID] = mapped_column(
        ForeignKey("webhook_subscriptions.id"), index=True
    )
    # Denormalized for queries/audit without a join, same as
    # CommunicationMessage.clinic_id.
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    event_type: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)

    status: Mapped[str] = mapped_column(
        String(20), default="queued", index=True
    )  # queued, sending, sent, failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    response_status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    subscription: Mapped["WebhookSubscription"] = relationship(foreign_keys=[subscription_id])
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])


class ApiToken(Base, TimestampMixin):
    """A bearer token issued to a clinic for third-party automations.

    ``token_hash`` is SHA-256 of the plaintext, not bcrypt: the token is
    a high-entropy ``secrets.token_urlsafe(32)`` value (same generator
    as ``WebhookSubscription``'s signing secret), never a human-chosen
    password, so it needs no slow/salted hash — only a fast, indexable
    lookup by hash, which bcrypt's per-hash random salt can't give.
    Plaintext is shown once, at creation, and never stored or returned
    again.

    Revocation mirrors ``WebhookSubscription``'s own
    ``disabled_at``/``disabled_reason`` shape (soft revoke, not delete)
    rather than a new pattern.

    No endpoint depends on this yet (issue #65, Phase 1 per Ramón's
    2026-08-21 email) — the public data-read API that will consume it
    is a follow-up PR.
    """

    __tablename__ = "api_tokens"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    name: Mapped[str] = mapped_column(String(255))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Ordered list of scope strings, e.g. "patients:read" (issue #65 §2/§11).
    # Not yet enforced anywhere — no consumer endpoint exists in Phase 1.
    scopes: Mapped[list[str]] = mapped_column(JSONB)

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_reason: Mapped[str | None] = mapped_column(String(255), default=None)

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])
