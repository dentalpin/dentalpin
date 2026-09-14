"""Provider resolution through the process-wide LLM provider registry."""

from __future__ import annotations

from app.config import settings
from app.core.llm.base import LLMConfigError, Provider
from app.core.llm.registry import llm_provider_registry
from app.core.llm.spec import ProviderConfig, ProviderSpec


def _create_openai(config: ProviderConfig) -> Provider:
    from app.core.llm.openai_provider import OpenAIProvider

    return OpenAIProvider(api_key=config.api_key or "")


def _create_anthropic(config: ProviderConfig) -> Provider:
    from app.core.llm.anthropic_provider import AnthropicProvider

    return AnthropicProvider(api_key=config.api_key or "")


OPENAI_SPEC = ProviderSpec(
    name="openai",
    label="OpenAI",
    default_model=settings.COPILOT_MODEL_CHAT_OPENAI,
    tool_dialect="openai",
    needs_api_key=True,
    api_key_setting="OPENAI_API_KEY",
    factory=_create_openai,
)

ANTHROPIC_SPEC = ProviderSpec(
    name="anthropic",
    label="Anthropic",
    default_model=settings.COPILOT_MODEL_CHAT_ANTHROPIC,
    tool_dialect="anthropic",
    needs_api_key=True,
    api_key_setting="ANTHROPIC_API_KEY",
    factory=_create_anthropic,
)


def get_provider_spec(name: str) -> ProviderSpec:
    """Return the registered specification for ``name``."""
    spec = llm_provider_registry.get(name)
    if spec is None:
        supported = ", ".join(item.name for item in llm_provider_registry.list()) or "none"
        raise LLMConfigError(f"Unsupported LLM provider: {name!r} (supported: {supported})")
    return spec


def get_configured_api_key(spec: ProviderSpec) -> str | None:
    """Return the deployment-level API key configured for ``spec``."""
    if spec.api_key_setting is None:
        return None
    return getattr(settings, spec.api_key_setting)


def get_provider(name: str, *, api_key: str | None = None) -> Provider:
    """Return a configured :class:`Provider` for ``name``.

    Raises :class:`LLMConfigError` for unsupported names so a clinic can
    never select a provider this deployment cannot serve.
    """
    spec = get_provider_spec(name)
    resolved_api_key = api_key or get_configured_api_key(spec)

    return spec.factory(ProviderConfig(api_key=resolved_api_key))
