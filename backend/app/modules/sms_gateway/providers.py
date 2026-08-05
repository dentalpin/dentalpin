"""Pluggable SMS provider abstraction.

To add a real provider once you've picked one:

1. Write a class implementing ``SmsProvider`` (just one method: ``send``).
2. Add it to the ``PROVIDERS`` dict at the bottom of this file.
3. Set ``provider_name`` to your new key in the clinic's SMS settings
   (Settings → SMS → Provider) and fill in the API key / sender ID.

Nothing else in this module, in ``notifications``, or anywhere else needs
to change — the adapter (``adapter.py``) always looks the provider up by
name through ``get_provider()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SmsSendResult:
    status: str  # "sent" | "failed" | "skipped"
    provider_message_id: str | None = None
    error_message: str | None = None


class SmsProvider(Protocol):
    """What a real SMS provider integration must implement."""

    async def send(
        self,
        *,
        to: str,
        body: str,
        sender_id: str | None,
        api_key: str | None,
        base_url: str | None,
    ) -> SmsSendResult:
        """Send one SMS. Must not raise — return a ``failed`` result instead."""
        ...


class PlaceholderProvider:
    """Default provider: doesn't call any external API.

    Used until a real provider is picked and configured. Returns
    ``skipped`` (not ``failed``) so the rest of the system — outbox,
    consent tracking, patient timeline — behaves exactly as it will once
    a real provider is wired in, except no message actually leaves the
    building. The caller (``adapter.py``) also writes every attempt to
    ``SmsOutboxLog`` so nothing is silently lost while you're still
    deciding on a provider.
    """

    async def send(
        self,
        *,
        to: str,
        body: str,
        sender_id: str | None,
        api_key: str | None,
        base_url: str | None,
    ) -> SmsSendResult:
        return SmsSendResult(
            status="skipped",
            error_message=(
                "No real SMS provider configured yet — this is the placeholder. "
                "Set a provider under Settings \u2192 SMS once you've picked one."
            ),
        )


# Registry of available providers by name. Add your real provider here
# once you've built it (see the module docstring above).
PROVIDERS: dict[str, type] = {
    "placeholder": PlaceholderProvider,
}


def get_provider(name: str) -> SmsProvider:
    provider_cls = PROVIDERS.get(name, PlaceholderProvider)
    return provider_cls()


def available_providers() -> list[str]:
    return sorted(PROVIDERS.keys())
