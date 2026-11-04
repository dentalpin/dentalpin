"""Read a compose file's backend service, for tests that a setting reaches it."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def backend_block(compose_name: str) -> str:
    """The backend service's slice of a compose file, comment lines removed.

    A commented-out key is not a forwarded key.
    """
    path = REPO_ROOT / compose_name
    assert path.exists(), f"missing compose file: {compose_name}"
    after = path.read_text(encoding="utf-8").split("\n  backend:", 1)[1]
    # The next service starts at exactly two spaces + a name; anything more
    # indented still belongs to backend.
    nxt = re.search(r"^  \S", after, re.M)
    block = after[: nxt.start()] if nxt else after
    return "\n".join(line for line in block.splitlines() if not line.strip().startswith("#"))


def forwarded_keys(compose_name: str) -> set[str]:
    """The environment keys the backend service passes through."""
    return set(re.findall(r"^\s{6}([A-Z][A-Z0-9_]*):", backend_block(compose_name), re.M))
