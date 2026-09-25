"""Tests for the pluggable LLM provider registry."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace

import pytest

from app.config import settings
from app.core.llm.base import ProviderEvent
from app.core.llm.factory import ANTHROPIC_SPEC, OPENAI_SPEC, get_provider
from app.core.llm.registry import ProviderRegistry, llm_provider_registry
from app.core.llm.spec import ProviderConfig, ProviderSpec
from app.modules.copilot import CopilotModule


class _FakeProvider:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    async def complete(
        self,
        *,
        system: str,
        messages: list,
        tools: list[dict],
        model: str,
        max_tokens: int,
    ) -> AsyncIterator[ProviderEvent]:
        if False:
            yield  # pragma: no cover


def _spec(name: str = "fake") -> ProviderSpec:
    return ProviderSpec(
        name=name,
        label="Fake",
        default_model="fake-model",
        tool_dialect="openai",
        needs_api_key=False,
        api_key_setting=None,
        factory=_FakeProvider,
    )


def test_registry_register_get_list_and_unregister() -> None:
    registry = ProviderRegistry()
    spec = _spec()

    registry.register(spec)

    assert registry.get("fake") is spec
    assert registry.list() == [spec]

    registry.unregister("fake")
    assert registry.get("fake") is None


def test_registry_registration_is_idempotent() -> None:
    registry = ProviderRegistry()
    spec = _spec()

    registry.register(spec)
    registry.register(spec)

    assert registry.list() == [spec]


def test_registry_registration_overrides_different_spec() -> None:
    registry = ProviderRegistry()
    original = _spec()
    override = replace(original, label="Replacement")

    registry.register(original)
    registry.register(override)

    assert registry.get("fake") is override
    assert registry.list() == [override]


def test_provider_spec_requires_key_setting_when_key_is_needed() -> None:
    with pytest.raises(ValueError, match="api_key_setting is missing"):
        replace(_spec(), needs_api_key=True)


def test_copilot_activation_registers_builtin_providers() -> None:
    previous_specs = {
        "openai": llm_provider_registry.get("openai"),
        "anthropic": llm_provider_registry.get("anthropic"),
    }
    llm_provider_registry.unregister("openai")
    llm_provider_registry.unregister("anthropic")

    try:
        module = CopilotModule()
        module.on_activate()

        assert llm_provider_registry.get("openai") is OPENAI_SPEC
        assert llm_provider_registry.get("anthropic") is ANTHROPIC_SPEC

        module.on_activate()

        assert llm_provider_registry.get("openai") is OPENAI_SPEC
        assert llm_provider_registry.get("anthropic") is ANTHROPIC_SPEC
    finally:
        llm_provider_registry.unregister("openai")
        llm_provider_registry.unregister("anthropic")
        for spec in previous_specs.values():
            if spec is not None:
                llm_provider_registry.register(spec)


def test_factory_resolves_registered_provider() -> None:
    captured: list[ProviderConfig] = []

    def factory(config: ProviderConfig) -> _FakeProvider:
        captured.append(config)
        return _FakeProvider(config)

    spec = ProviderSpec(
        name="test-provider",
        label="Test Provider",
        default_model="test-model",
        tool_dialect="openai",
        needs_api_key=True,
        api_key_setting="OPENAI_API_KEY",
        factory=factory,
    )
    llm_provider_registry.register(spec)

    try:
        provider = get_provider("test-provider", api_key="secret")
        assert isinstance(provider, _FakeProvider)
        assert captured == [ProviderConfig(api_key="secret")]
    finally:
        llm_provider_registry.unregister("test-provider")


def test_factory_reads_deployment_key_named_by_spec(monkeypatch) -> None:
    spec = replace(
        _spec("deployment-key-provider"),
        needs_api_key=True,
        api_key_setting="OPENAI_API_KEY",
    )
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "deployment-key")
    llm_provider_registry.register(spec)

    try:
        provider = get_provider(spec.name)
        assert isinstance(provider, _FakeProvider)
        assert provider.config == ProviderConfig(api_key="deployment-key")
    finally:
        llm_provider_registry.unregister(spec.name)
