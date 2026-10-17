"""Ollama implementation of the neutral :class:`Provider` protocol.

Speaks a self-hosted Ollama server's OpenAI-compatible endpoint
(``<base>/v1/chat/completions``) through the ``openai`` SDK, so the wire
format — Chat Completions streaming, tool calling, usage chunks — is
identical to :class:`OpenAIProvider` and this subclass only sets the
endpoint. Tool dialect is ``"openai"``; dotted tool names map
``.`` <-> ``-`` exactly like the OpenAI provider.

Ollama needs no API key (the ``openai`` SDK refuses an empty one, so a
placeholder stands in); pointed at a host on the operator's network, every
prompt stays there. Tool calling only works on pulled models that support
it; the mandatory PHI redactor still runs upstream (the local-tier
relaxation from the #332 brief stays deferred). Token-budget accounting
reads the streamed usage chunks, so a server that omits them leaves
``monthly_token_limit`` unenforced and ``GET /metrics`` reading zero.
"""

from __future__ import annotations

from app.core.llm.openai_provider import OpenAIProvider

#: Ollama's default server root; the OpenAI-compatible API lives under
#: ``/v1``. Matches the ``OLLAMA_BASE_URL`` default in ``app.config``.
OLLAMA_DEFAULT_BASE_URL = "http://ollama:11434"

#: Ollama ignores the value, but the OpenAI SDK rejects an empty key.
OLLAMA_PLACEHOLDER_API_KEY = "ollama"


def _openai_compatible_url(base_url: str | None) -> str:
    """Normalize a server root (with or without a trailing ``/v1``)."""
    root = (base_url or "").strip().rstrip("/") or OLLAMA_DEFAULT_BASE_URL
    if root.endswith("/v1"):
        return f"{root}/"
    return f"{root}/v1/"


class OllamaProvider(OpenAIProvider):
    """Streams completions from a local Ollama server, speaking neutral types."""

    def __init__(self, *, base_url: str | None = None) -> None:
        super().__init__(
            api_key=OLLAMA_PLACEHOLDER_API_KEY,
            base_url=_openai_compatible_url(base_url),
        )
