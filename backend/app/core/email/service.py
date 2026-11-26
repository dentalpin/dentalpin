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


def format_address_line(address: dict) -> str | None:
    """One-line clinic address (street, postal code + city, country).

    ``Clinic.address`` is a JSONB dict; templates print the result, never the
    dict itself (#1043). Same shape as the billing PDF letterhead.
    """
    parts = []
    if address.get("street"):
        parts.append(address["street"])
    city_line = " ".join(filter(None, [address.get("postal_code"), address.get("city")]))
    if city_line:
        parts.append(city_line)
    if address.get("country"):
        parts.append(address["country"])
    return ", ".join(parts) or None


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
        # Same loader, no autoescaping: renders the plain-text subject (#1204).
        self._text_env: Environment | None = None
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
            if settings.ENVIRONMENT == "production":
                # Misconfiguration, reached by omission: the console
                # provider is metadata-only here and reports FAILED, so
                # nothing is delivered and nothing claims it was (#614).
                logger.error(
                    "Email is not configured: no email will be delivered. "
                    "Set EMAIL_PROVIDER=smtp (or EMAIL_ENABLED=false to "
                    "silence this)."
                )
            else:
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
            if settings.ENVIRONMENT == "production":
                logger.error(
                    f"Unknown email provider '{settings.EMAIL_PROVIDER}': no email "
                    "will be delivered. Set EMAIL_PROVIDER=smtp (or "
                    "EMAIL_ENABLED=false to silence this)."
                )
            else:
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
            self._text_env = self._jinja_env.overlay(autoescape=False)
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

        from app.config import settings as app_settings
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
                default_from_email=settings.from_email or app_settings.EMAIL_FROM_ADDRESS,
                default_from_name=settings.from_name or app_settings.EMAIL_FROM_NAME,
            )

        # Fallback to global
        return None

    @staticmethod
    def _disabled_result() -> EmailResult:
        """Result for a globally disabled instance: nothing sent, nothing failed."""
        return EmailResult(
            status=EmailStatus.SKIPPED,
            provider="disabled",
            error_message="Email is disabled (EMAIL_ENABLED=false)",
        )

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

        from app.config import settings

        if not settings.EMAIL_ENABLED:
            # Global opt-out: this instance is not meant to deliver mail, so
            # skip without resolving the per-clinic provider or touching the
            # network. The outbox records this as a skip, not a failure.
            return self._disabled_result()

        # Try to get clinic-specific provider
        provider = self.provider  # Default to global
        clinic_provider = None
        if db and clinic_id:
            clinic_provider = await self.create_provider_for_clinic(db, clinic_id)
            if clinic_provider:
                provider = clinic_provider
                logger.info(f"Using clinic-specific email provider for clinic {clinic_id}")

        # The instance's sender is for the instance's provider. A clinic's
        # provider has its own default, which this used to shadow (#1052).
        if not clinic_provider and not message.from_email:
            message.from_email = settings.EMAIL_FROM_ADDRESS
            message.from_name = message.from_name or settings.EMAIL_FROM_NAME

        return await provider.send(message)

    async def send_templated(
        self,
        to_email: str,
        template_key: str,
        context: dict,
        subject: str | None,
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
            subject: Email subject (can include template variables). Empty
                means the file template's localized ``title`` block (#1204).
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

        from app.config import settings

        if not settings.EMAIL_ENABLED:
            # Guarded here too: a disabled instance must not render (and then
            # fail on) a template it is never going to deliver.
            return self._disabled_result()

        if isinstance(context.get("clinic_address"), dict):
            context = {**context, "clinic_address": format_address_line(context["clinic_address"])}

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

        # No subject from the caller (no clinic override row): the file
        # template's localized title is the subject, never the raw key (#1204).
        # The default subject is already rendered: it is never rendered a
        # second time, so a clinic name containing ``{{`` stays literal text.
        if not subject:
            rendered_subject = self.render_default_subject(template_key, locale, context)
        # A caller-supplied subject (the clinic's override row) may contain
        # template syntax. A subject is plain text, so it renders without
        # HTML autoescaping (#1043).
        elif "{{" in subject or "{%" in subject:
            rendered_subject = subject
            try:
                rendered_subject = (
                    self._jinja_env.overlay(autoescape=False).from_string(subject).render(context)
                )
            except Exception as e:
                logger.warning(f"Failed to render subject template: {e}")
        else:
            rendered_subject = subject

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

        for template_path in self._template_paths(template_key, locale, extension):
            try:
                template = self._jinja_env.get_template(template_path)
                # base.html reads ``locale`` for ``lang``/``dir``.
                return template.render({"locale": locale, **context})
            except Exception:
                continue

        logger.warning(f"Template not found: {template_key}.{extension} for locale {locale}")
        return None

    @staticmethod
    def _template_paths(template_key: str, locale: str, extension: str) -> list[str]:
        """Locale-specific template first, then the base locale (overlay
        locales), then the fallbacks."""
        template_paths = [f"{locale}/{template_key}.{extension}"]
        if locale == "pt-BR":
            template_paths.append(f"pt/{template_key}.{extension}")
        template_paths.extend(
            [
                f"en/{template_key}.{extension}",
                f"default/{template_key}.{extension}",
                f"{template_key}.{extension}",
            ]
        )
        return template_paths

    def render_default_subject(self, template_key: str, locale: str, context: dict) -> str:
        """Subject for an email with no clinic override: the ``title`` block of
        the same file template the body renders from (#1204).

        Plain text (no autoescaping), whitespace collapsed. Falls back to the
        clinic name, never to the raw template key.
        """
        self._initialize()
        fallback = context.get("clinic_name") or "DentalPin"
        if not self._text_env:
            return fallback
        for template_path in self._template_paths(template_key, locale, "html"):
            try:
                template = self._text_env.get_template(template_path)
            except Exception:
                continue
            block = template.blocks.get("title")
            if block is None:
                break
            try:
                ctx = template.new_context({"locale": locale, **context})
                title = " ".join("".join(block(ctx)).split()).strip(" -\u2013\u2014")
            except Exception as e:
                logger.warning(f"Failed to render subject for {template_key}: {e}")
                break
            return title or fallback
        return fallback

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
