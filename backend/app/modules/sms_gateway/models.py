"""sms_gateway settings model.

Provider credentials are Fernet-encrypted at rest via the shared
``app.core.email.encryption`` helpers (same scheme as whatsapp_kapso).
The log placeholder provider needs no credentials; Twilio-style
backends read the encrypted columns when they land.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic


class SmsGatewaySettings(Base, TimestampMixin):
    """Per-clinic SMS provider configuration (one row per clinic)."""

    __tablename__ = "sms_gateway_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinics.id"), unique=True, index=True, nullable=False
    )
    # Provider backend key: "log" (placeholder, default) today; "twilio"
    # and friends register under the same adapter later.
    provider: Mapped[str] = mapped_column(String(32), default="log")
    account_sid_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    clinic: Mapped[Clinic] = relationship(foreign_keys=[clinic_id])
