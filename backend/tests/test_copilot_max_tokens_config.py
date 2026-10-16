"""COPILOT_MAX_TOKENS must reach the container (#332).

The setting was declared in `Settings` and read nowhere, then wired into
the bridge — but the backend service enumerates its environment with no
`env_file:`, so a value in `.env` never reaches the container. The remedy
the templates print has to be applicable where it is printed, or the
operator changes nothing and finds out from a truncated answer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.config import Settings

REPO = Path(__file__).resolve().parents[2]

# The compose files that list the backend's environment explicitly.
COMPOSE_FILES = ("docker-compose.yml", "docker-compose.prod.yml")


def _backend_env_block(compose: str) -> str:
    """The `environment:` block of the backend service, comments stripped."""
    text = (REPO / compose).read_text(encoding="utf-8")
    after = text.split("\n  backend:", 1)[1]
    nxt = re.search(r"^  \S", after, re.M)
    block = after[: nxt.start()] if nxt else after
    # A commented-out key is not a forwarded key.
    return "\n".join(ln for ln in block.splitlines() if not ln.strip().startswith("#"))


@pytest.mark.parametrize("compose", COMPOSE_FILES)
def test_compose_forwards_the_token_ceiling(compose: str) -> None:
    block = _backend_env_block(compose)
    match = re.search(r"^\s+COPILOT_MAX_TOKENS:\s*\$\{COPILOT_MAX_TOKENS:-([^}]*)\}", block, re.M)
    assert match, f"{compose} does not forward COPILOT_MAX_TOKENS to the backend"
    assert match.group(1).strip() == "4096", "compose default must match the Settings default"


def test_compose_default_matches_the_settings_default() -> None:
    """A drifting pair means the documented default is a lie in one place."""
    assert Settings.model_fields["COPILOT_MAX_TOKENS"].default == 4096


@pytest.mark.parametrize("template", (".env.example", ".env.prod.example"))
def test_templates_document_the_setting(template: str) -> None:
    """An operator cannot set what the example never mentions."""
    body = (REPO / template).read_text(encoding="utf-8")
    assert "COPILOT_MAX_TOKENS" in body, template


def test_the_setting_is_an_int() -> None:
    """`${COPILOT_MAX_TOKENS:-}` with no default would resolve to an empty
    string and fail bool/int parsing at boot, the way EMAIL_ENABLED did."""
    assert Settings.model_fields["COPILOT_MAX_TOKENS"].annotation is int
