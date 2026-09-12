"""Provider resolution through the process-wide LLM provider registry."""

from __future__ import annotations

from app.config import settings
from app.core.llm.base import LLMConfigError, Provider
from app.core.llm.registry import llm_provider_registry
from app.core.llm.spec import ProviderConfig, ProviderSpec


def _create_openai(config: ProviderConfig) -> Provider:
    from app.core.llm.openai_provider import OpenAIProvider

    return OpenAIProvider(api_key=config.api_key or settings.OPENAI_API_KEY)


def _create_anthropic(config: ProviderConfig) -> Provider:
    from app.core.llm.anthropic_provider import AnthropicProvider

    return AnthropicProvider(api_key=config.api_key or settings.ANTHROPIC_API_KEY)


OPENAI_SPEC = ProviderSpec(
    name="openai",
    label="OpenAI",
    tier="paid",
    default_model=settings.COPILOT_MODEL_CHAT_OPENAI,
    supports_tools=True,
    redaction_required=True,
    needs_api_key=True,
    factory=_create_openai,
)

ANTHROPIC_SPEC = ProviderSpec(
    name="anthropic",
    label="Anthropic",
    tier="paid",
    default_model=settings.COPILOT_MODEL_CHAT_ANTHROPIC,
    supports_tools=True,
    redaction_required=True,
    needs_api_key=True,
    factory=_create_anthropic,
)


def get_provider(name: str, *, api_key: str | None = None) -> Provider:
    """Return a configured :class:`Provider` for ``name``.

    Raises :class:`LLMConfigError` for unsupported names so a clinic can
    never select a provider this deployment cannot serve.
    """
    spec = llm_provider_registry.get(name)
    if spec is None:
        supported = ", ".join(item.name for item in llm_provider_registry.list()) or "none"
        raise LLMConfigError(
            f"Unsupported LLM provider: {name!r} (supported: {supported})"
        )

    return spec.factory(ProviderConfig(api_key=api_key))
