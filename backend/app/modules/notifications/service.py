"""Notifications module business logic."""

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailResult, email_service
from app.core.i18n_names import catalog_name
from app.core.pdf_locales import LOCALE_BY_LANG, format_pdf_date
from app.core.utils.currency import format_currency
from app.core.utils.dates import clinic_zone

from .channels import Channel, channel_registry
from .models import (
    ClinicNotificationSettings,
    ClinicSmtpSettings,
    CommunicationMessage,
    NotificationPreference,
    NotificationTemplate,
)

# Default locale used for patient-facing communications when neither a
# clinic preference nor a patient preference is set. Matches the
# project's primary user base (Spain).
DEFAULT_COMMUNICATION_LOCALE = "es"


async def resolve_clinic_communication_locale(
    db: AsyncSession,
    clinic_id: UUID,
) -> str:
    """Read ``clinics.settings.communication_language`` for the given
    clinic. Falls back to :data:`DEFAULT_COMMUNICATION_LOCALE` when the
    clinic row is missing or the key isn't set.

    Used as the default locale for outbound communications — patient
    preferences (``NotificationPreference.preferred_locale``) override
    when present.
    """
    row = (
        await db.execute(
            text("SELECT settings FROM clinics WHERE id = :id"),
            {"id": clinic_id},
        )
    ).first()
    if not row:
        return DEFAULT_COMMUNICATION_LOCALE
    settings = row.settings or {}
    lang = settings.get("communication_language") if isinstance(settings, dict) else None
    return lang or DEFAULT_COMMUNICATION_LOCALE


async def resolve_communication_locale(
    db: AsyncSession,
    clinic_id: UUID,
    prefs: NotificationPreference | None,
) -> str:
    """The locale a patient's message renders in: the clinic default,
    overridden by the patient's ``preferred_locale``.

    The gateway picks the template with it; a context builder that formats
    for the locale (money, #1133) must use the same answer.
    """
    if prefs is not None and prefs.preferred_locale:
        return prefs.preferred_locale
    return await resolve_clinic_communication_locale(db, clinic_id)


async def resolve_patient_communication_locale(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID,
) -> str:
    """:func:`resolve_communication_locale` for a patient id."""
    prefs = await NotificationService.get_patient_preferences(db, clinic_id, patient_id)
    return await resolve_communication_locale(db, clinic_id, prefs)


Money = Callable[[Decimal | float | int | None], str | None]


def money_formatter(clinic, locale: str) -> Money:
    """Format amounts for a message context in the clinic's currency (#1133).

    Same formatter and locale map as the PDFs: ``format_currency`` with
    ``clinic.currency`` and the Babel locale of the message's language, so
    an es email reads ``1.300,00 €``, an en one ``€1,300.00`` and an INR
    clinic gets ``₹``. Templates render the string as is — they never add
    a currency symbol of their own. ``None`` stays ``None``.
    """
    currency = clinic.currency if clinic and clinic.currency else "EUR"
    babel_locale = LOCALE_BY_LANG.get(locale, LOCALE_BY_LANG[DEFAULT_COMMUNICATION_LOCALE])

    def money(amount: Decimal | float | int | None) -> str | None:
        if amount is None:
            return None
        return format_currency(amount, currency, babel_locale)

    return money


logger = logging.getLogger(__name__)


class ManagedConsentError(Exception):
    """A manual preference change would bypass consent managed by verified evidence."""


class NotificationService:
    """Service for managing notifications and sending emails."""

    # ========================================================================
    # Email Template Management
    # ========================================================================

    @staticmethod
    async def list_templates(
        db: AsyncSession,
        clinic_id: UUID,
        page: int = 1,
        page_size: int = 20,
        locale: str | None = None,
        include_system: bool = True,
    ) -> tuple[list[NotificationTemplate], int]:
        """List email templates for a clinic.

        Returns clinic-specific templates and optionally system templates.
        """
        # Build base query
        conditions = []

        if include_system:
            # Include system templates and clinic templates
            conditions.append(
                (NotificationTemplate.clinic_id == clinic_id)
                | (NotificationTemplate.clinic_id.is_(None))
            )
        else:
            conditions.append(NotificationTemplate.clinic_id == clinic_id)

        if locale:
            conditions.append(NotificationTemplate.locale == locale)

        # Count total
        count_query = select(func.count()).select_from(NotificationTemplate)
        for condition in conditions:
            count_query = count_query.where(condition)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Get items
        query = select(NotificationTemplate).order_by(
            NotificationTemplate.template_key, NotificationTemplate.locale, NotificationTemplate.id
        )
        for condition in conditions:
            query = query.where(condition)

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    @staticmethod
    async def get_template(
        db: AsyncSession,
        clinic_id: UUID | None,
        template_key: str,
        locale: str = "es",
        channel: str = "email",
        *,
        exact_locale: bool = False,
        require_text: bool = False,
    ) -> NotificationTemplate | None:
        """Resolve the active clinic row, then the matching system row.

        Priority: clinic-specific > system template. Within each tier a
        regional locale falls back to its base language (``pt-BR`` -> ``pt``),
        like the file template loader (#1136). WhatsApp provider templates are
        approved per language and sent with the message locale, so that
        channel, and ``exact_locale=True`` callers, match the locale exactly.
        """
        locales = [locale]
        base = locale.split("-", 1)[0]
        if not exact_locale and channel != "whatsapp" and base != locale:
            locales.append(base)

        owners = [NotificationTemplate.clinic_id == clinic_id] if clinic_id is not None else []
        owners.append(NotificationTemplate.clinic_id.is_(None))
        for owner in owners:
            for candidate in locales:
                result = await db.execute(
                    select(NotificationTemplate).where(
                        owner,
                        NotificationTemplate.template_key == template_key,
                        NotificationTemplate.locale == candidate,
                        NotificationTemplate.channel == channel,
                        NotificationTemplate.is_active == True,  # noqa: E712
                    )
                )
                template = result.scalar_one_or_none()
                if template and (not require_text or template.body_text):
                    return template
        return None

    @staticmethod
    async def get_clinic_template(
        db: AsyncSession, clinic_id: UUID, template_key: str, locale: str, channel: str
    ) -> NotificationTemplate | None:
        """Look up an exact clinic key, including inactive rows."""
        return await db.scalar(
            select(NotificationTemplate).where(
                NotificationTemplate.clinic_id == clinic_id,
                NotificationTemplate.template_key == template_key,
                NotificationTemplate.locale == locale,
                NotificationTemplate.channel == channel,
            )
        )

    @staticmethod
    async def get_template_by_id(
        db: AsyncSession,
        clinic_id: UUID,
        template_id: UUID,
    ) -> NotificationTemplate | None:
        """Get a template by ID."""
        result = await db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.id == template_id,
                (NotificationTemplate.clinic_id == clinic_id)
                | (NotificationTemplate.clinic_id.is_(None)),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_template(
        db: AsyncSession,
        clinic_id: UUID,
        data: dict,
    ) -> NotificationTemplate:
        """Create a new email template for a clinic."""
        template = NotificationTemplate(
            clinic_id=clinic_id,
            is_system=False,
            **data,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)
        return template

    @staticmethod
    async def update_template(
        db: AsyncSession,
        template: NotificationTemplate,
        data: dict,
    ) -> NotificationTemplate:
        """Update an email template."""
        if template.is_system:
            raise ValueError("Cannot modify system templates")

        for key, value in data.items():
            if value is not None:
                setattr(template, key, value)

        await db.commit()
        await db.refresh(template)
        return template

    @staticmethod
    async def delete_template(
        db: AsyncSession,
        template: NotificationTemplate,
    ) -> None:
        """Delete an email template."""
        if template.is_system:
            raise ValueError("Cannot delete system templates")

        await db.delete(template)
        await db.commit()

    @staticmethod
    async def upsert_provider_template(
        db: AsyncSession,
        clinic_id: UUID,
        *,
        template_key: str,
        locale: str,
        provider_template_name: str,
        provider_template_status: str,
        channel: str = "whatsapp",
    ) -> NotificationTemplate:
        """Map a notification type to a provider (e.g. WhatsApp HSM) template.

        Public seam so a vendor module (whatsapp_kapso) can register the
        approved-template mapping the gateway resolves, without touching the
        notifications tables directly. Idempotent per
        ``(clinic, key, locale, channel)``.
        """
        tmpl = (
            await db.execute(
                select(NotificationTemplate).where(
                    NotificationTemplate.clinic_id == clinic_id,
                    NotificationTemplate.template_key == template_key,
                    NotificationTemplate.locale == locale,
                    NotificationTemplate.channel == channel,
                )
            )
        ).scalar_one_or_none()
        if tmpl is None:
            tmpl = NotificationTemplate(
                clinic_id=clinic_id,
                template_key=template_key,
                locale=locale,
                channel=channel,
                is_system=False,
                is_active=True,
            )
            db.add(tmpl)
        tmpl.provider_template_name = provider_template_name
        tmpl.provider_template_status = provider_template_status
        tmpl.is_active = True
        await db.commit()
        await db.refresh(tmpl)
        return tmpl

    # ========================================================================
    # Notification Preferences
    # ========================================================================

    @staticmethod
    async def get_patient_preferences(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
    ) -> NotificationPreference | None:
        """Get notification preferences for a patient."""
        result = await db.execute(
            select(NotificationPreference)
            .where(
                NotificationPreference.clinic_id == clinic_id,
                NotificationPreference.patient_id == patient_id,
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create_patient_preferences(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        *,
        commit: bool = True,
    ) -> NotificationPreference:
        """Get or create notification preferences for a patient."""
        prefs = await NotificationService.get_patient_preferences(db, clinic_id, patient_id)
        if prefs:
            return prefs

        # Create default preferences. Two first reads for the same patient
        # (two tabs, an inbound message) race on
        # uq_notification_pref_clinic_patient; the loser reads the winner's row.
        prefs = NotificationPreference(
            clinic_id=clinic_id,
            patient_id=patient_id,
        )
        try:
            async with db.begin_nested():
                db.add(prefs)
        except IntegrityError:
            existing = await NotificationService.get_patient_preferences(db, clinic_id, patient_id)
            if existing is None:
                raise
            return existing
        if commit:
            await db.commit()
            await db.refresh(prefs)
        return prefs

    @staticmethod
    async def lock_whatsapp_patient(db: AsyncSession, clinic_id: UUID, patient_id: UUID):
        from app.modules.patients.models import Patient

        return await db.scalar(
            select(Patient)
            .where(Patient.clinic_id == clinic_id, Patient.id == patient_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    @staticmethod
    async def cancel_pending_whatsapp(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> None:
        await db.execute(
            update(CommunicationMessage)
            .where(
                CommunicationMessage.clinic_id == clinic_id,
                CommunicationMessage.patient_id == patient_id,
                CommunicationMessage.channel == Channel.WHATSAPP,
                CommunicationMessage.direction == "outbound",
                CommunicationMessage.status == "awaiting_manual",
            )
            .values(status="skipped", next_attempt_at=None)
        )

    @staticmethod
    def contact_binding(patient, address: str) -> str:
        """Fingerprint of a verified destination, scoped to the patient.

        It only detects that the address changed since it was verified. The
        address already sits in the patient row, so a secret adds no
        protection, and keying it would silently stop delivery to every
        enrolled patient whenever SECRET_KEY is rotated.
        """
        normalized = "".join(address.split()).casefold()
        return hashlib.sha256(f"{patient.id}:{normalized}".encode()).hexdigest()

    @staticmethod
    def verified_consent_allows(
        prefs: NotificationPreference | None,
        patient,
        channel: str,
        notification_type: str,
    ) -> bool:
        if prefs is None or prefs.verified_consents is None:
            return True
        if patient is None or patient.status != "active":
            return False
        projection = prefs.verified_consents
        # Only appointment reminders are gated by a purpose for now; widening
        # the purpose vocabulary is the scope of #917.
        if notification_type == "appointment_reminder" and not projection.get(notification_type):
            return False
        if channel not in ("email", "sms", "whatsapp"):
            return False
        address = patient.email if channel == "email" else patient.phone
        return bool(
            address
            and projection.get(channel) == NotificationService.contact_binding(patient, address)
        )

    @staticmethod
    async def require_verified_consent(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> None:
        """Enroll once. Caller owns the patient lock and the transaction."""
        prefs = await NotificationService.get_or_create_patient_preferences(
            db, clinic_id, patient_id, commit=False
        )
        if prefs.verified_consents is None:
            await NotificationService.set_verified_consents(
                db, clinic_id, patient_id, {}, at=datetime.now(UTC)
            )

    @staticmethod
    async def set_verified_consents(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        projection: dict[str, str | bool],
        *,
        at: datetime,
        apply_all: bool = False,
    ) -> None:
        """Apply verified evidence and suppress pending delivery in the caller's transaction.

        The caller holds the patient lock and owns commit or rollback.
        """
        prefs = await NotificationService.get_or_create_patient_preferences(
            db, clinic_id, patient_id, commit=False
        )
        previous = prefs.verified_consents or {}
        prefs.verified_consents = projection
        # appointment_reminder is hardcoded here on purpose: it is the only
        # purpose in scope until #917 generalizes the purpose mapping.
        prefs.preferences = {
            **(prefs.preferences or {}),
            "appointment_reminder": bool(projection.get("appointment_reminder")),
        }
        for channel in ("email", "sms", "whatsapp"):
            # Keep any separate delivery disable when the verified grant did
            # not change, e.g. when withdrawing a different channel.
            if (
                apply_all
                or not projection.get(channel)
                or previous.get(channel) != projection.get(channel)
            ):
                setattr(prefs, f"{channel}_enabled", bool(projection.get(channel)))
                if channel != "email":
                    setattr(prefs, f"{channel}_opt_in_at", at if projection.get(channel) else None)
        blocked_channels = [
            channel
            for channel in ("email", "sms", "whatsapp")
            if not projection.get(channel)
            or (previous.get(channel) and previous[channel] != projection[channel])
        ]
        affected = CommunicationMessage.channel.in_(blocked_channels) | (
            CommunicationMessage.channel.not_in(("email", "sms", "whatsapp"))
        )
        if not projection.get("appointment_reminder"):
            affected = affected | (CommunicationMessage.template_key == "appointment_reminder")
        await db.execute(
            update(CommunicationMessage)
            .where(
                CommunicationMessage.clinic_id == clinic_id,
                CommunicationMessage.patient_id == patient_id,
                CommunicationMessage.direction == "outbound",
                CommunicationMessage.status.in_(("queued", "failed", "awaiting_manual")),
                affected,
            )
            .values(
                status="skipped", error_message="verified_consent_required", next_attempt_at=None
            )
        )

    @staticmethod
    async def update_patient_preferences(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        data: dict,
    ) -> NotificationPreference:
        """Update notification preferences for a patient."""
        prefs = await NotificationService.get_or_create_patient_preferences(
            db, clinic_id, patient_id
        )

        if prefs.verified_consents is not None and data.get("whatsapp_consent") is not None:
            # A managed opt-in is issued and withdrawn together with its
            # evidence by whichever module enrolled the patient. A preference
            # toggle cannot create or revoke it.
            raise ManagedConsentError("Consent for this patient is managed by verified evidence")
        if data.get("whatsapp_consent") is not None or data.get("whatsapp_enabled") is not None:
            await NotificationService.lock_whatsapp_patient(db, clinic_id, patient_id)
            await db.refresh(prefs)

        for key, value in data.items():
            if value is None or key == "whatsapp_consent":
                continue
            if key == "preferences":
                # Merge, never replace: recording one opt-out must not
                # discard the patient's other recorded choices (#683).
                value = {**(prefs.preferences or {}), **value}
            setattr(prefs, key, value)

        consent = data.get("whatsapp_consent")
        if data.get("whatsapp_enabled") is False or consent is False:
            prefs.whatsapp_opt_in_at = None
            await NotificationService.cancel_pending_whatsapp(db, clinic_id, patient_id)
        elif consent is True and prefs.whatsapp_enabled and prefs.whatsapp_opt_in_at is None:
            prefs.whatsapp_opt_in_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(prefs)
        return prefs

    # ========================================================================
    # Clinic Settings
    # ========================================================================

    @staticmethod
    async def get_clinic_settings(
        db: AsyncSession,
        clinic_id: UUID,
    ) -> ClinicNotificationSettings | None:
        """Get notification settings for a clinic."""
        result = await db.execute(
            select(ClinicNotificationSettings).where(
                ClinicNotificationSettings.clinic_id == clinic_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create_clinic_settings(
        db: AsyncSession,
        clinic_id: UUID,
    ) -> ClinicNotificationSettings:
        """Get or create notification settings for a clinic."""
        settings = await NotificationService.get_clinic_settings(db, clinic_id)
        if settings:
            return settings

        # Create default settings
        settings = ClinicNotificationSettings(clinic_id=clinic_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        return settings

    @staticmethod
    async def available_channels(db: AsyncSession, clinic_id: UUID) -> list[str]:
        """Channels this clinic can actually use right now.

        Computed from the process-wide ``channel_registry`` plus each
        adapter's per-clinic ``supports`` check (e.g. WhatsApp appears only
        when a vendor adapter is registered AND connected for the clinic).
        Never imports a vendor module (ADR 0016).
        """
        available: list[str] = []
        for channel in channel_registry.available_channels():
            for adapter in channel_registry.adapters_for_channel(channel):
                if await adapter.supports(db, clinic_id):
                    available.append(channel.value)
                    break
        return available

    @staticmethod
    async def update_clinic_settings(
        db: AsyncSession,
        clinic_id: UUID,
        data: dict,
    ) -> ClinicNotificationSettings:
        """Update notification settings for a clinic."""
        settings = await NotificationService.get_or_create_clinic_settings(db, clinic_id)

        for field in (
            "preferred_channel",
            "fallback_enabled",
            "manual_channels",
            "sms_daily_limit",
        ):
            if data.get(field) is not None:
                setattr(settings, field, data[field])

        if data.get("settings") is not None:
            # Merge settings instead of replacing
            # Create a copy to ensure SQLAlchemy detects the change
            current_settings = dict(settings.settings) if settings.settings else {}
            for key, value in data["settings"].items():
                if key in current_settings:
                    # Create a new dict with merged values
                    current_settings[key] = {**current_settings[key], **value}
                else:
                    current_settings[key] = value
            settings.settings = current_settings

        await db.commit()
        await db.refresh(settings)
        return settings

    # ========================================================================
    # SMTP Settings
    # ========================================================================

    @staticmethod
    async def get_smtp_settings(
        db: AsyncSession,
        clinic_id: UUID,
    ) -> ClinicSmtpSettings | None:
        """Get SMTP settings for a clinic."""
        result = await db.execute(
            select(ClinicSmtpSettings).where(ClinicSmtpSettings.clinic_id == clinic_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create_smtp_settings(
        db: AsyncSession,
        clinic_id: UUID,
    ) -> ClinicSmtpSettings:
        """Get or create SMTP settings for a clinic."""
        settings = await NotificationService.get_smtp_settings(db, clinic_id)
        if settings:
            return settings

        # Create default settings (disabled by default)
        settings = ClinicSmtpSettings(
            clinic_id=clinic_id,
            provider="disabled",
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        return settings

    @staticmethod
    async def update_smtp_settings(
        db: AsyncSession,
        clinic_id: UUID,
        data: dict,
    ) -> ClinicSmtpSettings:
        """Update SMTP settings for a clinic.

        Handles password encryption if a new password is provided.
        """
        from app.core.email.encryption import encrypt_password

        settings = await NotificationService.get_or_create_smtp_settings(db, clinic_id)

        # Handle password separately - encrypt if provided
        if "password" in data:
            password = data.pop("password")
            if password:
                settings.password_encrypted = encrypt_password(password)
            # If password is None/empty, don't change existing password

        # Reset verification if connection settings change
        connection_fields = {"host", "port", "username", "use_tls", "use_ssl"}
        if any(field in data for field in connection_fields):
            settings.is_verified = False
            settings.last_verified_at = None

        # Update other fields
        for key, value in data.items():
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)

        await db.commit()
        await db.refresh(settings)
        return settings

    @staticmethod
    async def test_smtp_settings(
        db: AsyncSession,
        clinic_id: UUID,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        use_tls: bool,
        use_ssl: bool,
        from_email: str,
        to_email: str,
    ) -> EmailResult:
        """Test SMTP connection with specific settings.

        Creates a temporary SMTP provider and sends a test email.
        On success, marks the clinic's SMTP settings as verified.
        """
        from app.core.email.encryption import decrypt_password
        from app.core.email.providers.base import EmailMessage
        from app.core.email.providers.smtp import SMTPProvider

        # If no password provided, try to use existing one from DB
        actual_password = password
        if not actual_password:
            settings = await NotificationService.get_smtp_settings(db, clinic_id)
            if settings and settings.password_encrypted:
                actual_password = decrypt_password(settings.password_encrypted)

        # Create a temporary SMTP provider with the test settings
        provider = SMTPProvider(
            host=host,
            port=port,
            username=username,
            password=actual_password,
            use_tls=use_tls,
            use_ssl=use_ssl,
            default_from_email=from_email,
            default_from_name="DentalPin",
        )

        # Send test email
        message = EmailMessage(
            to_email=to_email,
            subject="DentalPin - Test de conexión SMTP",
            body_html="""
            <html>
            <body style="font-family: sans-serif; padding: 20px;">
                <h2>Conexión SMTP exitosa</h2>
                <p>Este es un email de prueba de la configuración SMTP de tu clínica.</p>
                <p>Si has recibido este mensaje, la configuración está funcionando correctamente.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">
                    Enviado desde DentalPin
                </p>
            </body>
            </html>
            """,
            body_text="Conexión SMTP exitosa. La configuración está funcionando correctamente.",
            from_email=from_email,
        )

        result = await provider.send(message)

        # Mark as verified if successful
        if result.is_success:
            settings = await NotificationService.get_or_create_smtp_settings(db, clinic_id)
            settings.is_verified = True
            settings.last_verified_at = datetime.now(UTC)
            await db.commit()

        return result

    # ========================================================================
    # Email Logs
    # ========================================================================

    @staticmethod
    async def list_logs(
        db: AsyncSession,
        clinic_id: UUID,
        page: int = 1,
        page_size: int = 20,
        patient_id: UUID | None = None,
        status: str | None = None,
        template_key: str | None = None,
    ) -> tuple[list[CommunicationMessage], int]:
        """List email logs with optional filters."""
        conditions = [CommunicationMessage.clinic_id == clinic_id]

        if patient_id:
            conditions.append(CommunicationMessage.patient_id == patient_id)
        if status:
            conditions.append(CommunicationMessage.status == status)
        if template_key:
            conditions.append(CommunicationMessage.template_key == template_key)

        # Count total
        count_query = select(func.count()).select_from(CommunicationMessage)
        for condition in conditions:
            count_query = count_query.where(condition)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Get items
        query = select(CommunicationMessage).order_by(
            CommunicationMessage.created_at.desc(), CommunicationMessage.id
        )
        for condition in conditions:
            query = query.where(condition)

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    @staticmethod
    async def list_conversation(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        channel: str | None = None,
        limit: int = 200,
    ) -> list[CommunicationMessage]:
        """Return a patient's message thread (inbound + outbound) in order."""
        conditions = [
            CommunicationMessage.clinic_id == clinic_id,
            CommunicationMessage.patient_id == patient_id,
        ]
        if channel:
            conditions.append(CommunicationMessage.channel == channel)
        query = (
            select(CommunicationMessage)
            .where(*conditions)
            # The newest ``limit``, returned oldest first (#1036).
            .order_by(CommunicationMessage.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(reversed(result.scalars().all()))

    # ========================================================================
    # Consent gate (used by the gateway)
    # ========================================================================

    @staticmethod
    async def should_send_notification(
        db: AsyncSession,
        clinic_id: UUID,
        notification_type: str,
        patient_id: UUID | None = None,
        check_auto_send: bool = True,
    ) -> tuple[bool, str]:
        """Check if a notification should be sent.

        Returns (should_send, reason).
        """
        # Check clinic settings
        clinic_settings = await NotificationService.get_clinic_settings(db, clinic_id)
        if clinic_settings:
            type_settings = clinic_settings.settings.get(notification_type, {})

            # Check if enabled
            if not type_settings.get("enabled", True):
                return False, "disabled_at_clinic_level"

            # Check auto_send if required
            if check_auto_send and not type_settings.get("auto_send", True):
                return False, "manual_send_required"

        # Check patient preferences. The channel toggles (email_enabled,
        # whatsapp_enabled, ...) are not read here: each one opts out of its
        # own channel, which the gateway's channel resolution enforces.
        if patient_id:
            prefs = await NotificationService.get_patient_preferences(db, clinic_id, patient_id)
            if NotificationService.opted_out_of_type(prefs, notification_type):
                return False, f"patient_opted_out_of_{notification_type}"

        return True, "ok"

    @staticmethod
    def opted_out_of_type(prefs: NotificationPreference | None, notification_type: str) -> bool:
        """The patient explicitly declined this type. An absent key is consent."""
        if prefs is None:
            return False
        return not (prefs.preferences or {}).get(notification_type, True)

    @staticmethod
    async def test_email_connection(to_email: str) -> EmailResult:
        """Send a test email to verify configuration."""
        from app.core.email.providers.base import EmailMessage

        message = EmailMessage(
            to_email=to_email,
            subject="DentalPin - Test de conexión de email",
            body_html="""
            <html>
            <body style="font-family: sans-serif; padding: 20px;">
                <h2>¡Conexión exitosa!</h2>
                <p>Este es un email de prueba de DentalPin.</p>
                <p>Si has recibido este mensaje, la configuración de email está funcionando correctamente.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">
                    Enviado desde DentalPin
                </p>
            </body>
            </html>
            """,
            body_text="¡Conexión exitosa! Este es un email de prueba de DentalPin.",
        )

        return await email_service.send(message)


def message_date(value: date, locale: str) -> str:
    """A date in a message, in the order of the locale it renders in (#1211).

    The same table as the PDFs (``core/pdf_locales``): ``26/11/2026`` in
    Spanish, ``26.11.2026`` in German, ``2026. 11. 26.`` in Hungarian.
    """
    return format_pdf_date(value, locale)


def appointment_when_context(start_time: datetime, clinic, locale: str) -> dict[str, str]:
    """``appointment_date`` / ``appointment_time`` on the clinic's wall clock.

    ``Appointment.start_time`` is stored in UTC; formatting it as stored told a
    Madrid patient booked for 10:00 to come at 09:00. ``clinic`` may be None
    (UTC then, the same fallback as ``clinic_zone``). ``locale`` is the one
    the message renders in, so the date follows its order (#1211).
    """
    local = start_time.astimezone(clinic_zone(clinic.timezone if clinic else None))
    return {
        "appointment_date": message_date(local, locale),
        "appointment_time": local.strftime("%H:%M"),
    }


def clinic_date_label(instant: datetime, clinic, locale: str) -> str:
    """The date of a stored UTC instant on the clinic's calendar (#922), in ``locale`` (#1211)."""
    return message_date(
        instant.astimezone(clinic_zone(clinic.timezone if clinic else None)), locale
    )


async def budget_treatments_context(db: AsyncSession, budget_id: UUID, money: Money) -> list[dict]:
    """The ``treatments`` table every locale's ``budget_sent.html`` renders.

    ``price`` is already formatted by ``money`` (see :func:`money_formatter`).

    Lived twice — once in ``handlers.py`` for the event-driven enqueue and
    once in ``router.py`` for the manual send. The copies diverged: #287
    fixed the handler's ``catalog_item.name`` (the model has no such
    attribute, only a per-locale ``names`` dict) and left the router's
    alone, so manual ``budget_sent`` raised ``AttributeError`` for any
    budget with items (#527). One implementation cannot drift from itself.

    Catalog names are fetched in a single ``IN`` query rather than one per
    line — a treatment plan commonly carries 5-30 of them.
    """
    from app.modules.budget.models import BudgetItem
    from app.modules.catalog.models import TreatmentCatalogItem

    items = (
        (
            await db.execute(
                select(BudgetItem)
                .where(BudgetItem.budget_id == budget_id)
                .order_by(BudgetItem.display_order)
            )
        )
        .scalars()
        .all()
    )
    if not items:
        return []

    catalog_ids = {item.catalog_item_id for item in items if item.catalog_item_id}
    names_by_id: dict[UUID, dict] = {}
    if catalog_ids:
        rows = (
            (
                await db.execute(
                    select(TreatmentCatalogItem.id, TreatmentCatalogItem.names).where(
                        TreatmentCatalogItem.id.in_(catalog_ids)
                    )
                )
            )
            .tuples()
            .all()
        )
        names_by_id = {row_id: names or {} for row_id, names in rows}

    return [
        {
            "name": catalog_name(names_by_id.get(item.catalog_item_id, {})) or "Tratamiento",
            "tooth": item.tooth_number,
            "price": money(item.line_total),
        }
        for item in items
    ]


APPOINTMENT_NOTIFICATION_TYPES = (
    "appointment_confirmation",
    "appointment_reminder",
    "appointment_cancelled",
)
BUDGET_NOTIFICATION_TYPES = ("budget_sent", "budget_accepted")


class SendContextError(Exception):
    """A manual send cannot build its context: a missing or foreign id.

    ``code`` is the machine name the agent tool returns; ``status_code`` and
    ``detail`` are what the REST route raises.
    """

    def __init__(self, code: str, status_code: int, detail: str):
        super().__init__(detail)
        self.code = code
        self.status_code = status_code
        self.detail = detail


@dataclass
class ManualSendContext:
    context: dict
    # The recipient: the one passed in, else the appointment's or budget's.
    patient: object | None
    # The appointment's or budget's own patient, when the type links one.
    linked_patient_id: UUID | None = None


async def _message_locale(db: AsyncSession, clinic_id: UUID, patient) -> str:
    """The gateway's answer for this recipient: patient preference, else clinic."""
    if patient:
        return await resolve_patient_communication_locale(db, clinic_id, patient.id)
    return await resolve_clinic_communication_locale(db, clinic_id)


async def build_manual_send_context(
    db: AsyncSession,
    clinic_id: UUID,
    notification_type: str,
    *,
    patient=None,
    appointment_id: UUID | None = None,
    budget_id: UUID | None = None,
    custom_context: dict | None = None,
) -> ManualSendContext:
    """Template context for a manual send, from the REST route or the copilot.

    Clinic name/phone/address always; an ``appointment_*`` type requires its
    appointment (date, time, professional), a ``budget_sent`` /
    ``budget_accepted`` its budget (number, totals, treatments). Both must
    belong to ``clinic_id``. The copilot tool used to fill only
    ``patient_name``, so its emails went out with no clinic, date or amount
    (#1181). Raises :class:`SendContextError`.
    """
    from app.core.auth.models import Clinic, User
    from app.modules.agenda.models import Appointment
    from app.modules.budget.models import Budget
    from app.modules.patients.models import Patient

    context = custom_context or {}
    linked_patient_id = None

    if patient:
        context["patient_name"] = f"{patient.first_name} {patient.last_name}"

    clinic = (await db.execute(select(Clinic).where(Clinic.id == clinic_id))).scalar_one_or_none()
    if clinic:
        context["clinic_name"] = clinic.name
        context["clinic_phone"] = clinic.phone
        context["clinic_address"] = clinic.address

    if notification_type in APPOINTMENT_NOTIFICATION_TYPES:
        if not appointment_id:
            raise SendContextError(
                "appointment_id_required",
                400,
                "appointment_id is required for appointment notifications",
            )
        appointment = (
            await db.execute(
                select(Appointment).where(
                    Appointment.id == appointment_id, Appointment.clinic_id == clinic_id
                )
            )
        ).scalar_one_or_none()
        if not appointment:
            raise SendContextError("appointment_not_found", 404, "Appointment not found")
        linked_patient_id = appointment.patient_id

        context["appointment_id"] = str(appointment.id)
        context["appointment_start_at"] = appointment.start_time.isoformat()
        if notification_type == "appointment_reminder":
            # Same day-valid check-in link the sweep puts in (ADR 0037, #1156).
            from app.modules.notifications.tasks import _reminder_checkin_url

            context["checkin_url"] = _reminder_checkin_url(appointment, clinic)

        if appointment.professional_id:
            professional = (
                await db.execute(select(User).where(User.id == appointment.professional_id))
            ).scalar_one_or_none()
            if professional:
                context["professional_name"] = f"{professional.first_name} {professional.last_name}"

        # Use patient from appointment if not provided
        if not patient:
            patient = (
                await db.execute(select(Patient).where(Patient.id == appointment.patient_id))
            ).scalar_one_or_none()
            if patient:
                context["patient_name"] = f"{patient.first_name} {patient.last_name}"

        # Dated in the locale the gateway will render in (#1211).
        context.update(
            appointment_when_context(
                appointment.start_time, clinic, await _message_locale(db, clinic_id, patient)
            )
        )

    if notification_type in BUDGET_NOTIFICATION_TYPES:
        if not budget_id:
            raise SendContextError(
                "budget_id_required", 400, "budget_id is required for budget notifications"
            )
        budget = (
            await db.execute(
                select(Budget).where(Budget.id == budget_id, Budget.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()
        if not budget:
            raise SendContextError("budget_not_found", 404, "Budget not found")
        linked_patient_id = budget.patient_id

        # Use patient from budget if not provided
        if not patient:
            patient = (
                await db.execute(select(Patient).where(Patient.id == budget.patient_id))
            ).scalar_one_or_none()
            if patient:
                context["patient_name"] = f"{patient.first_name} {patient.last_name}"

        # Amounts in the clinic's currency and dates in the order of the
        # locale the gateway will render in (#1133, #1211).
        locale = await _message_locale(db, clinic_id, patient)
        money = money_formatter(clinic, locale)

        context["budget_number"] = budget.budget_number
        context["budget_date"] = message_date(budget.valid_from, locale)
        context["total"] = money(budget.total)
        context["subtotal"] = money(budget.subtotal)
        context["discount_amount"] = money(budget.total_discount) if budget.total_discount else None
        context["notes"] = budget.patient_notes

        if budget.valid_until:
            context["validity_days"] = (budget.valid_until - budget.valid_from).days

        if notification_type == "budget_accepted":
            context["accepted_date"] = clinic_date_label(budget.updated_at, clinic, locale)

        if notification_type == "budget_sent":
            context["treatments"] = await budget_treatments_context(db, budget.id, money)

    return ManualSendContext(context=context, patient=patient, linked_patient_id=linked_patient_id)
