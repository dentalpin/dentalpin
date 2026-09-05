"""Reports module router."""

import csv
import io
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from .schemas import (
    AgingBucket,
    AgingReport,
    AppointmentFunnel,
    BillingSummary,
    BudgetByProfessional,
    BudgetByStatus,
    BudgetByTreatment,
    BudgetSummary,
    CabinetUtilization,
    DayOfWeekStats,
    DurationVarianceStats,
    FirstVisitsSummary,
    HoursByProfessional,
    IssuedTrend,
    NumberingGap,
    OverdueInvoice,
    PaymentMethodSummary,
    ProfessionalBillingSummary,
    PunctualityStats,
    SchedulingSummary,
    TrendPoint,
    VatSummaryItem,
    WaitingTimeStats,
)
from .services import (
    AppointmentLifecycleService,
    BillingReportService,
    BudgetReportService,
    FinancialReportService,
    SchedulingReportService,
)

router = APIRouter(tags=["reports"])


# ============================================================================
# Billing Reports
# ============================================================================


@router.get("/billing/summary", response_model=ApiResponse[BillingSummary])
async def get_billing_summary(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
) -> ApiResponse[BillingSummary]:
    """Get billing summary for a period.

    Returns total invoiced, total paid, total pending, counts, and VAT breakdown.
    """
    data = await BillingReportService.get_summary(db, ctx.clinic_id, date_from, date_to)
    return ApiResponse(data=BillingSummary(**data))


@router.get("/billing/overdue", response_model=ApiResponse[list[OverdueInvoice]])
async def get_overdue_invoices(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=200, ge=1, le=1000),
) -> ApiResponse[list[OverdueInvoice]]:
    """Get list of overdue invoices, oldest due-date first.

    ``limit`` caps the result at 1000 so a clinic with years of unpaid
    balances doesn't return an unbounded set.
    """
    data = await BillingReportService.get_overdue_invoices(db, ctx.clinic_id, limit=limit)
    return ApiResponse(data=[OverdueInvoice(**item) for item in data])


@router.get("/billing/by-payment-method", response_model=ApiResponse[list[PaymentMethodSummary]])
async def get_by_payment_method(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
) -> ApiResponse[list[PaymentMethodSummary]]:
    """Get payment breakdown by method.

    Returns total amounts and counts grouped by payment method.
    """
    data = await BillingReportService.get_by_payment_method(db, ctx.clinic_id, date_from, date_to)
    return ApiResponse(data=[PaymentMethodSummary(**item) for item in data])


@router.get(
    "/billing/by-professional",
    response_model=ApiResponse[list[ProfessionalBillingSummary]],
)
async def get_by_professional(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
) -> ApiResponse[list[ProfessionalBillingSummary]]:
    """Get billing breakdown by professional (creator).

    Returns total amounts and invoice counts per professional.
    """
    data = await BillingReportService.get_by_professional(db, ctx.clinic_id, date_from, date_to)
    return ApiResponse(data=[ProfessionalBillingSummary(**item) for item in data])


@router.get("/billing/vat-summary", response_model=ApiResponse[list[VatSummaryItem]])
async def get_vat_summary(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
) -> ApiResponse[list[VatSummaryItem]]:
    """Get VAT summary for accounting.

    Returns base amounts, tax amounts, and totals grouped by VAT rate.
    """
    data = await BillingReportService.get_vat_summary(db, ctx.clinic_id, date_from, date_to)
    return ApiResponse(data=[VatSummaryItem(**item) for item in data])


@router.get("/billing/gaps", response_model=ApiResponse[list[NumberingGap]])
async def get_numbering_gaps(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[NumberingGap]]:
    """Find gaps in invoice numbering.

    Returns missing numbers by series and year.
    Useful for compliance audits.
    """
    data = await BillingReportService.get_numbering_gaps(db, ctx.clinic_id)
    return ApiResponse(data=[NumberingGap(**item) for item in data])


# ============================================================================
# Financial family (invoice axis only — off-books rule is structural)
# ============================================================================


def _csv_response(filename: str, header: list[str], rows: list[list]) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/billing/aging")
async def get_aging_buckets(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.financial.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: str = Query(default="json", pattern="^(json|csv)$"),
):
    """Outstanding invoice totals per age bucket (invoice axis only).

    Buckets are due-date anchored (0-30/31-60/61-90/90+); invoices with
    no due date count as current. Totals are issued amounts, never net
    of collected ones. Same shape the dashboard aging card renders.
    """
    buckets = await FinancialReportService.aging_buckets(db, ctx.clinic_id)
    if format == "csv":
        return _csv_response(
            "aging.csv",
            ["bucket", "total", "invoices", "patients"],
            [[b["label"], b["total"], b["count"], b["patient_count"]] for b in buckets],
        )
    return ApiResponse(
        data=AgingReport(
            currency=ctx.clinic.currency,
            buckets=[AgingBucket(**b) for b in buckets],
        )
    )


@router.get("/billing/issued-trend")
async def get_issued_trend(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.financial.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the trend window"),
    date_to: date = Query(..., description="End date for the trend window"),
    format: str = Query(default="json", pattern="^(json|csv)$"),
):
    """Issued invoice totals per month (invoice axis only).

    Drafts, cancelled, voided and soft-deleted invoices never count.
    """
    points = await FinancialReportService.issued_trend(db, ctx.clinic_id, date_from, date_to)
    if format == "csv":
        return _csv_response(
            "issued-trend.csv",
            ["month", "total", "invoices"],
            [[p["month"], p["total"], p["count"]] for p in points],
        )
    return ApiResponse(
        data=IssuedTrend(
            currency=ctx.clinic.currency,
            points=[TrendPoint(**p) for p in points],
        )
    )


# ============================================================================
# Budget Reports
# ============================================================================


@router.get("/budgets/summary", response_model=ApiResponse[BudgetSummary])
async def get_budget_summary(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.budgets.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
) -> ApiResponse[BudgetSummary]:
    """Get budget summary for a period.

    Returns totals, acceptance rate, and average value.
    """
    data = await BudgetReportService.get_summary(db, ctx.clinic_id, date_from, date_to)
    return ApiResponse(data=BudgetSummary(**data))


@router.get("/budgets/by-professional", response_model=ApiResponse[list[BudgetByProfessional]])
async def get_budgets_by_professional(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.budgets.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
) -> ApiResponse[list[BudgetByProfessional]]:
    """Get budget breakdown by professional."""
    data = await BudgetReportService.get_by_professional(db, ctx.clinic_id, date_from, date_to)
    return ApiResponse(data=[BudgetByProfessional(**item) for item in data])


@router.get("/budgets/by-treatment", response_model=ApiResponse[list[BudgetByTreatment]])
async def get_budgets_by_treatment(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.budgets.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
    limit: int = Query(default=10, ge=1, le=50, description="Number of top treatments"),
) -> ApiResponse[list[BudgetByTreatment]]:
    """Get most common treatments in budgets."""
    data = await BudgetReportService.get_by_treatment(db, ctx.clinic_id, date_from, date_to, limit)
    return ApiResponse(data=[BudgetByTreatment(**item) for item in data])


@router.get("/budgets/by-status", response_model=ApiResponse[list[BudgetByStatus]])
async def get_budgets_by_status(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.budgets.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
) -> ApiResponse[list[BudgetByStatus]]:
    """Get budget breakdown by status."""
    data = await BudgetReportService.get_by_status(db, ctx.clinic_id, date_from, date_to)
    return ApiResponse(data=[BudgetByStatus(**item) for item in data])


# ============================================================================
# Scheduling Reports
# ============================================================================


@router.get("/scheduling/summary", response_model=ApiResponse[SchedulingSummary])
async def get_scheduling_summary(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.scheduling.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
) -> ApiResponse[SchedulingSummary]:
    """Get scheduling summary for a period.

    Returns appointment counts by status and rates.
    """
    data = await SchedulingReportService.get_summary(db, ctx.clinic_id, date_from, date_to)
    return ApiResponse(data=SchedulingSummary(**data))


@router.get("/scheduling/first-visits", response_model=ApiResponse[FirstVisitsSummary])
async def get_first_visits(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.scheduling.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
) -> ApiResponse[FirstVisitsSummary]:
    """Get first visits (new patients) statistics."""
    data = await SchedulingReportService.get_first_visits(db, ctx.clinic_id, date_from, date_to)
    return ApiResponse(data=FirstVisitsSummary(**data))


@router.get("/scheduling/by-professional", response_model=ApiResponse[list[HoursByProfessional]])
async def get_hours_by_professional(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.scheduling.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
) -> ApiResponse[list[HoursByProfessional]]:
    """Get hours worked by professional."""
    data = await SchedulingReportService.get_hours_by_professional(
        db, ctx.clinic_id, date_from, date_to
    )
    return ApiResponse(data=[HoursByProfessional(**item) for item in data])


@router.get("/scheduling/by-cabinet", response_model=ApiResponse[list[CabinetUtilization]])
async def get_cabinet_utilization(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.scheduling.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
) -> ApiResponse[list[CabinetUtilization]]:
    """Get cabinet/chair utilization."""
    data = await SchedulingReportService.get_cabinet_utilization(
        db, ctx.clinic_id, date_from, date_to
    )
    return ApiResponse(data=[CabinetUtilization(**item) for item in data])


@router.get("/scheduling/by-day-of-week", response_model=ApiResponse[list[DayOfWeekStats]])
async def get_by_day_of_week(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.scheduling.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(..., description="Start date for the report period"),
    date_to: date = Query(..., description="End date for the report period"),
) -> ApiResponse[list[DayOfWeekStats]]:
    """Get appointment distribution by day of week."""
    data = await SchedulingReportService.get_by_day_of_week(db, ctx.clinic_id, date_from, date_to)
    return ApiResponse(data=[DayOfWeekStats(**item) for item in data])


# ---- Appointment lifecycle analytics (issue #49) -------------------------


@router.get(
    "/scheduling/waiting-times",
    response_model=ApiResponse[WaitingTimeStats],
)
async def get_waiting_times(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.scheduling.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(...),
    date_to: date = Query(...),
    cabinet_id: UUID | None = Query(default=None),
    professional_id: UUID | None = Query(default=None),
) -> ApiResponse[WaitingTimeStats]:
    """Average / median / p90 time from ``checked_in`` to ``in_treatment``."""
    try:
        data = await AppointmentLifecycleService.waiting_times(
            db,
            ctx.clinic_id,
            date_from,
            date_to,
            cabinet_id=cabinet_id,
            professional_id=professional_id,
        )
    except ValueError as e:
        from fastapi import HTTPException
        from fastapi import status as http_status

        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return ApiResponse(data=WaitingTimeStats(**data))


@router.get(
    "/scheduling/punctuality",
    response_model=ApiResponse[PunctualityStats],
)
async def get_punctuality(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.scheduling.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(...),
    date_to: date = Query(...),
    cabinet_id: UUID | None = Query(default=None),
    professional_id: UUID | None = Query(default=None),
) -> ApiResponse[PunctualityStats]:
    """Patient punctuality (check-in vs scheduled start time)."""
    try:
        data = await AppointmentLifecycleService.punctuality(
            db,
            ctx.clinic_id,
            date_from,
            date_to,
            cabinet_id=cabinet_id,
            professional_id=professional_id,
        )
    except ValueError as e:
        from fastapi import HTTPException
        from fastapi import status as http_status

        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return ApiResponse(data=PunctualityStats(**data))


@router.get(
    "/scheduling/duration-variance",
    response_model=ApiResponse[DurationVarianceStats],
)
async def get_duration_variance(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.scheduling.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(...),
    date_to: date = Query(...),
    cabinet_id: UUID | None = Query(default=None),
    professional_id: UUID | None = Query(default=None),
) -> ApiResponse[DurationVarianceStats]:
    """Planned vs actual treatment duration (in-treatment → completed)."""
    try:
        data = await AppointmentLifecycleService.duration_variance(
            db,
            ctx.clinic_id,
            date_from,
            date_to,
            cabinet_id=cabinet_id,
            professional_id=professional_id,
        )
    except ValueError as e:
        from fastapi import HTTPException
        from fastapi import status as http_status

        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return ApiResponse(data=DurationVarianceStats(**data))


@router.get(
    "/scheduling/funnel",
    response_model=ApiResponse[AppointmentFunnel],
)
async def get_appointment_funnel(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("reports.scheduling.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(...),
    date_to: date = Query(...),
    cabinet_id: UUID | None = Query(default=None),
    professional_id: UUID | None = Query(default=None),
) -> ApiResponse[AppointmentFunnel]:
    """Counts per status + completion / no-show / cancellation rates."""
    try:
        data = await AppointmentLifecycleService.funnel(
            db,
            ctx.clinic_id,
            date_from,
            date_to,
            cabinet_id=cabinet_id,
            professional_id=professional_id,
        )
    except ValueError as e:
        from fastapi import HTTPException
        from fastapi import status as http_status

        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return ApiResponse(data=AppointmentFunnel(**data))
