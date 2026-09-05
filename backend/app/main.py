"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.router import limiter
from app.core.auth.router import router as auth_router
from app.core.log_context import (
    new_request_id,
    reset_request_context,
    set_request_context,
    setup_logging,
)
from app.core.plugins.loader import mount_modules, register_discovered
from app.core.plugins.processor import PendingProcessor
from app.core.plugins.service import ModuleService
from app.core.scheduler import init_scheduler, shutdown_scheduler
from app.core.schemas import ErrorResponse
from app.database import async_session_maker, engine, get_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown."""
    # Logging: attach the context filter early so every line emitted
    # during startup / module install also carries the bound fields
    # (defaults to ``-`` outside a request).
    setup_logging()

    # Security posture (audit SEC-01): public budget sessions fall back to
    # SECRET_KEY when BUDGET_PUBLIC_SECRET_KEY is unset. Warn once in
    # production; behavior unchanged (hard-requiring would break existing
    # deploys that rely on the fallback).
    if settings.ENVIRONMENT == "production" and not settings.BUDGET_PUBLIC_SECRET_KEY:
        logger.warning(
            "BUDGET_PUBLIC_SECRET_KEY is unset: public budget sessions fall "
            "back to SECRET_KEY. Set a dedicated key in production."
        )

    # Startup — discover everything, settle DB state, then mount only what
    # is installed (issue #91). Order matters: the processor may install or
    # remove modules in this very boot, and the mount step reads the result.
    discovered = register_discovered()

    # Sync in-memory registry into core_module (best-effort).
    try:
        async with async_session_maker() as session:
            await ModuleService(session).reconcile_with_db()
    except Exception:
        logger.exception("Module registry reconciliation failed at startup")

    # Process pending install/uninstall/upgrade operations.
    try:
        processor = PendingProcessor(async_session_maker)
        processed = await processor.run()
        if processed:
            logger.info("Processed pending module operations: %s", processed)
    except Exception:
        logger.exception("Pending module processor raised")

    # Not best-effort: if the DB is unreachable here, booting with zero
    # modules would serve a healthy-looking but empty API. Let it raise —
    # the container restarts and retries, as it already does when the
    # entrypoint's migrations fail.
    async with async_session_maker() as session:
        installed = await ModuleService.installed_names(session)
    mounted = mount_modules(app, [m for m in discovered if m.name in installed])
    logger.info(
        "Mounted %d/%d modules: %s", len(mounted), len(discovered), [m.name for m in mounted]
    )

    # Initialize scheduler for background jobs (active modules only)
    init_scheduler()

    yield

    # Shutdown
    shutdown_scheduler()
    await engine.dispose()


app = FastAPI(
    title="DentalPin API",
    description="Open source dental clinic management software",
    version="2.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
)

# Configure rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Configure CORS
allowed_origins = settings.allowed_origins_list.copy()
if settings.ENVIRONMENT == "development":
    allowed_origins.extend(
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ]
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Bind ``request_id`` for the lifetime of one HTTP request.

    Accepts an inbound ``X-Request-Id`` so a load balancer / client
    can correlate traces; otherwise mints a fresh short id. Echoes
    the value back on the response (success or error) so the caller
    can grep server logs. ``clinic_id`` / ``user_id`` are bound later
    by the auth dependency once they are known.
    """
    incoming = request.headers.get("x-request-id")
    rid = incoming if incoming and len(incoming) <= 64 else new_request_id()
    tokens = set_request_context(request_id=rid)
    try:
        response = await call_next(request)
    finally:
        reset_request_context(tokens)
    response.headers["X-Request-Id"] = rid
    return response


def _cors_headers(request: Request) -> dict[str, str]:
    # CORSMiddleware can't add headers to responses produced by exception
    # handlers (BaseHTTPMiddleware-based stacks lose the response when an
    # exception escapes). Without these headers, browsers report any 5xx
    # as a network error ("can't connect to server") instead of surfacing
    # the real status — which masks bugs and confuses users. So we mirror
    # CORSMiddleware's allow-list logic here for error responses.
    origin = request.headers.get("origin")
    if not origin:
        return {}
    if origin in allowed_origins or "*" in allowed_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler for HTTP exceptions using standard ErrorResponse format."""
    error_response = ErrorResponse(
        message=str(exc.detail),
        errors=[str(exc.detail)] if exc.detail else [],
    )
    headers = dict(exc.headers or {})
    headers.update(_cors_headers(request))
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
        headers=headers,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    logger.exception("Unhandled exception", exc_info=exc)
    if settings.ENVIRONMENT == "development":
        error_response = ErrorResponse(
            message=str(exc),
            errors=[str(exc)],
        )
    else:
        error_response = ErrorResponse(
            message="Internal server error",
            errors=[],
        )
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump(),
        headers=_cors_headers(request),
    )


# Mount auth router
app.include_router(auth_router, prefix="/api/v1")

# Mount module management router (install/uninstall/upgrade/restart).
from app.core.plugins.router import router as modules_router  # noqa: E402

app.include_router(modules_router, prefix="/api/v1")

# Mount AI agents infrastructure router (approval queue, audit, agent CRUD).
from app.core.agents.router import router as agents_router  # noqa: E402

app.include_router(agents_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> JSONResponse:
    """Liveness probe — process is up.

    Used by the proxy/orchestrator to decide whether the container should
    receive traffic. Must NOT depend on the DB: a transient DB blip should
    not pull the backend out of the load balancer (we used to do that and
    Cloudflare ended up serving "no available server" until someone redeployed
    by hand).
    """
    return JSONResponse(content={"status": "healthy", "version": "2.0.0"})


@app.get("/health/ready")
async def readiness_check(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Readiness probe — schema is reachable.

    Probes a core table so monitoring catches the case where the DB volume
    gets recreated under a running container (schema gone, every business
    endpoint 500s). Recovery from that state belongs in the entrypoint
    (`dentalpin db upgrade`) plus an explicit container restart — not in
    the proxy healthcheck, since Docker's `restart: unless-stopped` does
    not auto-restart on healthcheck failure.
    """
    try:
        await db.execute(text("SELECT 1 FROM users LIMIT 1"))
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "unready", "version": "2.0.0", "error": str(exc)},
        )
    return JSONResponse(content={"status": "ready", "version": "2.0.0"})


@app.get("/api/v1")
async def api_root() -> dict:
    """API root endpoint."""
    return {
        "message": "DentalPin API",
        "version": "2.0.0",
        "docs": "/docs" if settings.ENVIRONMENT == "development" else None,
    }
