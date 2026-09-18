"""HTTP surface for staff_attendance.

Mounted under ``/api/v1/staff_attendance/*``.
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from .schemas import (
    AttendanceEventResponse,
    AttendanceReportResponse,
    AttendanceReportRow,
    AttendanceStatusResponse,
    ClockRequest,
    MemberResponse,
)
from .service import AttendanceService

router = APIRouter()


@router.get("/members", response_model=ApiResponse[list[MemberResponse]])
async def list_members(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("staff_attendance.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[MemberResponse]]:
    members = await AttendanceService.list_members(db, ctx.clinic_id)
    return ApiResponse(data=[MemberResponse(**m) for m in members])


@router.post(
    "/events",
    response_model=ApiResponse[AttendanceEventResponse],
    status_code=status.HTTP_201_CREATED,
)
async def clock_event(
    data: ClockRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("staff_attendance.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AttendanceEventResponse]:
    row = await AttendanceService.clock(
        db,
        ctx.clinic_id,
        data.user_id,
        data.kind,
        at=data.at,
        note=data.note,
        created_by=ctx.user_id,
    )
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=AttendanceEventResponse.model_validate(row))


@router.get("/events", response_model=ApiResponse[list[AttendanceEventResponse]])
async def list_events(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("staff_attendance.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: UUID | None = None,
    day: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> ApiResponse[list[AttendanceEventResponse]]:
    rows = await AttendanceService.list_events(db, ctx.clinic_id, user_id, day, limit)
    return ApiResponse(data=[AttendanceEventResponse.model_validate(r) for r in rows])


@router.get("/status/{user_id}", response_model=ApiResponse[AttendanceStatusResponse])
async def get_status(
    user_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("staff_attendance.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AttendanceStatusResponse]:
    state, since = await AttendanceService.get_status(db, ctx.clinic_id, user_id)
    return ApiResponse(data=AttendanceStatusResponse(user_id=user_id, state=state, since=since))


@router.get("/report", response_model=ApiResponse[AttendanceReportResponse])
async def daily_report(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("staff_attendance.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    day: date = Query(...),
) -> ApiResponse[AttendanceReportResponse]:
    rows = await AttendanceService.daily_report(db, ctx.clinic_id, day)
    return ApiResponse(
        data=AttendanceReportResponse(
            date=day.isoformat(),
            rows=[AttendanceReportRow(**r) for r in rows],
        )
    )
