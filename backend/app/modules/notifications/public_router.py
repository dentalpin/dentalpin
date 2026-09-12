"""Public push-subscribe endpoints (no staff auth, token-bound).

Patient browser flow (T6): staff mints a single-use token
(``POST /api/v1/notifications/push/subscribe-tokens``); the patient
opens ``/p/push/<token>`` and the browser redeems it here with its
subscription. The random token (24 h, single use) is the auth — same
shape as budget public links (ADR 0006).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.router import limiter
from app.core.schemas import ApiResponse
from app.database import get_db

from .schemas import (
    PushPatientRedeem,
    PushSubscribed,
    PushSubscribeTokenValidate,
)

public_router = APIRouter(prefix="/public/push")


@public_router.get(
    "/subscribe/{token}",
    response_model=ApiResponse[PushSubscribeTokenValidate],
)
@limiter.limit("60/minute")
async def validate_push_subscribe_token(
    token: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PushSubscribeTokenValidate]:
    """Validate a subscribe token without consuming it (consent screen)."""
    from .channels.vapid import vapid_public_key
    from .push import PushSubscribeTokenService

    info = await PushSubscribeTokenService.validate(db, token)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired subscribe token"
        )
    public_key = vapid_public_key()
    if not public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebPush is not configured (DENTALPIN_VAPID_PRIVATE_KEY)",
        )
    return ApiResponse(
        data=PushSubscribeTokenValidate(
            valid=True,
            clinic_name=info["clinic_name"],
            expires_at=info["expires_at"],
            public_key=public_key,
        )
    )


@public_router.post(
    "/subscribe/{token}",
    response_model=ApiResponse[PushSubscribed],
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/15minute", key_func=lambda request: str(request.path_params.get("token")))
@limiter.limit("20/hour")
async def redeem_push_subscribe_token(
    token: UUID,
    data: PushPatientRedeem,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PushSubscribed]:
    """Redeem a subscribe token with a browser subscription (no auth).

    Returns ``{subscribed: true}`` only — no ids leak to the token
    holder. Single-use is enforced atomically in the UPDATE itself.
    """
    from .push import PushSubscribeTokenService

    try:
        await PushSubscribeTokenService.redeem(
            db, token, data.endpoint, data.keys.model_dump(), user_agent=data.user_agent
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired subscribe token"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ApiResponse(data=PushSubscribed(subscribed=True))
