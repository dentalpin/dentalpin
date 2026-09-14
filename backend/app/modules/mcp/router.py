"""ASGI wiring for the MCP endpoint.

The streamable-HTTP session manager has its own lifespan (``run()``) that
spawns per-session tasks inside a task group. Starlette never runs a *mounted*
sub-app's lifespan, so this module wraps the manager in a tiny lazy-runner:
the first HTTP request starts a background task that enters
``session_manager.run()`` for the life of the process, then forwards every
request into the manager's ASGI app. Requests that never get here (no token,
wrong scope) are rejected by the auth middleware before the runner is touched.

``build_mcp_router()`` returns a fresh, independent instance each call — the
manager cannot be reused after its ``run()`` context ends, and tests build a
router per event loop.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from mcp.server.streamable_http_manager import (
    StreamableHTTPASGIApp,
    StreamableHTTPSessionManager,
)
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .auth import DentalPinAuthMiddleware
from .server import build_mcp_server

logger = logging.getLogger(__name__)


class _LazyManagedMCPApp:
    """ASGI app that starts the session manager's ``run()`` on first use."""

    def __init__(self, manager: StreamableHTTPSessionManager, raw_app: ASGIApp):
        self._manager = manager
        self._raw_app = raw_app
        self._started = False
        self._ready = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self._ensure_started()
        if scope["type"] != "http":
            await self._raw_app(scope, receive, send)
            return
        await self._ready.wait()
        await self._raw_app(scope, receive, send)

    def _ensure_started(self) -> None:
        # Synchronous guard: no await between check and set, so concurrent
        # first requests cannot double-start the manager.
        if self._started:
            return
        self._started = True
        self._task = asyncio.get_running_loop().create_task(self._run_manager())

    async def _run_manager(self) -> None:
        try:
            async with self._manager.run():
                self._ready.set()
                # Keep the manager alive for the life of the process. Nothing
                # signals this event today; it exists so shutdown wiring can
                # stop the manager cleanly if that is ever surfaced.
                await asyncio.Event().wait()
        except Exception:
            logger.exception("MCP session manager failed to start")
        finally:
            self._ready.set()  # never deadlock a waiter


def build_mcp_router() -> APIRouter:
    """Build the MCP router (fresh session manager per call)."""
    server = build_mcp_server()
    manager = StreamableHTTPSessionManager(server, json_response=True)
    raw_app = StreamableHTTPASGIApp(manager)
    gated_app = DentalPinAuthMiddleware(_LazyManagedMCPApp(manager, raw_app))

    router = APIRouter()

    @router.post("", include_in_schema=False)
    async def _redirect_to_slashed(request: Request) -> RedirectResponse:
        # The real endpoint is the mount below (trailing slash). Keep the
        # bare path working too: MCP SDK clients follow same-origin 307s
        # while preserving method and body. (redirect_slashes is off app-wide.)
        return RedirectResponse(request.url.path + "/", status_code=307)

    # Mount the full MCP surface (initialize + session streams) under this
    # path.
    router.mount("/", gated_app)
    return router
