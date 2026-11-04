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
from tests._compose import backend_block

REPO = Path(__file__).resolve().parents[2]

# The compose files that list the backend's environment explicitly.
COMPOSE_FILES = ("docker-compose.yml", "docker-compose.prod.yml")


@pytest.mark.parametrize("compose", COMPOSE_FILES)
def test_compose_forwards_the_token_ceiling(compose: str) -> None:
    """The compose default must equal the Settings default, not repeat it as a
    second literal, so the pair is actually checked.

    `${COPILOT_MAX_TOKENS:-}` with no default would resolve to an empty
    string and fail int parsing at boot, the way EMAIL_ENABLED did.
    """
    block = backend_block(compose)
    match = re.search(r"^\s+COPILOT_MAX_TOKENS:\s*\$\{COPILOT_MAX_TOKENS:-([^}]*)\}", block, re.M)
    assert match, f"{compose} does not forward COPILOT_MAX_TOKENS to the backend"
    default = str(Settings.model_fields["COPILOT_MAX_TOKENS"].default)
    assert match.group(1).strip() == default, "compose default must match the Settings default"


@pytest.mark.parametrize("template", (".env.example", ".env.prod.example"))
def test_templates_document_the_setting(template: str) -> None:
    """An operator cannot set what the example never mentions."""
    body = (REPO / template).read_text(encoding="utf-8")
    assert "COPILOT_MAX_TOKENS" in body, template


def test_the_setting_is_an_int() -> None:
    """The field parses as an int so the env value cannot be free text."""
    assert Settings.model_fields["COPILOT_MAX_TOKENS"].annotation is int
