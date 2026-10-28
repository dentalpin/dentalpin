"""Every provider's API key must reach the container in both prod stacks.

The copilot's key comes from deployment settings and nowhere else:
``CopilotSettings`` stores ``provider`` and ``model`` but no key, and
``copilot/bridge.py`` calls ``get_provider(conv.provider)`` without one,
so ``get_configured_api_key`` reads ``settings.<SPEC>_API_KEY``. Neither
production compose file declares ``env_file``, which means a key that is
not listed under the backend service's ``environment:`` is empty inside
the container whatever the operator sets on the host — and every copilot
request then raises ``LLMConfigError``.

That is how the Coolify stack shipped with no LLM key at all while
``docker-compose.prod.yml`` carried three. This closes the gap for every
provider that exists now and every one added later: the keys come off the
registered ``ProviderSpec``s rather than a list restated here, so a new
provider fails this test until its key is forwarded too.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.llm.registry import llm_provider_registry
from app.modules.copilot import CopilotModule

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Both documented production entry points, so both carry the same settings.
PRODUCTION_COMPOSE = ("docker-compose.prod.yml", "docker-compose.coolify.yml")


def _backend_env_block(compose_name: str) -> str:
    """The backend service's slice of a compose file, as text."""
    path = REPO_ROOT / compose_name
    assert path.exists(), f"missing compose file: {compose_name}"
    body = path.read_text(encoding="utf-8")
    after = body.split("\n  backend:", 1)[1]
    # The next service starts at exactly two spaces + a name; anything
    # more deeply indented still belongs to backend.
    nxt = re.search(r"^  \S", after, re.M)
    return after[: nxt.start()] if nxt else after


def _forwarded_keys(compose_name: str) -> set[str]:
    return set(re.findall(r"^\s{6}([A-Z][A-Z0-9_]*):", _backend_env_block(compose_name), re.M))


def _api_key_settings() -> set[str]:
    """Every ``*_API_KEY`` and base-URL setting a built-in provider spec names.

    Read from the registry the copilot module populates, so this follows
    the providers instead of restating them.
    """
    CopilotModule().on_activate()
    specs = llm_provider_registry.list()
    keys = {spec.api_key_setting for spec in specs if spec.api_key_setting}
    # A keyless provider (Ollama) is configured by its endpoint instead,
    # and that setting has the same failure mode when it is not forwarded.
    keys |= {spec.base_url_setting for spec in specs if spec.base_url_setting}
    # Sanity floor: an empty or near-empty set would make the assertions
    # below pass vacuously, which is what a guard like this rots into.
    assert len(keys) >= 3, f"provider key set looks wrong: {sorted(keys)}"
    return keys


@pytest.mark.parametrize("compose_name", PRODUCTION_COMPOSE)
def test_production_compose_forwards_every_provider_api_key(compose_name: str) -> None:
    missing = sorted(_api_key_settings() - _forwarded_keys(compose_name))
    assert not missing, (
        f"{compose_name} does not forward {missing} to the backend; the copilot "
        "raises LLMConfigError for those providers no matter what the operator sets"
    )


@pytest.mark.parametrize("compose_name", PRODUCTION_COMPOSE)
def test_provider_api_keys_are_optional_not_required(compose_name: str) -> None:
    """A missing key disables the assistant; it must not block boot.

    ``${VAR:?...}`` refuses to start and bare ``${VAR}`` makes compose
    warn, so every optional key uses the explicit ``${VAR:-}`` form —
    the shape the required secrets deliberately do *not* use.
    """
    block = _backend_env_block(compose_name)
    wrong = []
    for key in sorted(_api_key_settings()):
        match = re.search(rf"^\s+{key}: (\S+)", block, re.M)
        assert match, f"{compose_name}: {key} not forwarded"
        if match.group(1) != f"${{{key}:-}}":
            wrong.append(f"{key}={match.group(1)}")
    assert not wrong, f"{compose_name}: {wrong} should use the ${{{{VAR:-}}}} optional form"
