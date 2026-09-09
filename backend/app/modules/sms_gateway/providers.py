"""SMS provider backends.

v1 ships the ``log`` placeholder only (mirrors the dev
``EMAIL_PROVIDER=console`` path): it records the send in the server log
and reports success so the outbox flow is exercisable end to end
without spending money. Twilio and other BSPs later register here via
:func:`register_provider` and become selectable through the settings
``provider`` field — no adapter change needed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.notifications.channels import OutboundMessage


class SmsProvider(Protocol):
    """A wire backend for one SMS provider."""

    name: str

    async def send(
        self, db: AsyncSession, clinic_id: UUID, msg: OutboundMessage
    ) -> tuple[bool, str | None, str | None]:
        """Return (ok, provider_message_id, error_message)."""
        ...


class LogSmsProvider:
    """Placeholder backend: logs and reports success. Sends nothing."""

    name = "log"

    async def send(
        self, db: AsyncSession, clinic_id: UUID, msg: OutboundMessage
    ) -> tuple[bool, str | None, str | None]:
        logger.info(
            "sms_gateway[log] clinic=%s to=%s kind=%s text=%.120s (NOT SENT — placeholder)",
            clinic_id,
            msg.to_address,
            msg.message_kind,
            msg.body_text or "",
        )
        return True, None, None


_PROVIDERS: dict[str, SmsProvider] = {"log": LogSmsProvider()}


def register_provider(provider: SmsProvider) -> None:
    """Register a new wire backend (e.g. Twilio) under its name."""
    _PROVIDERS[provider.name] = provider


def get_provider(name: str) -> SmsProvider | None:
    return _PROVIDERS.get(name)


def list_providers() -> list[str]:
    """Names of registered wire backends (settings UI + validation)."""
    return list(_PROVIDERS)
