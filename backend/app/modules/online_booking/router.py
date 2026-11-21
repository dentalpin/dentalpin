"""Public booking endpoints and authenticated reception actions.

Routes only parse input, apply the per-IP and per-contact abuse limits and
delegate to ``BookingService``; domain errors map to HTTP in ``BookingRoute``.
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.router import limiter
from app.database import get_db

from .exceptions import BookingRoute
from .rate_limit import consume_rate
from .schemas import AcceptInput, ConfirmInput, RejectInput, RequestInput, SettingsInput
from .service import PAGE_SIZE, BookingService

router = APIRouter(route_class=BookingRoute)
DB = Annotated[AsyncSession, Depends(get_db)]
CTX = Annotated[ClinicContext, Depends(get_clinic_context)]


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/settings")
async def get_settings(
    ctx: CTX, db: DB, _: Annotated[None, Depends(require_permission("online_booking.settings"))]
):
    settings = await BookingService.get_settings(db, ctx.clinic_id)
    return {"data": settings.model_dump(mode="json")}


@router.put("/settings")
async def update_settings(
    data: SettingsInput,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.settings"))],
):
    settings = await BookingService.update_settings(db, ctx.clinic_id, data)
    return {"data": settings.model_dump(mode="json")}


@router.get("/public/{clinic_id}/config")
@limiter.limit("60/minute")
async def public_config(request: Request, clinic_id: UUID, db: DB):
    await consume_rate("availability-ip", _client(request), 240)
    return {"data": await BookingService.public_config(db, clinic_id)}


@router.get("/public/{clinic_id}/availability")
@limiter.limit("60/minute")
async def availability(request: Request, clinic_id: UUID, day: date, db: DB):
    await consume_rate("availability-ip", _client(request), 240)
    return {"data": await BookingService.availability(db, clinic_id, day)}


@router.post("/public/{clinic_id}/requests", status_code=201)
@limiter.limit("10/hour")
async def create_request(request: Request, clinic_id: UUID, data: RequestInput, db: DB):
    await consume_rate("request-ip", _client(request), 10)
    if data.website:
        # Honeypot: answer like any other malformed request.
        raise HTTPException(400, "Unable to process request")
    await consume_rate("request-contact", f"{clinic_id}:{str(data.contact_email).lower()}", 3)
    message = await BookingService.create_request(db, clinic_id, data)
    return {"data": {"message": message}}


@router.post("/public/{clinic_id}/confirm")
@limiter.limit("10/minute")
async def confirm(request: Request, clinic_id: UUID, data: ConfirmInput, db: DB):
    await consume_rate("confirm-ip", _client(request), 120)
    return {"data": {"status": await BookingService.confirm(db, clinic_id, data.token)}}


@router.get("/requests/count")
async def count_requests(
    ctx: CTX, db: DB, _: Annotated[None, Depends(require_permission("online_booking.read"))]
):
    return {"data": await BookingService.count_confirmed(db, ctx.clinic_id)}


@router.get("/requests")
async def list_requests(
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.read"))],
    page: int = Query(default=1, ge=1, le=100000),
):
    items, total = await BookingService.list_requests(db, ctx.clinic_id, page)
    return {"data": items, "page": page, "has_more": page * PAGE_SIZE < total}


@router.get("/requests/{request_id}/patient-suggestions")
async def patient_suggestions(
    request_id: UUID,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.read"))],
    __: Annotated[None, Depends(require_permission("patients.read"))],
):
    patients = await BookingService.patient_suggestions(db, ctx.clinic_id, request_id)
    return {
        "data": [
            {
                "id": str(p.id),
                "first_name": p.first_name,
                "last_name": p.last_name,
                "phone": p.phone,
                "email": p.email,
                "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
            }
            for p in patients
        ]
    }


@router.post("/requests/{request_id}/accept")
async def accept(
    request_id: UUID,
    data: AcceptInput,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.write"))],
):
    result = await BookingService.accept(db, ctx, request_id, data)
    return {"data": {"status": result["status"], "appointment_id": str(result["appointment_id"])}}


@router.post("/requests/{request_id}/reject")
async def reject(
    request_id: UUID,
    data: RejectInput,
    ctx: CTX,
    db: DB,
    _: Annotated[None, Depends(require_permission("online_booking.write"))],
):
    return {"data": {"status": await BookingService.reject(db, ctx, request_id, data)}}
