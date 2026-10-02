"""Public budget endpoints (no staff auth, two-factor verification).

Implements the patient-facing flow described in
``docs/adr/0006-budget-public-link-2-factor-auth.md``:

1. ``GET    /api/v1/public/budgets/{token}/meta``      → returns
   the auth method the SPA should ask for (or ``none``), the
   ``locked``/``expired`` flags and the clinic name. No PII.
2. ``POST   /api/v1/public/budgets/{token}/verify``    → patient
   submits the verification value (phone last 4, DOB, or manual
   code). On success a signed cookie is set, scoped to the token.
3. ``GET    /api/v1/public/budgets/{token}``           → returns
   the budget detail (only with cookie or method=none). Marks the
   budget as viewed on the first call.
4. ``POST   /api/v1/public/budgets/{token}/accept``    → records
   acceptance + signature.
5. ``POST   /api/v1/public/budgets/{token}/reject``    → records
   rejection.

Rate limits via ``slowapi`` (``5/15minute`` per token, ``20/hour``
per IP, ``60/minute`` for ``/meta``). Sessions are HS256 JWTs
signed with ``settings.BUDGET_PUBLIC_SECRET_KEY`` (falls back to
``SECRET_KEY`` only in dev).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.router import limiter
from app.core.schemas import ApiResponse
from app.database import get_db

from .schemas import BudgetDetailResponse
from .service import BudgetService
from .workflow import (
    PUBLIC_AUTH_METHODS,
    PUBLIC_REJECTION_REASONS,
    PUBLIC_SESSION_TTL,
    BudgetWorkflowService,
    _hash_ip,
)

logger = logging.getLogger(__name__)

public_router = APIRouter()


# ---------------------------------------------------------------------------
# Cookie session helpers
# ---------------------------------------------------------------------------


def _public_secret() -> str:
    """Resolve the secret used to sign public budget session cookies.

    Production deploys must set ``BUDGET_PUBLIC_SECRET_KEY``. In
    development we fall back to ``SECRET_KEY`` so local runs work
    without extra setup, but this is logged once on startup.
    """
    return settings.BUDGET_PUBLIC_SECRET_KEY or settings.SECRET_KEY


def _cookie_name(token: UUID) -> str:
    """Cookie name is scoped per token so a stolen cookie from one
    budget cannot unlock another."""
    return f"bdg_session_{token}"


def _issue_session_cookie(response: Response, budget_id: UUID, token: UUID) -> None:
    """Set the per-token cookie. Path matches the module mount prefix
    (``/api/v1/budget/public/budgets/<token>``) so the browser sends
    it on the data-bearing endpoints. The legacy
    ``/api/v1/public/...`` path was wrong because the budget module
    is mounted with prefix ``/api/v1/budget`` (loader.py:181)."""
    expires_at = datetime.now(UTC) + PUBLIC_SESSION_TTL
    payload = {
        "sub": str(budget_id),
        "tok": str(token),
        "exp": int(expires_at.timestamp()),
    }
    encoded = jwt.encode(payload, _public_secret(), algorithm=settings.ALGORITHM)
    response.set_cookie(
        key=_cookie_name(token),
        value=encoded,
        max_age=int(PUBLIC_SESSION_TTL.total_seconds()),
        path=f"/api/v1/budget/public/budgets/{token}",
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
    )


def _verify_session_cookie(token: UUID, raw: str | None) -> UUID | None:
    if not raw:
        return None
    try:
        payload = jwt.decode(raw, _public_secret(), algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    if payload.get("tok") != str(token):
        return None
    sub = payload.get("sub")
    try:
        return UUID(sub) if sub else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Public schemas (no clinic_id, no PII beyond what the patient owns)
# ---------------------------------------------------------------------------


class PublicBudgetMeta(BaseModel):
    requires_verification: bool
    method: str
    locked: bool = False
    expired: bool = False
    already_decided: bool = False
    decided_status: str | None = None
    # Trust + personalization signals.
    clinic_name: str | None = None
    clinic_phone: str | None = None
    clinic_email: str | None = None
    clinic_address_line: str | None = None
    clinic_language: str | None = None
    clinic_currency: str | None = None
    patient_first_name: str | None = None
    budget_number: str | None = None
    budget_total: str | None = None
    valid_until: str | None = None


class PublicVerifyBody(BaseModel):
    method: str = Field(..., pattern="^(phone_last4|dob|manual_code|none)$")
    value: str = Field(..., min_length=1, max_length=64)


class PublicAcceptBody(BaseModel):
    signer_name: str = Field(..., min_length=1, max_length=200)
    signature_data: dict | None = Field(default=None)


class PublicRejectBody(BaseModel):
    reason: str = Field(...)
    note: str | None = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# /meta — first hit, no cookie required
# ---------------------------------------------------------------------------


@public_router.get(
    "/public/budgets/{token}/meta",
    response_model=ApiResponse[PublicBudgetMeta],
)
@limiter.limit("60/minute")
async def get_public_budget_meta(
    token: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PublicBudgetMeta]:
    budget = await BudgetService.get_by_public_token(db, token)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget link not found")

    locked = budget.public_locked_at is not None
    today = datetime.now(UTC).date()
    expired = budget.valid_until is not None and budget.valid_until < today
    already_decided = budget.status in {"accepted", "rejected"}

    # Resolve clinic + patient context via raw SQL. Both ``clinics`` and
    # ``patients`` live in modules already declared in budget.depends so
    # this is just a denormalised display read — kept as raw SQL to
    # avoid pulling the full ORM models for one row.
    from sqlalchemy import text as _text

    clinic_row = (
        await db.execute(
            _text(
                "SELECT name, phone, email, address, settings, currency FROM clinics WHERE id = :id"
            ),
            {"id": budget.clinic_id},
        )
    ).first()
    clinic_name = clinic_row.name if clinic_row else None
    clinic_phone = clinic_row.phone if clinic_row else None
    clinic_email = clinic_row.email if clinic_row else None
    clinic_currency = clinic_row.currency if clinic_row else None
    clinic_address_line: str | None = None
    clinic_language: str | None = None
    if clinic_row and clinic_row.address:
        addr = clinic_row.address or {}
        parts = [addr.get("street"), addr.get("city"), addr.get("postal_code")]
        clinic_address_line = ", ".join(p for p in parts if p) or None
    if clinic_row and clinic_row.settings:
        clinic_language = (clinic_row.settings or {}).get("communication_language")
    # Default to Spanish — matches the project's primary user base.
    clinic_language = clinic_language or "es"

    patient_row = (
        await db.execute(
            _text("SELECT first_name FROM patients WHERE id = :id AND clinic_id = :clinic_id"),
            {"id": budget.patient_id, "clinic_id": budget.clinic_id},
        )
    ).first()
    patient_first_name = patient_row.first_name if patient_row else None

    method = budget.public_auth_method
    requires_verification = method != "none" and not already_decided
    return ApiResponse(
        data=PublicBudgetMeta(
            requires_verification=requires_verification,
            method=method,
            locked=locked,
            expired=expired,
            already_decided=already_decided,
            decided_status=budget.status if already_decided else None,
            clinic_name=clinic_name,
            clinic_phone=clinic_phone,
            clinic_email=clinic_email,
            clinic_address_line=clinic_address_line,
            clinic_language=clinic_language,
            clinic_currency=clinic_currency,
            patient_first_name=patient_first_name,
            budget_number=budget.budget_number,
            budget_total=str(budget.total) if budget.total is not None else None,
            valid_until=budget.valid_until.isoformat() if budget.valid_until else None,
        )
    )


# ---------------------------------------------------------------------------
# /verify — exchange a knowledge factor for a session cookie
# ---------------------------------------------------------------------------


@public_router.post(
    "/public/budgets/{token}/verify",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("5/15minute", key_func=lambda request: str(request.path_params.get("token")))
@limiter.limit("20/hour")
async def verify_public_budget(
    token: UUID,
    body: PublicVerifyBody,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if body.method not in PUBLIC_AUTH_METHODS:
        raise HTTPException(status_code=400, detail="Invalid method")

    budget = await BudgetService.get_by_public_token(db, token)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget link not found")
    if budget.status in {"accepted", "rejected"}:
        raise HTTPException(
            status_code=409,
            detail="Budget already decided",
        )

    ip_hash = _hash_ip(request.client.host if request.client else None)
    ok, err = await BudgetWorkflowService.verify_public_access(
        db, budget, method=body.method, value=body.value, ip_hash=ip_hash
    )
    await db.commit()

    if not ok:
        if err == "locked":
            raise HTTPException(status_code=423, detail="locked")
        if err == "expired":
            raise HTTPException(status_code=410, detail="expired")
        if err == "rate_limited":
            raise HTTPException(status_code=429, detail="rate_limited")
        # method_mismatch / invalid both surface as 401 to the SPA.
        raise HTTPException(status_code=401, detail=err or "invalid")

    _issue_session_cookie(response, budget.id, token)


# ---------------------------------------------------------------------------
# Cookie-protected endpoints
# ---------------------------------------------------------------------------


async def _require_session(
    token: UUID,
    db: AsyncSession,
    cookie_value: str | None,
):
    """Resolve the budget for a public-cookie-protected route."""
    budget = await BudgetService.get_by_public_token(db, token)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget link not found")
    if budget.public_auth_method != "none":
        # method=none does not need a cookie; otherwise the cookie must
        # match the budget id and not be expired.
        sub = _verify_session_cookie(token, cookie_value)
        if sub is None or sub != budget.id:
            raise HTTPException(status_code=401, detail="verification_required")
    return budget


@public_router.get(
    "/public/budgets/{token}",
    response_model=ApiResponse[BudgetDetailResponse],
)
@limiter.limit("30/minute")
async def get_public_budget(
    token: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetDetailResponse]:
    cookie_value = request.cookies.get(_cookie_name(token))
    budget = await _require_session(token, db, cookie_value)

    today = datetime.now(UTC).date()
    if budget.valid_until is not None and budget.valid_until < today:
        raise HTTPException(status_code=410, detail="expired")

    ip_hash = _hash_ip(request.client.host if request.client else None)
    await BudgetWorkflowService.mark_viewed(db, budget, ip_hash=ip_hash)
    await db.commit()

    # Reload with items eagerly loaded for the response.
    budget = await BudgetService.get_budget(db, budget.clinic_id, budget.id, include_items=True)
    return ApiResponse(data=BudgetDetailResponse.model_validate(budget))


@public_router.post(
    "/public/budgets/{token}/accept",
    response_model=ApiResponse[PublicBudgetMeta],
)
@limiter.limit("10/minute")
async def accept_public_budget(
    token: UUID,
    body: PublicAcceptBody,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PublicBudgetMeta]:
    cookie_value = request.cookies.get(_cookie_name(token))
    budget = await _require_session(token, db, cookie_value)
    if budget.status in {"accepted", "rejected"}:
        raise HTTPException(status_code=409, detail="Budget already decided")

    sig_payload = {
        "signed_by_name": body.signer_name,
        "relationship_to_patient": "patient",
        "signature_method": "drawn" if body.signature_data else "click_accept",
        "signature_data": body.signature_data,
    }
    try:
        # Reload with items required by accept_budget validation.
        full_budget = await BudgetService.get_budget(
            db, budget.clinic_id, budget.id, include_items=True
        )
        await BudgetWorkflowService.accept_budget(
            db,
            full_budget,
            signature_data=sig_payload,
            accepted_by=full_budget.created_by,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            accepted_via="remote_link",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return ApiResponse(
        data=PublicBudgetMeta(
            requires_verification=False,
            method=budget.public_auth_method,
            already_decided=True,
            decided_status="accepted",
        )
    )


@public_router.get("/public/budgets/{token}/pdf/signed")
@limiter.limit("10/minute", key_func=lambda request: str(request.path_params.get("token")))
async def download_public_signed_budget_pdf(
    token: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Patient-facing download of the signed PDF.

    Same cookie + token scope as the rest of the public flow. 404
    when the budget has not been accepted yet. Audited via
    ``BudgetAccessLog`` (success=True so it never contributes to the
    lockout counter).
    """
    cookie_value = request.cookies.get(_cookie_name(token))
    budget = await _require_session(token, db, cookie_value)
    if budget.status != "accepted":
        raise HTTPException(status_code=404, detail="Budget has not been accepted")

    from sqlalchemy import select as _select

    from .models import BudgetAccessLog, BudgetSignature
    from .pdf import BudgetPDFService

    sig_q = (
        _select(BudgetSignature)
        .where(
            BudgetSignature.budget_id == budget.id,
            BudgetSignature.signature_type == "full_acceptance",
        )
        .order_by(BudgetSignature.signed_at.desc())
        .limit(1)
    )
    signature = (await db.execute(sig_q)).scalar_one_or_none()
    if signature is None:
        raise HTTPException(status_code=404, detail="Budget has not been signed")

    full_budget = await BudgetService.get_budget(
        db, budget.clinic_id, budget.id, include_items=True
    )

    from sqlalchemy import text as _text

    clinic_row = (
        await db.execute(
            _text(
                "SELECT id, name, address, phone, email, settings, tax_id, legal_name "
                "FROM clinics WHERE id = :id"
            ),
            {"id": budget.clinic_id},
        )
    ).first()
    clinic_settings = (
        clinic_row.settings if clinic_row and isinstance(clinic_row.settings, dict) else {}
    ) or {}
    locale = str(clinic_settings.get("communication_language") or "es")

    pdf_bytes = await BudgetPDFService.generate_pdf(
        full_budget,
        clinic_row,
        is_preview=False,
        locale=locale,
        signature=signature,
    )

    db.add(
        BudgetAccessLog(
            budget_id=budget.id,
            ip_hash=_hash_ip(request.client.host if request.client else None),
            success=True,
            method_attempted="download_signed_pdf",
        )
    )
    await db.commit()

    filename = f"presupuesto_{budget.budget_number}_v{budget.version}_firmado.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@public_router.post(
    "/public/budgets/{token}/reject",
    response_model=ApiResponse[PublicBudgetMeta],
)
@limiter.limit("10/minute")
async def reject_public_budget(
    token: UUID,
    body: PublicRejectBody,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PublicBudgetMeta]:
    cookie_value = request.cookies.get(_cookie_name(token))
    budget = await _require_session(token, db, cookie_value)
    if budget.status in {"accepted", "rejected"}:
        raise HTTPException(status_code=409, detail="Budget already decided")
    if body.reason not in PUBLIC_REJECTION_REASONS:
        raise HTTPException(status_code=400, detail="Invalid reason")

    try:
        full_budget = await BudgetService.get_budget(
            db, budget.clinic_id, budget.id, include_items=True
        )
        await BudgetWorkflowService.reject_budget(
            db,
            full_budget,
            rejected_by=full_budget.created_by,
            reason=body.reason,
            note=body.note,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return ApiResponse(
        data=PublicBudgetMeta(
            requires_verification=False,
            method=budget.public_auth_method,
            already_decided=True,
            decided_status="rejected",
        )
    )
