"""SMTP email provider.

This provider sends emails using the standard SMTP protocol.
It's compatible with any SMTP server including Gmail, Outlook,
Mailgun, AWS SES SMTP, and others.
"""

import asyncio
import logging
import smtplib
import ssl
import uuid
from datetime import UTC, datetime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from functools import partial

from app.core.email.providers.base import (
    EmailMessage,
    EmailProvider,
    EmailResult,
    EmailStatus,
)

logger = logging.getLogger(__name__)


class SMTPProvider(EmailProvider):
    """Email provider using SMTP protocol.

    This provider uses Python's smtplib to send emails via SMTP.
    It supports TLS/SSL and authentication.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: int = 30,
        default_from_email: str = "noreply@example.com",
        default_from_name: str = "Denplant",
    ):
        """Initialize the SMTP provider.

        Args:
            host: SMTP server hostname.
            port: SMTP server port.
            username: SMTP authentication username (optional).
            password: SMTP authentication password (optional).
            use_tls: Use STARTTLS for encryption (default True).
            use_ssl: Use SSL/TLS from the start (default False).
            timeout: Connection timeout in seconds.
            default_from_email: Default sender email address.
            default_from_name: Default sender name.
        """
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._use_ssl = use_ssl
        self._timeout = timeout
        self._default_from_email = default_from_email
        self._default_from_name = default_from_name

    @property
    def name(self) -> str:
        return "smtp"

    def _build_message(self, email: EmailMessage) -> MIMEMultipart:
        """Build a MIME message from EmailMessage.

        Args:
            email: The email message to convert.

        Returns:
            A MIMEMultipart message ready for sending.
        """
        msg = MIMEMultipart("alternative")

        # Set headers
        from_email = email.from_email or self._default_from_email
        from_name = email.from_name or self._default_from_name
        msg["From"] = formataddr((from_name, from_email))

        to_addr = formataddr((email.to_name, email.to_email)) if email.to_name else email.to_email
        msg["To"] = to_addr
        msg["Subject"] = email.subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()

        if email.reply_to:
            msg["Reply-To"] = email.reply_to

        if email.cc:
            msg["Cc"] = ", ".join(email.cc)

        # Add custom headers
        for key, value in email.headers.items():
            msg[key] = value

        # Attach plain text body
        if email.body_text:
            msg.attach(MIMEText(email.body_text, "plain", "utf-8"))

        # Attach HTML body
        msg.attach(MIMEText(email.body_html, "html", "utf-8"))

        # Add attachments
        for attachment in email.attachments:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.get("content", b""))
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=attachment.get("filename", "attachment"),
            )
            msg.attach(part)

        return msg

    def _send_sync(self, email: EmailMessage) -> EmailResult:
        """Synchronously send an email via SMTP.

        This method is run in a thread pool to avoid blocking.

        Args:
            email: The email message to send.

        Returns:
            EmailResult with the status of the operation.
        """
        message_id = f"smtp-{uuid.uuid4()}"

        try:
            msg = self._build_message(email)
            msg_id_header = msg["Message-ID"]

            # Collect all recipients
            recipients = [email.to_email]
            recipients.extend(email.cc)
            recipients.extend(email.bcc)

            # Create SSL context
            context = ssl.create_default_context()

            if self._use_ssl:
                # SSL from the start (port 465)
                server = smtplib.SMTP_SSL(
                    self._host,
                    self._port,
                    timeout=self._timeout,
                    context=context,
                )
            else:
                # Plain connection, then STARTTLS
                server = smtplib.SMTP(
                    self._host,
                    self._port,
                    timeout=self._timeout,
                )
                if self._use_tls:
                    server.starttls(context=context)

            try:
                # Authenticate if credentials provided
                if self._username and self._password:
                    server.login(self._username, self._password)

                # Send the email
                from_email = email.from_email or self._default_from_email
                server.sendmail(from_email, recipients, msg.as_string())

                logger.info(
                    f"Email sent via SMTP: {email.subject} to {email.to_email}",
                    extra={"message_id": msg_id_header},
                )

                return EmailResult(
                    status=EmailStatus.SUCCESS,
                    provider=self.name,
                    message_id=msg_id_header or message_id,
                    sent_at=datetime.now(UTC),
                )

            finally:
                server.quit()

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return EmailResult(
                status=EmailStatus.FAILED,
                provider=self.name,
                message_id=message_id,
                error_message=f"Authentication failed: {e}",
            )
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"SMTP recipients refused: {e}")
            return EmailResult(
                status=EmailStatus.FAILED,
                provider=self.name,
                message_id=message_id,
                error_message=f"Recipients refused: {e}",
            )
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return EmailResult(
                status=EmailStatus.FAILED,
                provider=self.name,
                message_id=message_id,
                error_message=f"SMTP error: {e}",
            )
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}", exc_info=True)
            return EmailResult(
                status=EmailStatus.FAILED,
                provider=self.name,
                message_id=message_id,
                error_message=str(e),
            )

    async def send(self, message: EmailMessage) -> EmailResult:
        """Send an email via SMTP asynchronously.

        The actual SMTP communication is done in a thread pool
        to avoid blocking the event loop.

        Args:
            message: The email message to send.

        Returns:
            EmailResult with the status of the operation.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(self._send_sync, message))

    async def health_check(self) -> bool:
        """Check if the SMTP server is reachable.

        Returns:
            True if the server responds, False otherwise.
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._health_check_sync)
        except Exception as e:
            logger.error(f"SMTP health check failed: {e}")
            return False

    def _health_check_sync(self) -> bool:
        """Synchronous health check for SMTP server."""
        try:
            context = ssl.create_default_context()

            if self._use_ssl:
                server = smtplib.SMTP_SSL(
                    self._host,
                    self._port,
                    timeout=self._timeout,
                    context=context,
                )
            else:
                server = smtplib.SMTP(
                    self._host,
                    self._port,
                    timeout=self._timeout,
                )
                if self._use_tls:
                    server.starttls(context=context)

            server.noop()
            server.quit()
            return True
        except Exception:
            return False
