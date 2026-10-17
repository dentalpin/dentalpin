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


def _create_gemini(config: ProviderConfig) -> Provider:
    from app.core.llm.gemini_provider import GeminiProvider

    return GeminiProvider(api_key=config.api_key or "")


def _create_openrouter(config: ProviderConfig) -> Provider:
    from app.core.llm.openrouter_provider import OpenRouterProvider

    return OpenRouterProvider(api_key=config.api_key or "")


def _create_groq(config: ProviderConfig) -> Provider:
    from app.core.llm.groq_provider import GroqProvider

    return GroqProvider(api_key=config.api_key or "")


def _create_ollama(config: ProviderConfig) -> Provider:
    from app.core.llm.ollama_provider import OllamaProvider

    return OllamaProvider(base_url=config.base_url)


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

GEMINI_SPEC = ProviderSpec(
    name="gemini",
    label="Gemini",
    default_model=settings.COPILOT_MODEL_CHAT_GEMINI,
    tool_dialect="openai",
    needs_api_key=True,
    api_key_setting="GEMINI_API_KEY",
    factory=_create_gemini,
)

OPENROUTER_SPEC = ProviderSpec(
    name="openrouter",
    label="OpenRouter",
    default_model=settings.COPILOT_MODEL_CHAT_OPENROUTER,
    tool_dialect="openai",
    needs_api_key=True,
    api_key_setting="OPENROUTER_API_KEY",
    factory=_create_openrouter,
)

GROQ_SPEC = ProviderSpec(
    name="groq",
    label="Groq",
    default_model=settings.COPILOT_MODEL_CHAT_GROQ,
    tool_dialect="openai",
    needs_api_key=True,
    api_key_setting="GROQ_API_KEY",
    factory=_create_groq,
)

OLLAMA_SPEC = ProviderSpec(
    name="ollama",
    label="Ollama",
    default_model=settings.COPILOT_MODEL_CHAT_OLLAMA,
    tool_dialect="openai",
    needs_api_key=False,
    api_key_setting=None,
    factory=_create_ollama,
    base_url_setting="OLLAMA_BASE_URL",
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


def get_configured_base_url(spec: ProviderSpec) -> str | None:
    """Return the deployment-level base URL configured for ``spec``.

    ``None`` for vendors with a fixed endpoint; the self-hosted provider
    (Ollama) reads its endpoint from ``OLLAMA_BASE_URL``. An unset *or*
    empty setting normalizes to ``None`` so the provider's own default
    applies (Compose forwards an unset var as ``""``, not omitted).
    """
    if spec.base_url_setting is None:
        return None
    return (getattr(settings, spec.base_url_setting) or "").strip() or None


def get_provider(name: str, *, api_key: str | None = None) -> Provider:
    """Return a configured :class:`Provider` for ``name``.

    Raises :class:`LLMConfigError` for unsupported names so a clinic can
    never select a provider this deployment cannot serve.
    """
    spec = get_provider_spec(name)
    resolved_api_key = api_key or get_configured_api_key(spec)

    return spec.factory(
        ProviderConfig(
            api_key=resolved_api_key,
            base_url=get_configured_base_url(spec),
        )
    )
