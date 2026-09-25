"""Vendor-agnostic LLM provider layer.

Public surface:

* :class:`Provider` — the streaming protocol the orchestrator depends on.
* neutral message/event types (:class:`ProviderMessage`, :class:`TextBlock`,
  :class:`ToolUseBlock`, :class:`ToolResultBlock`, :class:`TextDelta`,
  :class:`ToolUse`, :class:`Usage`, :class:`Done`, :class:`Role`).
* :func:`get_provider` — resolve a provider through the process-wide registry.

Provider specifications are registered by ``CopilotModule.on_activate()`` so
only an installed Copilot module contributes providers at runtime (ADR 0020).
"""

from app.core.llm.base import (
    ContentBlock,
    Done,
    LLMConfigError,
    LLMError,
    Provider,
    ProviderEvent,
    ProviderMessage,
    Role,
    TextBlock,
    TextDelta,
    ToolResultBlock,
    ToolUse,
    ToolUseBlock,
    Usage,
)
from app.core.llm.factory import get_provider

__all__ = [
    "ContentBlock",
    "Done",
    "LLMConfigError",
    "LLMError",
    "Provider",
    "ProviderEvent",
    "ProviderMessage",
    "Role",
    "TextBlock",
    "TextDelta",
    "ToolResultBlock",
    "ToolUse",
    "ToolUseBlock",
    "Usage",
    "get_provider",
]
