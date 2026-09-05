"""payroll HTTP surface — mounted at ``/api/v1/payroll/`` (admin only)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    AnnualReport,
    PayrollEntryCreate,
    PayrollEntryResponse,
    PayrollEntryUpdate,
    PayrollPeriodCreate,
    PayrollPeriodResponse,
    PayrollProfileCreate,
    PayrollProfileResponse,
    PayrollProfileUpdate,
    PeriodReport,
    PeriodTransition,
)
from .service import EntryService, PeriodService, ProfileService, ReportService, mask_profile

router = APIRouter()


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
@router.get("/profiles", response_model=PaginatedApiResponse[PayrollProfileResponse])
async def list_profiles(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[PayrollProfileResponse]:
    items, total = await ProfileService.list_profiles(db, ctx.clinic_id, page, page_size)
    return PaginatedApiResponse(
        data=[mask_profile(i) for i in items], total=total, page=page, page_size=page_size
    )


@router.post(
    "/profiles",
    response_model=ApiResponse[PayrollProfileResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    data: PayrollProfileCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollProfileResponse]:
    row = await ProfileService.create_profile(db, ctx.clinic_id, data)
    return ApiResponse(data=mask_profile(row))


@router.get("/profiles/{profile_id}", response_model=ApiResponse[PayrollProfileResponse])
async def get_profile(
    profile_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollProfileResponse]:
    row = await ProfileService.get_profile(db, ctx.clinic_id, profile_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ApiResponse(data=mask_profile(row))


@router.patch("/profiles/{profile_id}", response_model=ApiResponse[PayrollProfileResponse])
async def update_profile(
    profile_id: UUID,
    data: PayrollProfileUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollProfileResponse]:
    row = await ProfileService.get_profile(db, ctx.clinic_id, profile_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    row = await ProfileService.update_profile(db, row, data)
    return ApiResponse(data=mask_profile(row))


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------
@router.get("/periods", response_model=PaginatedApiResponse[PayrollPeriodResponse])
async def list_periods(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[PayrollPeriodResponse]:
    items, total = await PeriodService.list_periods(db, ctx.clinic_id, page, page_size)
    return PaginatedApiResponse(
        data=[PayrollPeriodResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/periods",
    response_model=ApiResponse[PayrollPeriodResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_period(
    data: PayrollPeriodCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollPeriodResponse]:
    row = await PeriodService.create_period(db, ctx.clinic_id, data)
    return ApiResponse(data=PayrollPeriodResponse.model_validate(row))


@router.get("/periods/{period_id}", response_model=ApiResponse[PayrollPeriodResponse])
async def get_period(
    period_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollPeriodResponse]:
    row = await PeriodService.get_period(db, ctx.clinic_id, period_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    return ApiResponse(data=PayrollPeriodResponse.model_validate(row))


@router.post("/periods/{period_id}/status", response_model=ApiResponse[PayrollPeriodResponse])
async def transition_period(
    period_id: UUID,
    data: PeriodTransition,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollPeriodResponse]:
    row = await PeriodService.get_period(db, ctx.clinic_id, period_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    row = await PeriodService.transition(db, row, data)
    return ApiResponse(data=PayrollPeriodResponse.model_validate(row))


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------
@router.get(
    "/periods/{period_id}/entries", response_model=PaginatedApiResponse[PayrollEntryResponse]
)
async def list_entries(
    period_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[PayrollEntryResponse]:
    items, total = await EntryService.list_entries(db, ctx.clinic_id, period_id, page, page_size)
    return PaginatedApiResponse(
        data=[PayrollEntryResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/entries",
    response_model=ApiResponse[PayrollEntryResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_entry(
    data: PayrollEntryCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollEntryResponse]:
    row = await EntryService.create_entry(db, ctx.clinic_id, data)
    return ApiResponse(data=PayrollEntryResponse.model_validate(row))


@router.get("/entries/{entry_id}", response_model=ApiResponse[PayrollEntryResponse])
async def get_entry(
    entry_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollEntryResponse]:
    row = await EntryService.get_entry(db, ctx.clinic_id, entry_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return ApiResponse(data=PayrollEntryResponse.model_validate(row))


@router.patch("/entries/{entry_id}", response_model=ApiResponse[PayrollEntryResponse])
async def update_entry(
    entry_id: UUID,
    data: PayrollEntryUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PayrollEntryResponse]:
    row = await EntryService.get_entry(db, ctx.clinic_id, entry_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    row = await EntryService.update_entry(db, row, data)
    return ApiResponse(data=PayrollEntryResponse.model_validate(row))


# ---------------------------------------------------------------------------
# Reports — aggregation only, no country logic
# ---------------------------------------------------------------------------
@router.get("/reports/monthly", response_model=ApiResponse[PeriodReport])
async def monthly_report(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.reports.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
) -> ApiResponse[PeriodReport]:
    data = await ReportService.monthly_report(db, ctx.clinic_id, month)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    return ApiResponse(data=PeriodReport(currency=ctx.clinic.currency, **data))


@router.get("/reports/annual", response_model=ApiResponse[AnnualReport])
async def annual_report(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payroll.reports.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: str = Query(pattern=r"^\d{4}$"),
) -> ApiResponse[AnnualReport]:
    data = await ReportService.annual_report(db, ctx.clinic_id, year)
    return ApiResponse(data=AnnualReport(currency=ctx.clinic.currency, **data))
