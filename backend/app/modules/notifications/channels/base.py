"""Channel adapter contract — the public surface vendor modules import.

A *channel* is a way of reaching a patient (email, WhatsApp, …). The
``notifications`` gateway owns the routing, consent and outbox logic; an
*adapter* only knows how to put one rendered message on the wire for one
channel. Vendor modules (e.g. ``whatsapp_kapso``) depend on
``notifications`` and register their adapter into :mod:`.registry`.

This module is the stable contract: vendors import ``Channel``,
``OutboundMessage``, ``AdapterResult`` and ``ChannelAdapter`` from here and
nothing else from the notifications internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class Channel(StrEnum):
    """Delivery channels the gateway can route to."""

    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    # Others land here as adapters appear.


class SendStatus(StrEnum):
    """Terminal-ish outcome of a single adapter ``send`` attempt.

    Mirrors ``app.core.email.providers.base.EmailStatus`` so the email
    path maps 1:1, but uses ``sent`` (the value persisted on
    ``communication_messages``) rather than ``success``.
    """

    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class OutboundMessage:
    """A rendered message handed to an adapter for delivery.

    Superset of ``app.core.email.providers.base.EmailMessage``: it carries
    both the email-shaped fields (``subject``/``body_html``/``body_text``)
    and the WhatsApp-shaped fields (``provider_template_name`` + ordered
    ``context``). An adapter uses whichever its channel needs.
    """

    channel: Channel
    to_address: str  # email address or E.164 phone number
    clinic_id: UUID
    template_key: str
    locale: str = "es"
    context: dict = field(default_factory=dict)
    to_name: str | None = None
    patient_id: UUID | None = None
    # "template" = pre-approved template (the only kind allowed for proactive
    # WhatsApp, outside the 24h session window); "session" = free-form.
    message_kind: str = "template"
    provider_template_name: str | None = None
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class AdapterResult:
    """Outcome of an adapter ``send``. Mirrors ``EmailResult``."""

    status: SendStatus
    provider: str
    provider_message_id: str | None = None
    error_message: str | None = None
    sent_at: datetime | None = None

    @property
    def is_sent(self) -> bool:
        return self.status == SendStatus.SENT


@runtime_checkable
class ChannelAdapter(Protocol):
    """What a module must implement to deliver one channel.

    Adapters are stateless and registered process-wide; per-clinic
    activation is decided by :meth:`supports` (reads the clinic's config),
    never by the adapter's mere presence.
    """

    channel: Channel
    adapter_name: str  # unique, e.g. "email", "whatsapp_kapso"

    async def supports(self, db: AsyncSession, clinic_id: UUID) -> bool:
        """Is this channel configured and active for the clinic?"""
        ...

    async def send(self, db: AsyncSession, msg: OutboundMessage) -> AdapterResult:
        """Deliver one message. Must not raise for delivery failures —
        return ``AdapterResult(status=FAILED, ...)`` instead."""
        ...
