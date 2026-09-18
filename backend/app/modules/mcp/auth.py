"""Bearer-token auth for the MCP endpoint (``dp_`` API tokens, not JWT).

The main API authenticates staff via JWT + RBAC. The MCP endpoint is
machine-to-machine: clients authenticate with the same ``dp_`` admin-issued
API tokens the integrations module already owns (issue #65). This ASGI
middleware wraps the streamable-HTTP app and enforces:

- a `dp_` prefix and a live (unrevoked) `ApiToken` row — else 401;
- the shared per-token fixed-window rate limit (same limits as the
  integrations public API; enforced inside
  `IntegrationsService.authenticate_token`) — else 429, so `initialize`,
  `tools/list`, `tools/call` and bad-token floods stay bounded;
- at least one MCP-supported scope (`patients:read` / `patients:write`) on
  the token — else 403.

On success it stamps the token's `last_used_at` (via the shared helper) so
an admin can see machine usage on the token list, and it stores the resolved
identity on ``scope["state"]["dentalpin"]``
(clinic id, token id, scopes) so the lowlevel ``tools/call`` handler can read
it back from the per-message starlette request it receives (``ctx.request``),
and it sets ``scope["user"]``/``scope["auth"]`` for the SDK's session-owner
binding (a session may only be reused by the credential that created it).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from starlette.authentication import AuthCredentials
from starlette.types import ASGIApp, Receive, Scope, Send

from app.database import async_session_maker
from app.modules.integrations.service import IntegrationsService, RateLimitError

# Scopes that authorize access to the MCP surface (subset of the integration
# token catalog). The token must carry at least one; per-tool visibility and
# RBAC enforcement happen inside server.py, which translates the token's
# scopes into the RBAC grants the curated tools declare.
MCP_SCOPES: frozenset[str] = frozenset({"patients:read", "patients:write"})

_IDENTITY_KEY = "dentalpin"

# ``AuthenticatedUser`` only feeds the SDK's principal comparison (client_id,
# issuer, subject) — the raw token string itself never leaves this process,
# so a placeholder keeps the comparison deterministic without echoing the
# secret into ASGI scope.
_TOKEN_PLACEHOLDER = "dp_<authorized>"


class DentalPinAuthMiddleware:
    """ASGI middleware requiring a valid ``dp_`` API token on every request."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            identity = await self._authenticate(scope)
        except RateLimitError as exc:
            await self._reject(
                send,
                status_code=429,
                error="rate_limited",
                description=(
                    "Rate limit exceeded for this API token. "
                    f"Retry after {exc.retry_after_seconds}s"
                ),
            )
            return
        if identity is None:
            await self._reject(
                send,
                status_code=401,
                error="invalid_token",
                description="Missing, invalid, or revoked API token",
            )
            return
        if not (MCP_SCOPES & set(identity["scopes"])):
            await self._reject(
                send,
                status_code=403,
                error="insufficient_scope",
                description=f"Required scopes: {', '.join(sorted(MCP_SCOPES))}",
            )
            return

        scope.setdefault("state", {})[_IDENTITY_KEY] = identity
        scope["user"] = AuthenticatedUser(
            AccessToken(
                token=_TOKEN_PLACEHOLDER,
                client_id=f"dp:{identity['token_id']}",
                scopes=identity["scopes"],
                subject=f"clinic:{identity['clinic_id']}",
            )
        )
        scope["auth"] = AuthCredentials(identity["scopes"])
        await self.app(scope, receive, send)

    @staticmethod
    async def _authenticate(scope: Scope) -> dict[str, Any] | None:
        authorization = next(
            (
                v.decode("latin-1")
                for k, v in scope.get("headers") or []
                if k.lower() == b"authorization"
            ),
            None,
        )
        if not authorization or not authorization.startswith("Bearer "):
            return None
        plaintext = authorization.removeprefix("Bearer ").strip()

        async with async_session_maker() as db:
            auth = await IntegrationsService.authenticate_token(db, plaintext)
            if auth is None:
                return None
            # Commit so the helper's ``last_used_at`` stamp survives this
            # short-lived session; rate limiting is enforced inside the helper.
            await db.commit()
            token = auth.token
            scopes = list(token.scopes or [])
        return {
            "token_id": UUID(str(token.id)),
            "clinic_id": token.clinic_id,
            "scopes": scopes,
        }

    @staticmethod
    async def _reject(send: Send, *, status_code: int, error: str, description: str) -> None:
        body = json.dumps({"error": error, "error_description": description}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
