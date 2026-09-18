"""Public intake endpoint — the clinic's website posts enquiries here.

No clinic context, no require_permission: the intake key *is* the auth
(same shape as notifications/public_router.py). Do not add
get_clinic_context "for consistency" — it would require a JWT the
website does not have.

Two rules this file must keep:

1. **The response never varies by branch** (D12). No different status,
   body, wording or obvious timing between "new lead", "recall queued"
   and "matched an opted-out patient" — otherwise the endpoint is an
   unauthenticated oracle for "is this phone one of your patients?".
2. **The plaintext key is never stored or logged.** Only its SHA-256 is
   used, including as the rate-limit bucket name.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.router import limiter
from app.core.schemas import ApiResponse
from app.database import get_db

from .schemas import LeadIntakeAck, LeadIntakeCreate
from .service import LeadIntakeKeyService, LeadIntakeService, LeadSettingsService

logger = logging.getLogger(__name__)

public_router = APIRouter(prefix="/public")

_ACK = ApiResponse(data=LeadIntakeAck(received=True))


def _key_rejected() -> HTTPException:
    """One generic 401, built fresh per raise.

    Missing, unknown and inactive keys are indistinguishable on purpose —
    the caller must not learn which case it hit.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid intake key",
    )


def _by_lead_key(request: Request) -> str:
    """Rate-limit bucket: sha256 of the presented key.

    Never the raw header — the secret must not sit in limiter state.
    """
    raw = request.headers.get("X-Lead-Key") or ""
    return hashlib.sha256(raw.encode()).hexdigest()


def _enforce_body_limit(request: Request) -> None:
    """Reject an oversized declared body with 413.

    FastAPI parses the JSON body before dependencies run, so this is a
    declared-size ceiling rather than a streaming read cap; combined with
    the max_length on every intake field it is the storage-abuse floor.
    """
    limit = max(1, settings.LEADS_INTAKE_MAX_BODY_KB) * 1024
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Request body exceeds {settings.LEADS_INTAKE_MAX_BODY_KB} KB",
        )


@public_router.post(
    "/intake",
    response_model=ApiResponse[LeadIntakeAck],
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute", key_func=_by_lead_key)
@limiter.limit("30/hour")
async def intake_lead(
    data: LeadIntakeCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_lead_key: Annotated[str | None, Header(alias="X-Lead-Key")] = None,
    _body_limit: Annotated[None, Depends(_enforce_body_limit)] = None,
) -> ApiResponse[LeadIntakeAck]:
    """Accept one enquiry from the clinic's website.

    Cheapest rejection first: honeypot, body size, key, daily cap. The
    outcome is discarded — a matched enquiry must not be distinguishable
    from a new one (D12).
    """
    # 1. Honeypot: a bot must see success, and nothing is written — not
    #    even a recall.
    if data.website.strip():
        logger.info("leads: honeypot triggered — enquiry discarded")
        return _ACK

    # 2. Key: the whole security model. One generic 401 for missing,
    #    unknown and inactive keys.
    if not x_lead_key:
        raise _key_rejected()
    clinic_id = await LeadIntakeKeyService.resolve_clinic_id(db, x_lead_key)
    if clinic_id is None:
        raise _key_rejected()

    # 3. Daily cap: one atomic statement, counted before the write so
    #    blocked attempts keep showing in the gauge.
    day_count, daily_cap = await LeadSettingsService.consume_daily_quota(db, clinic_id)
    if daily_cap and day_count > daily_cap:
        # Commit the counter *before* rejecting: get_db rolls the session
        # back when the handler raises, which would silently discard the
        # increment and make a flood look like it never happened. The
        # gauge is the clinic's only signal of how big the flood is.
        await db.commit()
        logger.warning(
            "leads: daily cap reached for clinic %s (%s/%s)", clinic_id, day_count, daily_cap
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily intake limit reached for this clinic",
            headers={"Retry-After": "3600"},
        )

    # 4. Route, discard the outcome, always the same answer.
    await LeadIntakeService.route(
        db,
        clinic_id,
        data.model_dump(),
        recommended_by=None,
    )
    return _ACK
