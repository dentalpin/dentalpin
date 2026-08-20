"""Email service facade.

This service provides a unified interface for sending emails using
any configured provider. It handles template rendering and provider
selection.
"""

import logging
from pathlib import Path
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.providers.base import (
    EmailMessage,
    EmailProvider,
    EmailResult,
    EmailStatus,
)
from app.core.email.providers.console import ConsoleProvider
from app.core.email.providers.smtp import SMTPProvider

logger = logging.getLogger(__name__)

# Template directory path
TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates" / "email"


class EmailService:
    """Facade for sending emails through configured providers.

    This service:
    - Selects the appropriate provider based on configuration
    - Renders email templates using Jinja2
    - Provides a simple interface for sending templated emails
    """

    def __init__(self) -> None:
        """Initialize the email service."""
        self._provider: EmailProvider | None = None
        self._jinja_env: Environment | None = None
        self._initialized = False

    def _initialize(self) -> None:
        """Lazy initialization of provider and template engine."""
        if self._initialized:
            return

        from app.config import settings

        # Initialize provider based on settings
        if settings.TESTING or not settings.EMAIL_ENABLED:
            self._provider = ConsoleProvider()
            logger.info("Email service using console provider (testing/disabled mode)")
        elif settings.EMAIL_PROVIDER == "console":
            self._provider = ConsoleProvider()
            logger.info("Email service using console provider")
        elif settings.EMAIL_PROVIDER == "smtp":
            self._provider = SMTPProvider(
                host=settings.EMAIL_SMTP_HOST,
                port=settings.EMAIL_SMTP_PORT,
                username=settings.EMAIL_SMTP_USER or None,
                password=settings.EMAIL_SMTP_PASSWORD or None,
                use_tls=settings.EMAIL_SMTP_TLS,
                default_from_email=settings.EMAIL_FROM_ADDRESS,
                default_from_name=settings.EMAIL_FROM_NAME,
            )
            logger.info(
                f"Email service using SMTP provider: {settings.EMAIL_SMTP_HOST}:{settings.EMAIL_SMTP_PORT}"
            )
        else:
            # Fallback to console if unknown provider
            self._provider = ConsoleProvider()
            logger.warning(
                f"Unknown email provider '{settings.EMAIL_PROVIDER}', falling back to console"
            )

        # Initialize Jinja2 environment for templates
        if TEMPLATES_DIR.exists():
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(TEMPLATES_DIR)),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            logger.info(f"Email templates loaded from {TEMPLATES_DIR}")
        else:
            logger.warning(f"Email templates directory not found: {TEMPLATES_DIR}")

        self._initialized = True

    @property
    def provider(self) -> EmailProvider:
        """Get the current email provider."""
        self._initialize()
        if self._provider is None:
            raise RuntimeError("Email service not properly initialized")
        return self._provider

    async def create_provider_for_clinic(
        self,
        db: AsyncSession,
        clinic_id: UUID,
    ) -> EmailProvider | None:
        """Create an email provider for a specific clinic.

        Reads the clinic's SMTP settings from the database and creates
        an appropriate provider. Falls back to global config if no
        clinic-specific settings are configured.

        Args:
            db: Database session.
            clinic_id: Clinic UUID.

        Returns:
            EmailProvider configured for the clinic, or None to use global.
        """
        from sqlalchemy import select

        from app.core.email.encryption import decrypt_password
        from app.modules.notifications.models import ClinicSmtpSettings

        # Get clinic SMTP settings
        result = await db.execute(
            select(ClinicSmtpSettings).where(ClinicSmtpSettings.clinic_id == clinic_id)
        )
        settings = result.scalar_one_or_none()

        if not settings or not settings.is_active:
            # No clinic-specific settings, use global
            return None

        if settings.provider == "disabled":
            # Email disabled for this clinic
            logger.info(f"Email disabled for clinic {clinic_id}")
            return None

        if settings.provider == "console":
            return ConsoleProvider()

        if settings.provider == "smtp" and settings.host:
            # Decrypt password if set
            password = None
            if settings.password_encrypted:
                password = decrypt_password(settings.password_encrypted)

            return SMTPProvider(
                host=settings.host,
                port=settings.port,
                username=settings.username,
                password=password,
                use_tls=settings.use_tls,
                use_ssl=settings.use_ssl,
                default_from_email=settings.from_email or "",
                default_from_name=settings.from_name or "Denplant",
            )

        # Fallback to global
        return None

    async def send(
        self,
        message: EmailMessage,
        db: AsyncSession | None = None,
        clinic_id: UUID | None = None,
    ) -> EmailResult:
        """Send an email message.

        Args:
            message: The email message to send.
            db: Database session (required for clinic-specific config).
            clinic_id: Clinic UUID for per-clinic SMTP settings.

        Returns:
            EmailResult with the status of the operation.
        """
        self._initialize()

        # Try to get clinic-specific provider
        provider = self.provider  # Default to global
        if db and clinic_id:
            clinic_provider = await self.create_provider_for_clinic(db, clinic_id)
            if clinic_provider:
                provider = clinic_provider
                logger.info(f"Using clinic-specific email provider for clinic {clinic_id}")

        # Apply default from address if not set
        if not message.from_email:
            from app.config import settings

            message.from_email = settings.EMAIL_FROM_ADDRESS
            message.from_name = message.from_name or settings.EMAIL_FROM_NAME

        return await provider.send(message)

    async def send_templated(
        self,
        to_email: str,
        template_key: str,
        context: dict,
        subject: str,
        locale: str = "es",
        to_name: str | None = None,
        from_email: str | None = None,
        from_name: str | None = None,
        reply_to: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        template_html: str | None = None,
        template_text: str | None = None,
        db: AsyncSession | None = None,
        clinic_id: UUID | None = None,
    ) -> EmailResult:
        """Send an email using a template.

        This method renders a Jinja2 template with the provided context
        and sends the resulting email.

        Args:
            to_email: Recipient email address.
            template_key: Template identifier (e.g., 'appointment_confirmation').
            context: Template context variables.
            subject: Email subject (can include template variables).
            locale: Language code for template selection (default 'es').
            to_name: Recipient name (optional).
            from_email: Sender email (optional, uses default).
            from_name: Sender name (optional, uses default).
            reply_to: Reply-to address (optional).
            cc: CC recipients (optional).
            bcc: BCC recipients (optional).
            template_html: Custom HTML template content (overrides file template).
            template_text: Custom text template content (overrides file template).
            db: Database session (required for clinic-specific config).
            clinic_id: Clinic UUID for per-clinic SMTP settings.

        Returns:
            EmailResult with the status of the operation.
        """
        self._initialize()

        # Render HTML template
        body_html = self._render_template(
            template_key=template_key,
            locale=locale,
            context=context,
            extension="html",
            custom_template=template_html,
        )

        if not body_html:
            logger.error(f"Failed to render HTML template: {template_key}")
            return EmailResult(
                status=EmailStatus.FAILED,
                provider=self.provider.name,
                error_message=f"Template not found: {template_key}",
            )

        # Render text template (optional)
        body_text = self._render_template(
            template_key=template_key,
            locale=locale,
            context=context,
            extension="txt",
            custom_template=template_text,
        )

        # Render subject if it contains template syntax
        rendered_subject = subject
        if "{{" in subject or "{%" in subject:
            try:
                rendered_subject = self._jinja_env.from_string(subject).render(context)
            except Exception as e:
                logger.warning(f"Failed to render subject template: {e}")

        message = EmailMessage(
            to_email=to_email,
            to_name=to_name,
            subject=rendered_subject,
            body_html=body_html,
            body_text=body_text,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            cc=cc or [],
            bcc=bcc or [],
        )

        return await self.send(message, db=db, clinic_id=clinic_id)

    def _render_template(
        self,
        template_key: str,
        locale: str,
        context: dict,
        extension: str = "html",
        custom_template: str | None = None,
    ) -> str | None:
        """Render a Jinja2 template.

        Args:
            template_key: Template identifier.
            locale: Language code.
            context: Template context.
            extension: File extension (html or txt).
            custom_template: Custom template string (overrides file).

        Returns:
            Rendered template string, or None if template not found.
        """
        # If custom template provided, use it directly
        if custom_template:
            try:
                return self._jinja_env.from_string(custom_template).render(context)
            except Exception as e:
                logger.error(f"Failed to render custom template: {e}")
                return None

        if not self._jinja_env:
            logger.warning("Jinja2 environment not initialized")
            return None

        # Try locale-specific template first, then fallback to default
        template_paths = [
            f"{locale}/{template_key}.{extension}",
            f"default/{template_key}.{extension}",
            f"{template_key}.{extension}",
        ]

        for template_path in template_paths:
            try:
                template = self._jinja_env.get_template(template_path)
                return template.render(context)
            except Exception:
                continue

        logger.warning(f"Template not found: {template_key}.{extension} for locale {locale}")
        return None

    async def health_check(self) -> bool:
        """Check if the email service is healthy.

        Returns:
            True if the service can send emails, False otherwise.
        """
        self._initialize()
        return await self.provider.health_check()

    def get_provider_name(self) -> str:
        """Get the name of the current provider.

        Returns:
            Provider name string.
        """
        self._initialize()
        return self.provider.name


# Global singleton instance
email_service = EmailService()
