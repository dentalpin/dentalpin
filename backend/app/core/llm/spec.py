"""Metadata and runtime configuration for pluggable LLM providers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.core.llm.base import Provider


@dataclass(frozen=True)
class ProviderConfig:
    """Runtime configuration used to construct an LLM provider."""

    api_key: str | None = None
    base_url: str | None = None


@dataclass(frozen=True)
class ProviderSpec:
    """Describe an LLM provider and how to construct it."""

    name: str
    label: str
    default_model: str
    tool_dialect: Literal["openai", "anthropic"]
    needs_api_key: bool
    api_key_setting: str | None
    factory: Callable[[ProviderConfig], Provider]

    def __post_init__(self) -> None:
        if self.needs_api_key and not self.api_key_setting:
            raise ValueError(
                f"Provider {self.name!r} needs an API key but api_key_setting is missing"
            )
