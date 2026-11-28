"""Public data-read API — token-authenticated, clinic-scoped (issue #65 §2).

Where router.py handles admin CRUD (staff JWT + ``require_permission``),
this router is the *consumer* endpoint for API tokens (issue #65 §11):
third-party automations authenticate with ``Authorization: Bearer dp_...``
against the token's scopes and read clinic data without a staff account.

Design notes:
- Scope enforcement is a dependency factory (``require_scope``) mirroring
  ``require_permission``'s shutdown — a token missing the scope gets 403.
- Rate limiting is a per-token fixed window (per-minute + per-day),
  surfaced in ``X-RateLimit-*`` response headers and enforced with 429.
  In-memory per claim-process — a multi-worker deployment shares nothing
  here; documented limitation, same as any other in-process limiter.
- Read paths reuse ``PatientService`` (patients is in ``manifest.depends``)
  rather than duplicating query logic, and every query is clinic-scoped off
  the *token's* clinic, not a JWT clinic context.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from ..patients.models import Patient
from ..patients.service import PatientService
from .models import ApiToken
from .schemas import PublicPatientResponse, PublicTokenInfo
from .service import _TOKEN_PREFIX, _hash_token

public_router = APIRouter()

# Per-token fixed-window rate limits (issue #65 §2: "per token, per minute
# + per day, surfaced in headers"). In-memory per process — see module
# docstring.
RATE_LIMIT_PER_MINUTE = 60
RATE_LIMIT_PER_DAY = 1000

_WINDOW_SECONDS_MINUTE = 60
_WINDOW_SECONDS_DAY = 86400


class _RateWindow:
    __slots__ = ("start", "count")

    def __init__(self) -> None:
        self.start = int(time.time())
        self.count = 0


# token_id -> per-window counters. Bounded by the number of tokens a clinic
# issues; entries are reset (not deleted) on window rollover so this never
# grows unboundedly.
_rate_windows: dict[UUID, dict[str, _RateWindow]] = {}


class PublicTokenContext:
    """Authenticated API-token request context: token + resolved clinic."""

    def __init__(self, token: ApiToken, rate_headers: dict[str, str]):
        self.token = token
        self.clinic_id = token.clinic_id
        self.scopes = token.scopes or []
        self.rate_headers = rate_headers


def _rate_limit(token_id: UUID) -> dict[str, str]:
    """Fixed-window check; raises 429 when over. Returns header values."""
    now = int(time.time())
    windows = _rate_windows.setdefault(token_id, {})

    minute = windows.setdefault("minute", _RateWindow())
    day = windows.setdefault("day", _RateWindow())

    if now - minute.start >= _WINDOW_SECONDS_MINUTE:
        minute.start, minute.count = now, 0
    if now - day.start >= _WINDOW_SECONDS_DAY:
        day.start, day.count = now, 0

    minute.count += 1
    day.count += 1

    if minute.count > RATE_LIMIT_PER_MINUTE or day.count > RATE_LIMIT_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for this API token.",
            headers={"Retry-After": str(_WINDOW_SECONDS_MINUTE)},
        )

    return {
        "X-RateLimit-Limit-Minute": str(RATE_LIMIT_PER_MINUTE),
        "X-RateLimit-Remaining-Minute": str(RATE_LIMIT_PER_MINUTE - minute.count),
        "X-RateLimit-Limit-Day": str(RATE_LIMIT_PER_DAY),
        "X-RateLimit-Remaining-Day": str(RATE_LIMIT_PER_DAY - day.count),
        "X-RateLimit-Reset": str(minute.start + _WINDOW_SECONDS_MINUTE),
    }


async def get_api_token_context(
    authorization: Annotated[str | None, Header()] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> PublicTokenContext:
    """Resolve ``dp_`` bearer token -> ApiToken, or 401/403."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    plaintext = authorization.removeprefix("Bearer ").strip()
    if not plaintext.startswith(_TOKEN_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = (
        await db.execute(select(ApiToken).where(ApiToken.token_hash == _hash_token(plaintext)))
    ).scalar_one_or_none()

    if token is None or token.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    rate_headers = _rate_limit(token.id)
    # Usage tracking for the admin token list — committed with the
    # request's session on success.
    token.last_used_at = datetime.now(UTC)
    return PublicTokenContext(token=token, rate_headers=rate_headers)


def require_scope(scope: str):
    """Dependency factory: reject a token that lacks ``scope`` (403)."""

    async def _scope_checker(
        ctx: Annotated[PublicTokenContext, Depends(get_api_token_context)],
    ) -> None:
        if scope not in ctx.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token does not have scope: {scope}",
            )

    return _scope_checker


@public_router.get("/ping", response_model=ApiResponse[PublicTokenInfo])
async def ping(
    response: Response,
    ctx: Annotated[PublicTokenContext, Depends(get_api_token_context)],
) -> ApiResponse[PublicTokenInfo]:
    """Token introspection — what a Zapier/Make app calls as its auth
    test. Any valid (unrevoked) token may ping; no scope required."""
    response.headers.update(ctx.rate_headers)
    return ApiResponse(
        data=PublicTokenInfo(
            clinic_id=ctx.clinic_id, token_name=ctx.token.name, scopes=list(ctx.scopes)
        )
    )


@public_router.get("/patients", response_model=PaginatedApiResponse[PublicPatientResponse])
async def list_public_patients(
    response: Response,
    ctx: Annotated[PublicTokenContext, Depends(get_api_token_context)],
    _: Annotated[None, Depends(require_scope("patients:read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = None,
    phone: str | None = Query(default=None, max_length=32),
    email: str | None = Query(default=None, max_length=255),
    national_id: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[PublicPatientResponse]:
    """List/find patients for the token's clinic.

    ``phone`` / ``email`` / ``national_id`` are format-tolerant exact
    matches (whitespace/dashes and case ignored) — the find leg of
    Zapier's search-or-create pattern (issue #65 §5). ``search`` stays
    the generic name/phone substring filter.
    """
    if phone or email or national_id:
        patients, total = await _find_patients(
            db,
            ctx.clinic_id,
            phone=phone,
            email=email,
            national_id=national_id,
            search=search,
            page=page,
            page_size=page_size,
        )
    else:
        patients, total = await PatientService.list_patients(
            db, ctx.clinic_id, search=search, page=page, page_size=page_size
        )
    response.headers.update(ctx.rate_headers)
    return PaginatedApiResponse(
        data=[PublicPatientResponse.model_validate(p) for p in patients],
        total=total,
        page=page,
        page_size=page_size,
    )


async def _find_patients(
    db: AsyncSession,
    clinic_id: UUID,
    *,
    phone: str | None,
    email: str | None,
    national_id: str | None,
    search: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Patient], int]:
    """Format-tolerant exact-match lookup (the structured find primitive)."""
    stmt = select(Patient).where(Patient.clinic_id == clinic_id)
    if phone:
        normalized = phone.replace(" ", "").replace("-", "")
        stmt = stmt.where(func.replace(func.replace(Patient.phone, " ", ""), "-", "") == normalized)
    if email:
        stmt = stmt.where(func.lower(Patient.email) == email.strip().lower())
    if national_id:
        stmt = stmt.where(func.upper(Patient.national_id) == national_id.strip().upper())
    if search:
        term = search.strip()
        stmt = stmt.where(
            or_(
                Patient.first_name.icontains(term, autoescape=True),
                Patient.last_name.icontains(term, autoescape=True),
            )
        )
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                stmt.order_by(Patient.created_at.desc(), Patient.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


@public_router.get("/patients/{patient_id}", response_model=ApiResponse[PublicPatientResponse])
async def get_public_patient(
    patient_id: UUID,
    response: Response,
    ctx: Annotated[PublicTokenContext, Depends(get_api_token_context)],
    _: Annotated[None, Depends(require_scope("patients:read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PublicPatientResponse]:
    patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    response.headers.update(ctx.rate_headers)
    return ApiResponse(data=PublicPatientResponse.model_validate(patient))
