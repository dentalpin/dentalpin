"""Payroll HTTP surface.

Mounted under /api/v1/payroll/* by the module registry — no prefix on
this router. Collection routes use "" (no trailing slash) — CORRECTED
from the phase doc, which claimed "/" is used; the confirmed real
pattern (patients/router.py, and the working medications/router.py) is
"", not "/". Permissions: payroll.read / payroll.write.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    MonthlySummaryResponse,
    AnnualSummaryResponse,
    PayrollEntryCreate,
    PayrollEntryResponse,
    PayrollPeriodCreate,
    PayrollPeriodResponse,
    StaffPayrollProfileCreate,
    StaffPayrollProfileResponse,
    StaffPayrollProfileUpdate,
)
from .service import PayrollEntryService, PayrollPeriodService, PayrollReportService, StaffPayrollProfileService

router = APIRouter()


# --- Staff payroll profiles ------------------------------------------------


@router.get("/staff", response_model=PaginatedApiResponse[StaffPayrollProfileResponse])
async def list_staff_profiles(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaginatedApiResponse[StaffPayrollProfileResponse]:
    profiles = await StaffPayrollProfileService.list(db, ctx.clinic_id)
    data = [StaffPayrollProfileResponse.model_validate(p) for p in profiles]
    return PaginatedApiResponse(data=data, total=len(data), page=1, page_size=max(len(data), 1))


@router.post(
    "/staff",
    response_model=ApiResponse[StaffPayrollProfileResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_staff_profile(
    data: StaffPayrollProfileCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[StaffPayrollProfileResponse]:
    profile = await StaffPayrollProfileService.create(
        db, ctx.clinic_id, data.model_dump(exclude_unset=True)
    )
    return ApiResponse(data=StaffPayrollProfileResponse.model_validate(profile))


@router.put("/staff/{profile_id}", response_model=ApiResponse[StaffPayrollProfileResponse])
async def update_staff_profile(
    profile_id: UUID,
    data: StaffPayrollProfileUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[StaffPayrollProfileResponse]:
    profile = await StaffPayrollProfileService.get(db, ctx.clinic_id, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff payroll profile not found")
    profile = await StaffPayrollProfileService.update(db, profile, data.model_dump(exclude_unset=True))
    return ApiResponse(data=StaffPayrollProfileResponse.model_validate(profile))


# --- Payroll periods --------------------------------------------------------


@router.get("/periods", response_model=PaginatedApiResponse[PayrollPeriodResponse])
async def list_periods(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaginatedApiResponse[PayrollPeriodResponse]:
    periods = await PayrollPeriodService.list(db, ctx.clinic_id)
    data = [PayrollPeriodResponse.model_validate(p) for p in periods]
    return PaginatedApiResponse(data=data, total=len(data), page=1, page_size=max(len(data), 1))


@router.post(
    "/periods", response_model=ApiResponse[PayrollPeriodResponse], status_code=status.HTTP_201_CREATED
)
async def create_period(
    data: PayrollPeriodCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollPeriodResponse]:
    period = await PayrollPeriodService.create(db, ctx.clinic_id, data.month, data.year)
    return ApiResponse(data=PayrollPeriodResponse.model_validate(period))


@router.post("/periods/{period_id}/generate", response_model=ApiResponse[list[PayrollEntryResponse]])
async def generate_period_entries(
    period_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[PayrollEntryResponse]]:
    period = await PayrollPeriodService.get(db, ctx.clinic_id, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll period not found")
    entries = await PayrollPeriodService.generate_entries(db, ctx.clinic_id, period)
    return ApiResponse(data=[PayrollEntryResponse.model_validate(e) for e in entries])


@router.post("/periods/{period_id}/process", response_model=ApiResponse[PayrollPeriodResponse])
async def process_period(
    period_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollPeriodResponse]:
    period = await PayrollPeriodService.get(db, ctx.clinic_id, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll period not found")
    period = await PayrollPeriodService.mark_processed(db, period)

    # Event publishing: needs EventType.PAYROLL_PERIOD_PROCESSED added to
    # app/core/events/types.py (shared-file edit, see install guide) —
    # NOT done automatically here since that file's real content/naming
    # convention wasn't available to confirm against.
    from app.core.events import EventType, event_bus

    await event_bus.publish(
        EventType.PAYROLL_PERIOD_PROCESSED,
        {"period_id": str(period.id), "clinic_id": str(ctx.clinic_id)},
    )
    return ApiResponse(data=PayrollPeriodResponse.model_validate(period))


@router.post("/periods/{period_id}/mark-paid", response_model=ApiResponse[PayrollPeriodResponse])
async def mark_period_paid(
    period_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollPeriodResponse]:
    period = await PayrollPeriodService.get(db, ctx.clinic_id, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll period not found")
    period = await PayrollPeriodService.mark_paid(db, period)

    from app.core.events import EventType, event_bus

    await event_bus.publish(
        EventType.PAYROLL_PAYMENT_MADE,
        {"period_id": str(period.id), "clinic_id": str(ctx.clinic_id)},
    )
    return ApiResponse(data=PayrollPeriodResponse.model_validate(period))


@router.get("/periods/{period_id}/entries", response_model=ApiResponse[list[PayrollEntryResponse]])
async def list_period_entries(
    period_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[PayrollEntryResponse]]:
    entries = await PayrollEntryService.list_for_period(db, ctx.clinic_id, period_id)
    return ApiResponse(data=[PayrollEntryResponse.model_validate(e) for e in entries])


# --- Payroll entries -------------------------------------------------------


@router.put("/entries/{entry_id}", response_model=ApiResponse[PayrollEntryResponse])
async def update_entry(
    entry_id: UUID,
    data: PayrollEntryCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollEntryResponse]:
    entry = await PayrollEntryService.get(db, ctx.clinic_id, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll entry not found")
    entry = await PayrollEntryService.update(db, entry, data.model_dump(exclude_unset=True))
    return ApiResponse(data=PayrollEntryResponse.model_validate(entry))


@router.post("/entries/{entry_id}/mark-paid", response_model=ApiResponse[PayrollEntryResponse])
async def mark_entry_paid(
    entry_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollEntryResponse]:
    entry = await PayrollEntryService.get(db, ctx.clinic_id, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll entry not found")
    entry = await PayrollEntryService.mark_paid(db, entry)
    return ApiResponse(data=PayrollEntryResponse.model_validate(entry))


# --- Reports ----------------------------------------------------------------


@router.get("/reports/monthly", response_model=ApiResponse[MonthlySummaryResponse])
async def monthly_summary(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    month: int = Query(ge=1, le=12),
    year: int = Query(ge=2000, le=2100),
) -> ApiResponse[MonthlySummaryResponse]:
    summary = await PayrollReportService.monthly_summary(db, ctx.clinic_id, month, year)
    return ApiResponse(data=MonthlySummaryResponse(**summary))


@router.get("/reports/annual", response_model=ApiResponse[AnnualSummaryResponse])
async def annual_summary(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: int = Query(ge=2000, le=2100),
) -> ApiResponse[AnnualSummaryResponse]:
    summary = await PayrollReportService.annual_summary(db, ctx.clinic_id, year)
    return ApiResponse(data=AnnualSummaryResponse(**summary))
