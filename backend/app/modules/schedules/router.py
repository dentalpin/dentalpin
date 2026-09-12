"""Schedules HTTP surface: clinic hours + professional hours + availability + analytics.

Mounted at ``/api/v1/schedules/``.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import (
    ClinicContext,
    get_clinic_context,
    require_permission,
)
from app.core.auth.rbac import has_permission_for
from app.core.schemas import ApiResponse
from app.database import get_db

from .models import (
    ClinicOverride,
    ClinicWeeklySchedule,
    ProfessionalOverride,
    ProfessionalWeeklySchedule,
)
from .schemas import (
    AvailabilityRange,
    AvailabilityResponse,
    ClinicHoursResponse,
    ClinicHoursUpdate,
    ClinicOverrideCreate,
    ClinicOverrideResponse,
    ClinicOverrideUpdate,
    OccupancyResponse,
    OccupancyRow,
    PeakHourRow,
    PeakHoursResponse,
    ProfessionalHoursResponse,
    ProfessionalHoursUpdate,
    ProfessionalOverrideCreate,
    ProfessionalOverrideResponse,
    ProfessionalOverrideUpdate,
    ShiftOut,
    UtilizationResponse,
    UtilizationRow,
    WeekdayShiftsOut,
)
from .services import (
    AnalyticsService,
    AvailabilityService,
    ClinicHoursService,
    ProfessionalHoursService,
)

router = APIRouter()


# --- helpers ----------------------------------------------------------


def _weekly_to_response(weekly: ClinicWeeklySchedule, timezone: str) -> ClinicHoursResponse:
    by_day: dict[int, list[ShiftOut]] = {d: [] for d in range(7)}
    for shift in weekly.shifts:
        if shift.weekday is None:
            continue
        by_day[shift.weekday].append(
            ShiftOut(id=shift.id, start_time=shift.start_time, end_time=shift.end_time)
        )
    for wd in by_day:
        by_day[wd].sort(key=lambda s: s.start_time)

    return ClinicHoursResponse(
        id=weekly.id,
        clinic_id=weekly.clinic_id,
        timezone=timezone,
        is_active=weekly.is_active,
        days=[WeekdayShiftsOut(weekday=wd, shifts=by_day[wd]) for wd in range(7)],
    )


def _professional_weekly_to_response(
    weekly: ProfessionalWeeklySchedule,
) -> ProfessionalHoursResponse:
    by_day: dict[int, list[ShiftOut]] = {d: [] for d in range(7)}
    for shift in weekly.shifts:
        if shift.weekday is None:
            continue
        by_day[shift.weekday].append(
            ShiftOut(id=shift.id, start_time=shift.start_time, end_time=shift.end_time)
        )
    for wd in by_day:
        by_day[wd].sort(key=lambda s: s.start_time)

    return ProfessionalHoursResponse(
        id=weekly.id,
        clinic_id=weekly.clinic_id,
        user_id=weekly.user_id,
        is_active=weekly.is_active,
        days=[WeekdayShiftsOut(weekday=wd, shifts=by_day[wd]) for wd in range(7)],
    )


def _override_to_response(
    override: ClinicOverride,
) -> ClinicOverrideResponse:
    shifts = [
        ShiftOut(id=s.id, start_time=s.start_time, end_time=s.end_time) for s in override.shifts
    ]
    shifts.sort(key=lambda s: s.start_time)
    return ClinicOverrideResponse(
        id=override.id,
        clinic_id=override.clinic_id,
        start_date=override.start_date,
        end_date=override.end_date,
        kind=override.kind,
        reason=override.reason,
        shifts=shifts,
    )


def _professional_override_to_response(
    override: ProfessionalOverride,
) -> ProfessionalOverrideResponse:
    shifts = [
        ShiftOut(id=s.id, start_time=s.start_time, end_time=s.end_time) for s in override.shifts
    ]
    shifts.sort(key=lambda s: s.start_time)
    return ProfessionalOverrideResponse(
        id=override.id,
        clinic_id=override.clinic_id,
        user_id=override.user_id,
        start_date=override.start_date,
        end_date=override.end_date,
        kind=override.kind,
        reason=override.reason,
        shifts=shifts,
    )


async def _require_professional_access(
    db: AsyncSession, ctx: ClinicContext, user_id: UUID, action: str
) -> None:
    """Raise 403 if the user lacks rights to read/write someone else's schedule."""
    perm_general = f"schedules.professional.{action}"
    perm_own = f"schedules.professional.own.{action}"
    if await has_permission_for(db, ctx.clinic_id, ctx.role, perm_general):
        return
    if await has_permission_for(db, ctx.clinic_id, ctx.role, perm_own) and user_id == ctx.user_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Permission denied: {perm_general}",
    )


# --- Clinic hours -----------------------------------------------------


@router.get("/clinic-hours", response_model=ApiResponse[ClinicHoursResponse])
async def get_clinic_hours(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("schedules.clinic_hours.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ClinicHoursResponse]:
    weekly = await ClinicHoursService.get_or_create_weekly(db, ctx.clinic_id)
    timezone = await ClinicHoursService.get_clinic_timezone(db, ctx.clinic_id)
    return ApiResponse(data=_weekly_to_response(weekly, timezone))


@router.put("/clinic-hours", response_model=ApiResponse[ClinicHoursResponse])
async def update_clinic_hours(
    payload: ClinicHoursUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("schedules.clinic_hours.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ClinicHoursResponse]:
    weekly = await ClinicHoursService.get_or_create_weekly(db, ctx.clinic_id)
    weekly = await ClinicHoursService.replace_weekly_shifts(
        db,
        weekly,
        [
            {
                "weekday": d.weekday,
                "shifts": [{"start_time": s.start_time, "end_time": s.end_time} for s in d.shifts],
            }
            for d in payload.days
        ],
    )
    timezone = await ClinicHoursService.get_clinic_timezone(db, ctx.clinic_id)
    return ApiResponse(data=_weekly_to_response(weekly, timezone))


@router.get(
    "/clinic-overrides",
    response_model=ApiResponse[list[ClinicOverrideResponse]],
)
async def list_clinic_overrides(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("schedules.clinic_hours.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    start: date | None = None,
    end: date | None = None,
) -> ApiResponse[list[ClinicOverrideResponse]]:
    overrides = await ClinicHoursService.list_overrides(db, ctx.clinic_id, start, end)
    return ApiResponse(data=[_override_to_response(o) for o in overrides])


@router.post(
    "/clinic-overrides",
    response_model=ApiResponse[ClinicOverrideResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_clinic_override(
    payload: ClinicOverrideCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("schedules.clinic_hours.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ClinicOverrideResponse]:
    override = await ClinicHoursService.create_override(
        db,
        ctx.clinic_id,
        {
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "kind": payload.kind,
            "reason": payload.reason,
            "shifts": [
                {"start_time": s.start_time, "end_time": s.end_time} for s in payload.shifts
            ],
        },
    )
    return ApiResponse(data=_override_to_response(override))


@router.put(
    "/clinic-overrides/{override_id}",
    response_model=ApiResponse[ClinicOverrideResponse],
)
async def update_clinic_override(
    override_id: UUID,
    payload: ClinicOverrideUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("schedules.clinic_hours.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ClinicOverrideResponse]:
    override = await ClinicHoursService.get_override(db, ctx.clinic_id, override_id)
    if override is None:
        raise HTTPException(status_code=404, detail="Override not found")
    override = await ClinicHoursService.update_override(
        db,
        override,
        {
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "kind": payload.kind,
            "reason": payload.reason,
            "shifts": [
                {"start_time": s.start_time, "end_time": s.end_time} for s in payload.shifts
            ],
        },
    )
    return ApiResponse(data=_override_to_response(override))


@router.delete(
    "/clinic-overrides/{override_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_clinic_override(
    override_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("schedules.clinic_hours.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    override = await ClinicHoursService.get_override(db, ctx.clinic_id, override_id)
    if override is None:
        raise HTTPException(status_code=404, detail="Override not found")
    await ClinicHoursService.delete_override(db, override)


# --- Professional hours -----------------------------------------------


@router.get(
    "/professionals/{user_id}/hours",
    response_model=ApiResponse[ProfessionalHoursResponse],
)
async def get_professional_hours(
    user_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ProfessionalHoursResponse]:
    await _require_professional_access(db, ctx, user_id, "read")
    if not await ProfessionalHoursService.is_professional(db, ctx.clinic_id, user_id):
        raise HTTPException(status_code=404, detail="Professional not found")
    weekly = await ProfessionalHoursService.get_or_create_weekly(db, ctx.clinic_id, user_id)
    return ApiResponse(data=_professional_weekly_to_response(weekly))


@router.put(
    "/professionals/{user_id}/hours",
    response_model=ApiResponse[ProfessionalHoursResponse],
)
async def update_professional_hours(
    user_id: UUID,
    payload: ProfessionalHoursUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ProfessionalHoursResponse]:
    await _require_professional_access(db, ctx, user_id, "write")
    if not await ProfessionalHoursService.is_professional(db, ctx.clinic_id, user_id):
        raise HTTPException(status_code=404, detail="Professional not found")
    weekly = await ProfessionalHoursService.get_or_create_weekly(db, ctx.clinic_id, user_id)
    weekly = await ProfessionalHoursService.replace_weekly_shifts(
        db,
        weekly,
        [
            {
                "weekday": d.weekday,
                "shifts": [{"start_time": s.start_time, "end_time": s.end_time} for s in d.shifts],
            }
            for d in payload.days
        ],
    )
    return ApiResponse(data=_professional_weekly_to_response(weekly))


@router.get(
    "/professionals/{user_id}/overrides",
    response_model=ApiResponse[list[ProfessionalOverrideResponse]],
)
async def list_professional_overrides(
    user_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    start: date | None = None,
    end: date | None = None,
) -> ApiResponse[list[ProfessionalOverrideResponse]]:
    await _require_professional_access(db, ctx, user_id, "read")
    if not await ProfessionalHoursService.is_professional(db, ctx.clinic_id, user_id):
        raise HTTPException(status_code=404, detail="Professional not found")
    overrides = await ProfessionalHoursService.list_overrides(
        db, ctx.clinic_id, user_id, start, end
    )
    return ApiResponse(data=[_professional_override_to_response(o) for o in overrides])


@router.post(
    "/professionals/{user_id}/overrides",
    response_model=ApiResponse[ProfessionalOverrideResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_professional_override(
    user_id: UUID,
    payload: ProfessionalOverrideCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ProfessionalOverrideResponse]:
    await _require_professional_access(db, ctx, user_id, "write")
    if not await ProfessionalHoursService.is_professional(db, ctx.clinic_id, user_id):
        raise HTTPException(status_code=404, detail="Professional not found")
    override = await ProfessionalHoursService.create_override(
        db,
        ctx.clinic_id,
        user_id,
        {
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "kind": payload.kind,
            "reason": payload.reason,
            "shifts": [
                {"start_time": s.start_time, "end_time": s.end_time} for s in payload.shifts
            ],
        },
    )
    return ApiResponse(data=_professional_override_to_response(override))


@router.put(
    "/professionals/{user_id}/overrides/{override_id}",
    response_model=ApiResponse[ProfessionalOverrideResponse],
)
async def update_professional_override(
    user_id: UUID,
    override_id: UUID,
    payload: ProfessionalOverrideUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ProfessionalOverrideResponse]:
    await _require_professional_access(db, ctx, user_id, "write")
    override = await ProfessionalHoursService.get_override(db, ctx.clinic_id, user_id, override_id)
    if override is None:
        raise HTTPException(status_code=404, detail="Override not found")
    override = await ProfessionalHoursService.update_override(
        db,
        override,
        {
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "kind": payload.kind,
            "reason": payload.reason,
            "shifts": [
                {"start_time": s.start_time, "end_time": s.end_time} for s in payload.shifts
            ],
        },
    )
    return ApiResponse(data=_professional_override_to_response(override))


@router.delete(
    "/professionals/{user_id}/overrides/{override_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_professional_override(
    user_id: UUID,
    override_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _require_professional_access(db, ctx, user_id, "write")
    override = await ProfessionalHoursService.get_override(db, ctx.clinic_id, user_id, override_id)
    if override is None:
        raise HTTPException(status_code=404, detail="Override not found")
    await ProfessionalHoursService.delete_override(db, override)


# --- Availability -----------------------------------------------------


@router.get("/availability", response_model=ApiResponse[AvailabilityResponse])
async def get_availability(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("schedules.availability.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    start: date = Query(...),
    end: date = Query(...),
    professional_id: UUID | None = Query(default=None),
) -> ApiResponse[AvailabilityResponse]:
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    timezone, ranges = await AvailabilityService.resolve(
        db, ctx.clinic_id, start, end, professional_id
    )
    return ApiResponse(
        data=AvailabilityResponse(
            timezone=timezone,
            ranges=[
                AvailabilityRange(
                    start=r.start,
                    end=r.end,
                    state=r.state,
                    professional_id=r.professional_id,
                    reason=r.reason,
                )
                for r in ranges
            ],
        )
    )


# --- Analytics --------------------------------------------------------


@router.get("/analytics/occupancy", response_model=ApiResponse[OccupancyResponse])
async def get_occupancy(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("schedules.analytics.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    start: date = Query(...),
    end: date = Query(...),
    cabinet_id: UUID | None = Query(default=None),
) -> ApiResponse[OccupancyResponse]:
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    rows = await AnalyticsService.occupancy(db, ctx.clinic_id, start, end, cabinet_id)
    return ApiResponse(
        data=OccupancyResponse(
            start=start,
            end=end,
            rows=[OccupancyRow(**row) for row in rows],
        )
    )


@router.get("/analytics/utilization", response_model=ApiResponse[UtilizationResponse])
async def get_utilization(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("schedules.analytics.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    start: date = Query(...),
    end: date = Query(...),
    professional_id: UUID | None = Query(default=None),
) -> ApiResponse[UtilizationResponse]:
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    rows = await AnalyticsService.utilization(db, ctx.clinic_id, start, end, professional_id)
    return ApiResponse(
        data=UtilizationResponse(
            start=start,
            end=end,
            rows=[UtilizationRow(**row) for row in rows],
        )
    )


@router.get("/analytics/peak-hours", response_model=ApiResponse[PeakHoursResponse])
async def get_peak_hours(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("schedules.analytics.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    start: date = Query(...),
    end: date = Query(...),
) -> ApiResponse[PeakHoursResponse]:
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    rows = await AnalyticsService.peak_hours(db, ctx.clinic_id, start, end)
    return ApiResponse(
        data=PeakHoursResponse(
            start=start,
            end=end,
            rows=[PeakHourRow(**row) for row in rows],
        )
    )
