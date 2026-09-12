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
    tier: Literal["paid", "free", "local"]
    default_model: str
    supports_tools: bool
    redaction_required: bool
    needs_api_key: bool
    factory: Callable[[ProviderConfig], Provider]
