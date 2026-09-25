"""Process-wide registry for pluggable LLM providers."""

from __future__ import annotations

import logging

from app.core.llm.spec import ProviderSpec

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Map provider names to active provider specifications."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderSpec] = {}

    def register(self, spec: ProviderSpec) -> None:
        """Register ``spec`` by name, idempotently replacing overrides."""
        existing = self._providers.get(spec.name)
        if existing == spec:
            return
        if existing is not None:
            logger.info("LLM provider %r re-registered (override)", spec.name)
        self._providers[spec.name] = spec

    def unregister(self, name: str) -> None:
        """Remove a registered provider if present."""
        self._providers.pop(name, None)

    def get(self, name: str) -> ProviderSpec | None:
        """Return a provider specification by name, or ``None``."""
        return self._providers.get(name)

    def list(self) -> list[ProviderSpec]:
        """Return all registered provider specifications."""
        return list(self._providers.values())


llm_provider_registry = ProviderRegistry()
