"""Notifications module database models (multi-channel).

Generalized from email-only to a channel-agnostic gateway:
- ``NotificationTemplate`` (was ``EmailTemplate``) carries a ``channel`` and,
  for WhatsApp, a Meta/Kapso approved-template name.
- ``CommunicationMessage`` (was ``EmailLog``) is BOTH the outbox queue row
  and the immutable-ish audit record, across every channel.
- ``NotificationPreference`` gains per-channel WhatsApp opt-in + the 24h
  session-window marker.
- ``ClinicChannelSettings`` (new) records which adapter handles which
  channel per clinic (no secrets — those live in the vendor module).
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic
    from app.modules.patients.models import Patient


class NotificationTemplate(Base, TimestampMixin):
    """Customizable notification template, per channel.

    Templates can be system-level (clinic_id=None) or per-clinic. For
    ``channel='email'`` the ``subject``/``body_html`` are used; for
    ``channel='whatsapp'`` the ``provider_template_name`` (a Meta-approved
    HSM) is used and ``variables`` holds the ordered substitution list.
    """

    __tablename__ = "notification_templates"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinics.id"), index=True, default=None
    )  # NULL = system template

    # Identification
    channel: Mapped[str] = mapped_column(String(20), default="email", index=True)
    template_key: Mapped[str] = mapped_column(String(100), index=True)
    locale: Mapped[str] = mapped_column(String(5), default="es")  # es, en

    # Email content (ignored for non-email channels)
    subject: Mapped[str | None] = mapped_column(String(255), default=None)
    body_html: Mapped[str | None] = mapped_column(Text, default=None)
    body_text: Mapped[str | None] = mapped_column(Text, default=None)

    # WhatsApp / provider-template content (ignored for email)
    provider_template_name: Mapped[str | None] = mapped_column(String(200), default=None)
    provider_template_status: Mapped[str | None] = mapped_column(
        String(20), default=None
    )  # approved, pending, rejected

    # Metadata
    variables: Mapped[dict | None] = mapped_column(JSONB, default=None)
    description: Mapped[str | None] = mapped_column(String(500), default=None)

    # Flags
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    clinic: Mapped["Clinic | None"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (
        UniqueConstraint(
            "clinic_id",
            "template_key",
            "locale",
            "channel",
            name="uq_notification_template_clinic_key_locale_channel",
        ),
        Index("idx_notification_templates_clinic", "clinic_id"),
        Index("idx_notification_templates_key", "template_key"),
    )


class NotificationPreference(Base, TimestampMixin):
    """Notification preferences for patients or users.

    Stores opt-in/opt-out settings. Either patient_id or user_id is set.
    """

    __tablename__ = "notification_preferences"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    # Subject - either patient or user
    patient_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("patients.id"), index=True, default=None
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True, default=None)

    # Channel master toggles
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # WhatsApp uses patients.phone as the number. Opt-out, like email: an
    # explicit False blocks; a missing row means the patient is reachable.
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    whatsapp_opt_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # SMS uses patients.phone as the number (E.164). Opt-out, like email:
    # an explicit False blocks; a missing row means the patient is
    # reachable. sms_opt_in_at mirrors whatsapp_opt_in_at for the
    # consent trail.
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_opt_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Last inbound message timestamp — opens the 24h free-form session window.
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Per-type preferences (channel-agnostic opt-in)
    preferences: Mapped[dict] = mapped_column(
        JSONB,
        default=lambda: {
            "appointment_confirmation": True,
            "appointment_reminder": True,
            "appointment_cancelled": True,
            "budget_sent": True,
            "budget_accepted": True,
            "welcome": True,
        },
    )

    # Language preference
    preferred_locale: Mapped[str] = mapped_column(String(5), default="es")

    # Relationships
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])
    patient: Mapped["Patient | None"] = relationship(foreign_keys=[patient_id])

    __table_args__ = (
        UniqueConstraint("clinic_id", "patient_id", name="uq_notification_pref_clinic_patient"),
        UniqueConstraint("clinic_id", "user_id", name="uq_notification_pref_clinic_user"),
        Index("idx_notification_preferences_clinic", "clinic_id"),
        Index("idx_notification_preferences_patient", "patient_id"),
        Index("idx_notification_preferences_user", "user_id"),
    )


class ClinicNotificationSettings(Base, TimestampMixin):
    """Clinic-level notification settings.

    Per-type ``settings`` answers *which events fire* (``enabled`` /
    ``auto_send`` / ``hours_before``). The clinic-wide channel columns answer
    *which channel they use*: ``preferred_channel`` is the default wire for
    every auto-send, ``fallback_enabled`` allows the other installed channel
    when the preferred one is not viable, and ``manual_channels`` drives which
    Send buttons the rest of the app renders. Defaults stay email-only so
    existing clinics are unchanged until an admin picks WhatsApp.
    """

    __tablename__ = "clinic_notification_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), unique=True, index=True)

    # Clinic-wide channel configuration (not per-type).
    preferred_channel: Mapped[str] = mapped_column(
        String(20), default="email", server_default="email"
    )  # 'email' | 'whatsapp'
    fallback_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    # Max SMS parts queued per clinic per UTC day (cost guard — SMS is
    # billed per message, unlike email). Enforced in enqueue; admins
    # adjust it via clinic settings. No equivalent cap exists for
    # email/whatsapp (flat-rate transports).
    sms_daily_limit: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    manual_channels: Mapped[list] = mapped_column(
        JSONB, default=lambda: ["email"], server_default=text("'[\"email\"]'::jsonb")
    )  # subset of installed channels

    settings: Mapped[dict] = mapped_column(
        JSONB,
        default=lambda: {
            "appointment_confirmation": {"auto_send": True, "enabled": True},
            "appointment_cancelled": {"auto_send": True, "enabled": True},
            "appointment_reminder": {"auto_send": True, "enabled": True, "hours_before": 24},
            "budget_sent": {"auto_send": False, "enabled": True},
            "budget_accepted": {"auto_send": True, "enabled": True},
            "welcome": {"auto_send": False, "enabled": True},
            "invoice_sent": {"auto_send": False, "enabled": True},
            "budget_reminder": {"auto_send": True, "enabled": True},
            "recall_reminder": {"auto_send": True, "enabled": True},
        },
    )

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (Index("idx_clinic_notification_settings_clinic", "clinic_id"),)


class ClinicChannelSettings(Base, TimestampMixin):
    """Which adapter handles which channel for a clinic. NO secrets here.

    Generic and reusable by any future vendor (Twilio, telephony). Vendor
    credentials live in the vendor module's own table.
    """

    __tablename__ = "clinic_channel_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    channel: Mapped[str] = mapped_column(String(20))  # email, whatsapp, ...
    adapter_name: Mapped[str] = mapped_column(String(50))  # e.g. "whatsapp_kapso"
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict | None] = mapped_column(JSONB, default=None)  # non-secret display config

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (
        UniqueConstraint("clinic_id", "channel", name="uq_clinic_channel_settings_clinic_channel"),
        Index("idx_clinic_channel_settings_clinic", "clinic_id"),
    )


class ClinicSmtpSettings(Base, TimestampMixin):
    """SMTP configuration per clinic (Fernet-encrypted password)."""

    __tablename__ = "clinic_smtp_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), unique=True, index=True)

    provider: Mapped[str] = mapped_column(String(20), default="smtp")  # smtp, console, disabled

    host: Mapped[str | None] = mapped_column(String(255), default=None)
    port: Mapped[int] = mapped_column(Integer, default=587)
    username: Mapped[str | None] = mapped_column(String(255), default=None)
    password_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    use_tls: Mapped[bool] = mapped_column(Boolean, default=True)
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=False)

    from_email: Mapped[str | None] = mapped_column(String(255), default=None)
    from_name: Mapped[str | None] = mapped_column(String(255), default=None)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (Index("idx_clinic_smtp_settings_clinic", "clinic_id"),)


class CommunicationMessage(Base, TimestampMixin):
    """Outbox queue row AND audit record for one outbound message.

    Lifecycle: ``queued`` → ``sending`` → ``sent`` → (``delivered``/``read``)
    or ``failed`` (retried up to ``max_attempts``) or ``skipped`` (consent /
    no viable channel). One source of truth across all channels.
    """

    __tablename__ = "communication_messages"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    # Routing
    channel: Mapped[str] = mapped_column(String(20), default="email")
    # outbound (we send) | inbound (patient replied) — the conversation thread.
    direction: Mapped[str] = mapped_column(String(20), default="outbound")
    to_address: Mapped[str] = mapped_column(String(255))  # email or E.164 phone (the counterparty)
    patient_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("patients.id"), index=True, default=None
    )

    # Content reference
    template_key: Mapped[str] = mapped_column(String(100))
    message_kind: Mapped[str] = mapped_column(String(20), default="template")  # template | session
    subject: Mapped[str | None] = mapped_column(String(255), default=None)
    # Literal text for inbound messages and free-form (session) outbound sends.
    # Template outbound renders from the template, so this stays NULL there.
    body_text: Mapped[str | None] = mapped_column(Text, default=None)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(20), default="queued", index=True
    )  # queued, sending, sent, failed, skipped, delivered, read
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Provider info
    provider: Mapped[str | None] = mapped_column(String(50), default=None)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    # Idempotency
    dedup_key: Mapped[str | None] = mapped_column(String(200), default=None)

    # Timestamps (created_at/updated_at via TimestampMixin)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Event tracking
    triggered_by_event: Mapped[str | None] = mapped_column(String(100), default=None)
    triggered_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), index=True, default=None
    )

    # Sanitized template context for debugging
    context_data: Mapped[dict | None] = mapped_column(JSONB, default=None)

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])
    patient: Mapped["Patient | None"] = relationship(foreign_keys=[patient_id])

    __table_args__ = (
        Index("idx_communication_messages_clinic", "clinic_id"),
        Index("idx_communication_messages_status", "status"),
        Index("idx_communication_messages_created_at", "created_at"),
        Index("idx_communication_messages_patient", "patient_id"),
        Index("idx_communication_messages_template", "template_key"),
        # Drives the dispatch poll.
        Index("idx_communication_messages_dispatch", "status", "next_attempt_at"),
        # Conversation thread read: messages for a patient on a channel, in order.
        Index(
            "idx_communication_messages_thread",
            "clinic_id",
            "patient_id",
            "channel",
            "created_at",
        ),
        # Idempotency: at most one row per (clinic, dedup_key) when set.
        Index(
            "uq_communication_messages_dedup",
            "clinic_id",
            "dedup_key",
            unique=True,
            postgresql_where=text("dedup_key IS NOT NULL"),
        ),
    )
