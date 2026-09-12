"""Process-wide registry of gateway adapters.

Provider modules register their adapter here from ``on_activate()``
(never at import time — ADR 0020: an uninstalled provider is never
registered). Mirrors ``app.modules.notifications.channels.registry``.
"""

from __future__ import annotations

import logging

from .base import GatewayAdapter

logger = logging.getLogger(__name__)


class GatewayRegistry:
    """Maps a provider key to its adapter."""

    def __init__(self) -> None:
        self._adapters: dict[str, GatewayAdapter] = {}

    def register(self, adapter: GatewayAdapter) -> None:
        key = adapter.provider_key
        existing = self._adapters.get(key)
        if existing is not None and type(existing) is type(adapter):
            return  # idempotent: same adapter re-registered on re-import/restart
        if key in self._adapters:
            logger.info("Gateway adapter %r re-registered (override)", key)
        self._adapters[key] = adapter

    def unregister(self, provider_key: str) -> None:
        self._adapters.pop(provider_key, None)

    def get(self, provider_key: str) -> GatewayAdapter | None:
        return self._adapters.get(provider_key)

    def available_providers(self) -> list[str]:
        return sorted(self._adapters.keys())


# Global singleton. Empty until a provider module (e.g. razorpay)
# registers from its own on_activate().
gateway_registry = GatewayRegistry()
