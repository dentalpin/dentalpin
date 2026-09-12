"""razorpay models — per-clinic Razorpay credentials + webhook health.

Secrets (key secret, webhook secret) are Fernet-encrypted at rest via
the project-wide ``app.core.email.encryption`` util, exactly like
``whatsapp_kapso``. ``key_id`` is stored in plaintext — Razorpay's own
key id is meant to be handed to the browser (Checkout.js needs it) and
is not a secret on its own.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic


class RazorpaySettings(Base, TimestampMixin):
    """Per-clinic Razorpay connection: mode + credentials + webhook health."""

    __tablename__ = "razorpay_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), unique=True, index=True)

    mode: Mapped[str] = mapped_column(String(10), default="test")  # test | live
    key_id: Mapped[str | None] = mapped_column(String(100), default=None)
    key_secret_encrypted: Mapped[str] = mapped_column(Text, default="")
    webhook_secret_encrypted: Mapped[str] = mapped_column(Text, default="")

    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Webhook health — never the payload itself, no secrets.
    last_webhook_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_webhook_processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_webhook_event_type: Mapped[str | None] = mapped_column(String(50), default=None)
    last_webhook_error: Mapped[str | None] = mapped_column(Text, default=None)
    last_webhook_error_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (Index("idx_razorpay_settings_clinic", "clinic_id"),)
