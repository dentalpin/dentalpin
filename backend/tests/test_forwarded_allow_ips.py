"""The trusted-proxy set for uvicorn's ``--proxy-headers`` (#623).

``X-Forwarded-For`` is a client-writable header. uvicorn only reads it
for peers listed in ``FORWARDED_ALLOW_IPS``, and the literal ``*`` means
every peer: uvicorn then returns the **leftmost** entry, the one the
caller wrote. The login rate limit keys on ``request.client.host``
(``get_remote_address``, ``core/auth/router.py``), so with ``*`` a
client that sends a fresh ``X-Forwarded-For`` per attempt gets a fresh
bucket per attempt and the limit stops existing. The session's
``client_ip`` comes from the same value, so the audit trail follows.

These tests drive uvicorn's real ``ProxyHeadersMiddleware`` with the
value the compose files actually ship, so a future edit back to ``*``
fails here rather than in production.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from slowapi.util import get_remote_address
from starlette.requests import Request
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

REPO = Path(__file__).resolve().parents[2]
COMPOSE_FILES = (
    "docker-compose.yml",
    "docker-compose.prod.yml",
    "docker-compose.coolify.yml",
)

# The peer the proxy would reach the backend from, inside a Docker network.
TRUSTED_PEER = "172.18.0.5"
# A peer that is not a proxy at all — a client hitting an exposed port.
UNTRUSTED_PEER = "203.0.113.7"


def _shipped_default(compose: str) -> str:
    """The ``${FORWARDED_ALLOW_IPS:-...}`` default from a compose file."""
    text = (REPO / compose).read_text(encoding="utf-8")
    match = re.search(r"FORWARDED_ALLOW_IPS:\s*\$\{FORWARDED_ALLOW_IPS:-([^}]*)\}", text)
    assert match, f"{compose} declares no FORWARDED_ALLOW_IPS default"
    return match.group(1).strip()


async def _resolved_client(trusted: str, peer: str, forwarded: str | None) -> str:
    """Run the real middleware and report what the app layer would see."""
    seen: dict[str, str] = {}

    async def app(scope, receive, send):
        request = Request(scope)
        # Exactly what the limiter keys on.
        seen["key"] = get_remote_address(request)

    headers = [(b"host", b"api.example.com")]
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode()))

    scope = {
        "type": "http",
        "scheme": "http",
        "method": "GET",
        "path": "/api/v1/auth/login",
        "headers": headers,
        "client": (peer, 44321),
    }
    await ProxyHeadersMiddleware(app, trusted_hosts=trusted)(scope, None, None)
    return seen["key"]


# --- what every shipped deployment must guarantee ------------------------


@pytest.mark.parametrize("compose", COMPOSE_FILES)
def test_no_compose_file_trusts_every_peer(compose: str) -> None:
    assert _shipped_default(compose) != "*"


def test_no_deploy_file_passes_the_wildcard_flag() -> None:
    """A CLI flag beats the env var, so neither may carry ``*`` either."""
    offenders = []
    for rel in (*COMPOSE_FILES, "backend/Dockerfile"):
        for lineno, line in enumerate((REPO / rel).read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            # Both spellings: shell form (--flag=* / --flag *) and the
            # Dockerfile JSON exec form ("--flag", "*").
            if re.search(r'--forwarded-allow-ips["\']?\s*[=,]?\s*["\']?\*', line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


@pytest.mark.asyncio
@pytest.mark.parametrize("compose", COMPOSE_FILES)
async def test_spoofed_header_from_an_untrusted_peer_is_ignored(compose: str) -> None:
    """The issue's acceptance test: the rate-limit key must not move."""
    trusted = _shipped_default(compose)
    keys = {
        await _resolved_client(trusted, UNTRUSTED_PEER, spoof)
        for spoof in ("9.9.9.9", "198.51.100.44", "203.0.113.99", "10.1.2.3")
    }
    assert keys == {UNTRUSTED_PEER}


@pytest.mark.asyncio
@pytest.mark.parametrize("compose", COMPOSE_FILES)
async def test_a_real_proxy_still_delivers_the_real_client(compose: str) -> None:
    """The other half: tightening this must not collapse every client
    onto the proxy's IP, which would make the login limit global."""
    trusted = _shipped_default(compose)
    assert await _resolved_client(trusted, TRUSTED_PEER, "198.51.100.23") == "198.51.100.23"


@pytest.mark.asyncio
async def test_coolify_traefik_peer_is_trusted() -> None:
    """Coolify puts its networks in 10.0.x (Traefik reached prod from
    10.0.2.5); untrusted, every client became Traefik's IP."""
    trusted = _shipped_default("docker-compose.coolify.yml")
    assert await _resolved_client(trusted, "10.0.2.5", "198.51.100.23") == "198.51.100.23"


@pytest.mark.asyncio
@pytest.mark.parametrize("compose", COMPOSE_FILES)
async def test_an_appending_proxy_does_not_let_the_forged_entry_win(compose: str) -> None:
    """A proxy that appends rather than overwrites leaves the client's
    own entry on the left. Restricted, uvicorn walks right-to-left and
    stops at the first untrusted hop, so the appended real client wins.
    This is the case ``*`` gets wrong even behind a proxy."""
    trusted = _shipped_default(compose)
    forged_then_real = "9.9.9.9, 198.51.100.23"
    assert await _resolved_client(trusted, TRUSTED_PEER, forged_then_real) == "198.51.100.23"


# --- the behaviour being fixed, pinned so the value keeps mattering ------


@pytest.mark.asyncio
async def test_wildcard_is_the_bypass_this_guards_against() -> None:
    keys = {
        await _resolved_client("*", UNTRUSTED_PEER, spoof)
        for spoof in ("9.9.9.9", "198.51.100.44", "203.0.113.99")
    }
    assert len(keys) == 3, "a fresh bucket per request is the bypass"
    assert await _resolved_client("*", TRUSTED_PEER, "9.9.9.9, 198.51.100.23") == "9.9.9.9"


# --- the plumbing the whole fix rests on ---------------------------------


def test_uvicorn_reads_the_env_var_when_the_flag_is_absent() -> None:
    """The Dockerfile deliberately passes no ``--forwarded-allow-ips``, so
    everything above depends on uvicorn picking the value out of the
    environment. That is one line in uvicorn's own Config
    (``os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1,::1")``) and
    nothing in this repo would notice if a future release moved it: the
    CMD would silently fall back to uvicorn's default, which is safe but
    collapses every client onto the proxy's IP and makes the login limit
    global. Pinned here so an upgrade that breaks it fails loudly.
    """
    from uvicorn.config import Config

    previous = os.environ.get("FORWARDED_ALLOW_IPS")
    try:
        os.environ["FORWARDED_ALLOW_IPS"] = "10.9.8.7,172.16.0.0/12"
        config = Config("app.main:app", proxy_headers=True)
        assert config.forwarded_allow_ips == "10.9.8.7,172.16.0.0/12"

        del os.environ["FORWARDED_ALLOW_IPS"]
        fallback = Config("app.main:app", proxy_headers=True)
        # Safe, but not what we ship — see the comment above.
        assert fallback.forwarded_allow_ips == "127.0.0.1,::1"
        assert "*" not in str(fallback.forwarded_allow_ips)
    finally:
        os.environ.pop("FORWARDED_ALLOW_IPS", None)
        if previous is not None:
            os.environ["FORWARDED_ALLOW_IPS"] = previous


# --- the session audit trail ---------------------------------------------


def test_client_ip_ignores_the_forwarded_header() -> None:
    """``_client_ip`` stores the session's ``client_ip``; it must not
    re-parse the header uvicorn already adjudicated."""
    from app.core.auth.router import _client_ip

    scope = {
        "type": "http",
        "scheme": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": [(b"x-forwarded-for", b"9.9.9.9")],
        "client": (UNTRUSTED_PEER, 44321),
    }
    assert _client_ip(Request(scope)) == UNTRUSTED_PEER


def test_client_ip_survives_a_missing_peer() -> None:
    from app.core.auth.router import _client_ip

    scope = {"type": "http", "scheme": "http", "method": "GET", "path": "/", "headers": []}
    assert _client_ip(Request(scope)) is None
