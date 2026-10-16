"""Console email provider for development and testing.

This provider logs emails to the console instead of actually sending them.
It's useful for development and testing environments.

In production (misconfiguration — the operator never set a real
provider) it logs metadata only and reports the send as failed, so no
patient content reaches the logs and nothing claims delivery (#614).
"""

import logging
import uuid
from datetime import UTC, datetime

from app.config import settings
from app.core.email.providers.base import (
    EmailMessage,
    EmailProvider,
    EmailResult,
    EmailStatus,
)

logger = logging.getLogger(__name__)


def _mask_address(address: str | None) -> str:
    """Mask an email local part (a***@example.com); domains are not PII."""
    if not address or "@" not in address:
        return "unknown"
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}" if local else f"***@{domain}"


class ConsoleProvider(EmailProvider):
    """Email provider that logs emails to the console.

    This provider is used in development and testing environments.
    It simulates sending emails by logging them with all details.
    """

    @property
    def name(self) -> str:
        return "console"

    async def send(self, message: EmailMessage) -> EmailResult:
        """Log the email to the console instead of sending.

        In production the full content never reaches the logs: only
        metadata (masked recipient, attachment count) is logged and the
        send reports FAILED with the remedy, so the UI and the outbox
        stop claiming delivery (#614).

        Args:
            message: The email message to "send".

        Returns:
            EmailResult indicating success (dev/test) or failure
            (production without a real provider).
        """
        message_id = f"console-{uuid.uuid4()}"
        sent_at = datetime.now(UTC)

        if settings.ENVIRONMENT == "production" and not settings.TESTING:
            logger.error(
                "Email NOT delivered (console provider in production): "
                "to=%s attachments=%d id=%s. Set EMAIL_PROVIDER=smtp "
                "(or EMAIL_ENABLED=false if this instance sends no mail).",
                _mask_address(message.to_email),
                len(message.attachments),
                message_id,
            )
            return EmailResult(
                status=EmailStatus.FAILED,
                provider=self.name,
                message_id=message_id,
                error_message=(
                    "Email is not configured: no email was delivered. "
                    "Set EMAIL_PROVIDER=smtp (or EMAIL_ENABLED=false)."
                ),
                sent_at=sent_at,
            )

        # Create a formatted output
        separator = "=" * 60
        output = f"""
{separator}
EMAIL SENT (Console Provider)
{separator}
Message ID: {message_id}
Sent at: {sent_at.isoformat()}

From: {message.from_name or "N/A"} <{message.from_email or "default"}>
To: {message.to_name or "N/A"} <{message.to_email}>
Subject: {message.subject}
"""

        if message.cc:
            output += f"CC: {', '.join(message.cc)}\n"
        if message.bcc:
            output += f"BCC: {', '.join(message.bcc)}\n"
        if message.reply_to:
            output += f"Reply-To: {message.reply_to}\n"
        if message.attachments:
            output += f"Attachments: {len(message.attachments)} file(s)\n"
            for att in message.attachments:
                output += f"  - {att.get('filename', 'unnamed')}\n"

        output += f"""
--- BODY (TEXT) ---
{message.body_text or "(no plain text version)"}

--- BODY (HTML) ---
{message.body_html}
{separator}
"""

        logger.info(output)

        return EmailResult(
            status=EmailStatus.SUCCESS,
            provider=self.name,
            message_id=message_id,
            sent_at=sent_at,
        )

    async def health_check(self) -> bool:
        """Console provider is always healthy."""
        return True
