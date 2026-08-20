"""Notifications module business logic."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailResult, email_service

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

    Used as the default locale for outbound emails / SMS — patient
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


logger = logging.getLogger(__name__)


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
            NotificationTemplate.template_key, NotificationTemplate.locale
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
        clinic_id: UUID,
        template_key: str,
        locale: str = "es",
        channel: str = "email",
    ) -> NotificationTemplate | None:
        """Get a template by key, locale and channel.

        Priority: clinic-specific > system template.
        """
        # First try clinic-specific
        result = await db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.clinic_id == clinic_id,
                NotificationTemplate.template_key == template_key,
                NotificationTemplate.locale == locale,
                NotificationTemplate.channel == channel,
                NotificationTemplate.is_active == True,  # noqa: E712
            )
        )
        template = result.scalar_one_or_none()
        if template:
            return template

        # Fallback to system template
        result = await db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.clinic_id.is_(None),
                NotificationTemplate.template_key == template_key,
                NotificationTemplate.locale == locale,
                NotificationTemplate.channel == channel,
                NotificationTemplate.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

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
            select(NotificationPreference).where(
                NotificationPreference.clinic_id == clinic_id,
                NotificationPreference.patient_id == patient_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create_patient_preferences(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
    ) -> NotificationPreference:
        """Get or create notification preferences for a patient."""
        prefs = await NotificationService.get_patient_preferences(db, clinic_id, patient_id)
        if prefs:
            return prefs

        # Create default preferences
        prefs = NotificationPreference(
            clinic_id=clinic_id,
            patient_id=patient_id,
        )
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)
        return prefs

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

        for key, value in data.items():
            if value is not None:
                setattr(prefs, key, value)

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
    async def update_clinic_settings(
        db: AsyncSession,
        clinic_id: UUID,
        data: dict,
    ) -> ClinicNotificationSettings:
        """Update notification settings for a clinic."""
        settings = await NotificationService.get_or_create_clinic_settings(db, clinic_id)

        if "settings" in data:
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
            default_from_name="Denplant",
        )

        # Send test email
        message = EmailMessage(
            to_email=to_email,
            subject="Denplant - Test de conexión SMTP",
            body_html="""
            <html>
            <body style="font-family: sans-serif; padding: 20px;">
                <h2>Conexión SMTP exitosa</h2>
                <p>Este es un email de prueba de la configuración SMTP de tu clínica.</p>
                <p>Si has recibido este mensaje, la configuración está funcionando correctamente.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">
                    Enviado desde Denplant
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
        query = select(CommunicationMessage).order_by(CommunicationMessage.created_at.desc())
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
            .order_by(CommunicationMessage.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

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

        # Check patient preferences
        if patient_id:
            prefs = await NotificationService.get_patient_preferences(db, clinic_id, patient_id)
            if prefs:
                # Check global email toggle
                if not prefs.email_enabled:
                    return False, "patient_opted_out"

                # Check specific preference
                if not prefs.preferences.get(notification_type, True):
                    return False, f"patient_opted_out_of_{notification_type}"

        return True, "ok"

    @staticmethod
    async def test_email_connection(to_email: str) -> EmailResult:
        """Send a test email to verify configuration."""
        from app.core.email.providers.base import EmailMessage

        message = EmailMessage(
            to_email=to_email,
            subject="Denplant - Test de conexión de email",
            body_html="""
            <html>
            <body style="font-family: sans-serif; padding: 20px;">
                <h2>¡Conexión exitosa!</h2>
                <p>Este es un email de prueba de Denplant.</p>
                <p>Si has recibido este mensaje, la configuración de email está funcionando correctamente.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">
                    Enviado desde Denplant
                </p>
            </body>
            </html>
            """,
            body_text="¡Conexión exitosa! Este es un email de prueba de Denplant.",
        )

        return await email_service.send(message)
