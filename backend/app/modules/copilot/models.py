"""Copilot module — conversation persistence + per-clinic config.

Tables on the ``copilot`` Alembic branch:

* ``copilot_conversations`` — one chat session, linked to a core
  ``agent_sessions`` row so every tool call lands in
  ``agent_audit_logs``.
* ``copilot_messages`` — the turn-by-turn transcript in **real space**
  (the redactor tokenizes only on the way to the provider). The source
  of truth for resuming a suspended turn: an assistant ``tool_use``
  block with no matching ``tool_result`` means "awaiting confirmation".
* ``copilot_nudges`` — proactive contextual suggestions surfaced in the
  drawer (event-driven, ADR 0014 §Deferred).
* ``copilot_settings`` — per-clinic provider/model/budget, lazy-created.

Cross-module FK is limited to ``agent_sessions`` / ``clinics`` / ``users``
(all core), so the module keeps ``depends = []``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class CopilotConversation(Base, TimestampMixin):
    __tablename__ = "copilot_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Link to the core agent session so tool calls audit-trail correctly.
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Per-conversation redaction salt (#586). Beside the context blob,
    # never inside it: the blob is seeded into the redactor and logged,
    # the salt must be neither. Generated on first redactor build.
    redaction_salt: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="openai")
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CopilotMessage(Base):
    __tablename__ = "copilot_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("copilot_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # Monotonic per-conversation ordinal: assistant + tool messages in the
    # same turn share a timestamp, so order must not depend on created_at.
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # system | user | assistant | tool
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # Neutral content blocks serialized to JSON (see bridge serde).
    content: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CopilotNudge(Base):
    """A proactive, contextual suggestion surfaced in the copilot drawer
    (ADR 0014 §Deferred — event-driven nudges).

    Created by an event handler (e.g. ``appointment.cancelled`` → "fill
    the freed slot from recalls?"). The row stores ``kind`` + ``payload``
    only; the frontend renders the localized text and the chat prompt, so
    the nudge is locale-correct without storing copy. Visibility is gated
    per viewer by ``required_permission`` (NULL = anyone with chat).
    Deduped per clinic on ``dedupe_key``; expires on ``expires_at`` (a
    same-day TTL) and is filtered out thereafter — no purge needed for
    correctness.
    """

    __tablename__ = "copilot_nudges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    required_permission: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # pending | dismissed | acted
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("clinic_id", "dedupe_key", name="uq_copilot_nudge_dedupe"),)


class CopilotSettings(Base):
    __tablename__ = "copilot_settings"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="openai")
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    redaction_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # NULL → no ceiling.
    monthly_token_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_cost_limit_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Morning digest (proactivity v1 + v2): opt-in deterministic daily email.
    digest_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # digest_hour is interpreted in the clinic's IANA timezone
    # (``clinics.timezone``), not server-local (v2).
    digest_hour: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=8)
    # v2: multiple recipients. Stored as a JSONB array of user-id strings
    # rather than a join table — there's no FK, so a deleted/expelled user
    # leaves a stale id, but the task already skips ids that don't resolve
    # to an active clinic member (it must, since each recipient's role
    # scopes their digest). One email per recipient, each scoped to that
    # recipient's role permissions (RBAC parity by construction).
    digest_recipient_user_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
