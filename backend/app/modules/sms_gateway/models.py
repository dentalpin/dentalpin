"""sms_gateway models — per-clinic SMS provider config + a send log for the placeholder.

Secrets are Fernet-encrypted at rest via the project-wide
``app.core.email.encryption`` util (same pattern as ``whatsapp_kapso``).
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class SmsGatewaySettings(Base, TimestampMixin):
    """Per-clinic SMS provider connection. ``provider_name`` selects which
    :class:`~.providers.SmsProvider` implementation handles sends — starts
    at ``"placeholder"`` until a real provider is chosen and configured.
    """

    __tablename__ = "sms_gateway_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), unique=True, index=True)

    provider_name: Mapped[str] = mapped_column(String(50), default="placeholder")
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    sender_id: Mapped[str | None] = mapped_column(String(50))
    base_url: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)


class SmsOutboxLog(Base, TimestampMixin):
    """Every send attempt, including ones the placeholder provider only
    logged instead of actually sending — so nothing is silently lost
    while no real provider is configured yet.
    """

    __tablename__ = "sms_outbox_log"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    to_address: Mapped[str] = mapped_column(String(32))
    body: Mapped[str] = mapped_column(Text)
    provider_name: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20))  # sent | failed | skipped
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
