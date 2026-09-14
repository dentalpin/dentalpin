"""Bearer-token auth for the MCP endpoint (``dp_`` API tokens, not JWT).

The main API authenticates staff via JWT + RBAC. The MCP endpoint is
machine-to-machine: clients authenticate with the same ``dp_`` admin-issued
API tokens the integrations module already owns (issue #65). This ASGI
middleware wraps the streamable-HTTP app and enforces:

- a `dp_` prefix and a live (unrevoked) `ApiToken` row — else 401;
- the ``patients:read`` scope on the token — else 403.

On success it stores the resolved identity on ``scope["state"]["dentalpin"]``
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
from app.modules.integrations.service import IntegrationsService

# Scope the token must carry to reach the MCP tools (mirrors the public
# data-read API). When integrations grows a write scope (``patients:write``)
# the curated tool set can expand alongside it.
REQUIRED_SCOPE = "patients:read"

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
        identity = await self._authenticate(scope)
        if identity is None:
            await self._reject(
                send,
                status_code=401,
                error="invalid_token",
                description="Missing, invalid, or revoked API token",
            )
            return
        if REQUIRED_SCOPE not in identity["scopes"]:
            await self._reject(
                send,
                status_code=403,
                error="insufficient_scope",
                description=f"Required scope: {REQUIRED_SCOPE}",
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
            token = await IntegrationsService.authenticate_token(db, plaintext)
            if token is None:
                return None
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
