"""Public booking endpoints and authenticated reception actions.

Routes only parse input, apply the per-IP and per-contact abuse limits and
delegate to ``BookingService``; domain errors map to HTTP in ``BookingRoute``.
"""

import hashlib
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.router import limiter
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .captcha import challenge, consume
from .exceptions import BookingRoute
from .rate_limit import consume_rate
from .schemas import (
    AcceptInput,
    AcceptOut,
    Availability,
    BookingRequestOut,
    ConfirmInput,
    ConfirmOut,
    LogoInput,
    LogoState,
    MessageOut,
    PatientSuggestion,
    PublicConfig,
    RejectInput,
    RequestInput,
    SettingsInput,
    StatusOut,
)
from .service import PAGE_SIZE, BookingService

router = APIRouter(route_class=BookingRoute)
DB = Annotated[AsyncSession, Depends(get_db)]
CTX = Annotated[ClinicContext, Depends(get_clinic_context)]


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/settings", response_model=ApiResponse[SettingsInput])
async def get_settings(
    ctx: CTX, db: DB, _: Annotated[None, Depends(require_permission("online_booking.settings"))]
) -> ApiResponse[SettingsInput]:
    return ApiResponse(data=await BookingService.get_settings(db, ctx.clinic_id))


@router.put("/settings", response_model=ApiResponse[SettingsInput])
async def update_settings(
    data: SettingsInput,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.settings"))],
) -> ApiResponse[SettingsInput]:
    return ApiResponse(data=await BookingService.update_settings(db, ctx.clinic_id, data))


@router.get("/settings/logo")
async def settings_logo(
    ctx: CTX, db: DB, _: Annotated[None, Depends(require_permission("online_booking.settings"))]
) -> Response:
    return Response(
        await BookingService.settings_logo(db, ctx.clinic_id),
        media_type="image/png",
        headers={
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.put("/settings/logo", response_model=ApiResponse[LogoState])
async def upload_logo(
    data: LogoInput,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.settings"))],
) -> ApiResponse[LogoState]:
    await BookingService.upload_logo(db, ctx.clinic_id, data)
    return ApiResponse(data=LogoState(uploaded=True))


@router.delete("/settings/logo", response_model=ApiResponse[LogoState])
async def delete_logo(
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.settings"))],
) -> ApiResponse[LogoState]:
    await BookingService.delete_logo(db, ctx.clinic_id)
    return ApiResponse(data=LogoState(uploaded=False))


@router.get("/public/{clinic_id}/logo")
@limiter.limit("60/minute")
async def public_logo(request: Request, clinic_id: UUID, db: DB) -> Response:
    content = await BookingService.public_logo(db, clinic_id)
    etag = f'"{hashlib.sha256(content).hexdigest()}"'
    headers = {
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "public, max-age=0, must-revalidate",
        "ETag": etag,
    }
    validators = [value.strip() for value in request.headers.get("if-none-match", "").split(",")]
    if "*" in validators or etag in validators or f"W/{etag}" in validators:
        return Response(status_code=304, headers=headers)
    return Response(content, media_type="image/png", headers=headers)


@router.get("/public/{clinic_id}/config", response_model=ApiResponse[PublicConfig])
@limiter.limit("60/minute")
async def public_config(request: Request, clinic_id: UUID, db: DB) -> ApiResponse[PublicConfig]:
    await consume_rate("availability-ip", _client(request), 240)
    return ApiResponse(data=PublicConfig(**await BookingService.public_config(db, clinic_id)))


@router.get(
    "/public/{clinic_id}/availability",
    response_model=ApiResponse[Availability],
    response_model_exclude_none=True,
)
@limiter.limit("60/minute")
async def availability(
    request: Request,
    clinic_id: UUID,
    db: DB,
    day: date | None = None,
    from_day: date | None = None,
    days: int = Query(default=7, ge=1, le=31),
    reason: str | None = Query(default=None, max_length=30),
) -> ApiResponse[Availability]:
    await consume_rate("availability-ip", _client(request), 240)
    result = await BookingService.availability(db, clinic_id, day, from_day, days, reason)
    return ApiResponse(data=Availability(**result))


@router.get("/public/{clinic_id}/challenge")
@limiter.limit("30/minute")
async def public_challenge(request: Request, clinic_id: UUID, db: DB):
    await consume_rate("challenge-ip", _client(request), 240)
    await BookingService.public_settings(db, clinic_id)
    return JSONResponse(challenge(clinic_id), headers={"Cache-Control": "no-store"})


@router.post(
    "/public/{clinic_id}/requests", status_code=201, response_model=ApiResponse[MessageOut]
)
@limiter.limit("10/hour")
async def create_request(
    request: Request, clinic_id: UUID, data: RequestInput, db: DB
) -> ApiResponse[MessageOut]:
    await consume_rate("request-ip", _client(request), 10)
    if data.website:
        # Honeypot: answer like any other malformed request.
        raise HTTPException(400, "Unable to process request")
    await consume_rate("request-contact", f"{clinic_id}:{str(data.contact_email).lower()}", 3)
    await BookingService.public_settings(db, clinic_id)
    await consume(db, clinic_id, data.altcha)
    message = await BookingService.create_request(db, clinic_id, data)
    return ApiResponse(data=MessageOut(message=message))


@router.post("/public/{clinic_id}/confirm", response_model=ApiResponse[ConfirmOut])
@limiter.limit("10/minute")
async def confirm(
    request: Request, clinic_id: UUID, data: ConfirmInput, db: DB
) -> ApiResponse[ConfirmOut]:
    await consume_rate("confirm-ip", _client(request), 120)
    return ApiResponse(data=ConfirmOut(**await BookingService.confirm(db, clinic_id, data.token)))


@router.get("/requests/count", response_model=ApiResponse[int])
async def count_requests(
    ctx: CTX, db: DB, _: Annotated[None, Depends(require_permission("online_booking.read"))]
) -> ApiResponse[int]:
    return ApiResponse(data=await BookingService.count_confirmed(db, ctx.clinic_id))


@router.get("/requests", response_model=PaginatedApiResponse[BookingRequestOut])
async def list_requests(
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.read"))],
    page: int = Query(default=1, ge=1, le=100000),
) -> PaginatedApiResponse[BookingRequestOut]:
    items, total = await BookingService.list_requests(db, ctx.clinic_id, page)
    return PaginatedApiResponse(
        data=[BookingRequestOut(**item) for item in items],
        total=total,
        page=page,
        page_size=PAGE_SIZE,
    )


@router.get(
    "/requests/{request_id}/patient-suggestions",
    response_model=ApiResponse[list[PatientSuggestion]],
)
async def patient_suggestions(
    request_id: UUID,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.read"))],
    __: Annotated[None, Depends(require_permission("patients.read"))],
) -> ApiResponse[list[PatientSuggestion]]:
    patients = await BookingService.patient_suggestions(db, ctx.clinic_id, request_id)
    return ApiResponse(data=[PatientSuggestion.model_validate(p) for p in patients])


@router.post("/requests/{request_id}/accept", response_model=ApiResponse[AcceptOut])
async def accept(
    request_id: UUID,
    data: AcceptInput,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.write"))],
) -> ApiResponse[AcceptOut]:
    return ApiResponse(data=AcceptOut(**await BookingService.accept(db, ctx, request_id, data)))


@router.post("/requests/{request_id}/reject", response_model=ApiResponse[StatusOut])
async def reject(
    request_id: UUID,
    data: RejectInput,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.write"))],
) -> ApiResponse[StatusOut]:
    return ApiResponse(
        data=StatusOut(status=await BookingService.reject(db, ctx, request_id, data))
    )
