"""Payments module FastAPI router.

Endpoints under ``/api/v1/payments/``. Reports are nested under
``/api/v1/payments/reports/*`` so the module owns both the operational
and analytic surfaces — consistent with the design that payment KPIs
should not be cross-joined against invoice data.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    AgingBuckets,
    AllocationResponse,
    BudgetIdsRequest,
    BudgetSummariesByIds,
    FilterIdsResponse,
    MethodBreakdown,
    PatientIdsRequest,
    PatientLedger,
    PatientSummariesByIds,
    PaymentCreate,
    PaymentReallocate,
    PaymentResponse,
    PaymentsSummary,
    PaymentsTrends,
    ProfessionalBreakdown,
    RazorpayOrderCreate,
    RazorpayOrderResponse,
    RazorpayVerifyCreate,
    RefundCreate,
    RefundResponse,
    RefundsReport,
)
from .razorpay_service import (
    RazorpayNotConfigured,
    create_order,
    verify_signature,
)
from .service import (
    LedgerService,
    PaymentReadService,
    PaymentReportsService,
    PaymentService,
)
from .workflow import (
    PaymentWorkflowError,
    reallocate_payment,
    record_payment,
    refund_payment,
)

router = APIRouter()


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# --- Payments ---------------------------------------------------------


@router.get("", response_model=PaginatedApiResponse[PaymentResponse])
async def list_payments(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    date_from: date | None = None,
    date_to: date | None = None,
    method: str | None = None,
    patient_id: UUID | None = None,
    has_refunds: bool | None = Query(default=None),
    has_unallocated: bool | None = Query(default=None),
    amount_min: Decimal | None = Query(default=None, ge=Decimal("0")),
    amount_max: Decimal | None = Query(default=None, ge=Decimal("0")),
    sort: str | None = Query(default=None, max_length=50),
) -> PaginatedApiResponse[PaymentResponse]:
    items, total = await PaymentService.list(
        db,
        ctx.clinic_id,
        date_from=date_from,
        date_to=date_to,
        method=method,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
        has_refunds=has_refunds,
        has_unallocated=has_unallocated,
        amount_min=amount_min,
        amount_max=amount_max,
        sort=sort,
    )
    return PaginatedApiResponse(
        data=[PaymentResponse.from_model(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ApiResponse[PaymentResponse], status_code=201)
async def create_payment(
    payload: PaymentCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PaymentResponse]:
    try:
        payment = await record_payment(
            db,
            clinic_id=ctx.clinic_id,
            currency=ctx.clinic.currency,
            patient_id=payload.patient_id,
            amount=payload.amount,
            method=payload.method,
            payment_date=payload.payment_date,
            recorded_by=ctx.user_id,
            allocations=[a.model_dump() for a in payload.allocations],
            reference=payload.reference,
            notes=payload.notes,
            idempotency_key=payload.idempotency_key,
        )
    except PaymentWorkflowError as exc:
        raise _bad_request(exc)

    fresh = await PaymentService.get(db, ctx.clinic_id, payment.id)
    if fresh is None:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Payment vanished after create")
    return ApiResponse(data=PaymentResponse.from_model(fresh))


# --- Razorpay ---------------------------------------------------------
#
# Online payment flow. The client opens Razorpay's checkout with the
# order created here; the browser callback then POSTs to -verify so the
# signature is checked server-side before a payment record is written.


@router.post(
    "/razorpay-order",
    response_model=ApiResponse[RazorpayOrderResponse],
    status_code=201,
)
async def razorpay_create_order(
    payload: RazorpayOrderCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.write"))],
) -> ApiResponse[RazorpayOrderResponse]:
    try:
        order = create_order(amount=float(payload.amount), currency=payload.currency)
    except RazorpayNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ApiResponse(
        data=RazorpayOrderResponse(
            order_id=order["order_id"],
            amount=order["amount"],
            currency=order["currency"],
            key_id=settings.RAZORPAY_KEY_ID,
        )
    )


@router.post("/razorpay-verify", response_model=ApiResponse[PaymentResponse], status_code=201)
async def razorpay_verify(
    payload: RazorpayVerifyCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PaymentResponse]:
    try:
        ok = verify_signature(
            payload.razorpay_payment_id,
            payload.razorpay_order_id,
            payload.razorpay_signature,
        )
    except RazorpayNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Invalid Razorpay signature — payment not recorded.",
        )
    try:
        payment = await record_payment(
            db,
            clinic_id=ctx.clinic_id,
            currency=ctx.clinic.currency,
            patient_id=payload.patient_id,
            amount=payload.amount,
            method="razorpay",
            payment_date=payload.payment_date,
            recorded_by=ctx.user_id,
            allocations=[a.model_dump() for a in payload.allocations],
            reference=payload.razorpay_payment_id,
            notes=f"Razorpay order: {payload.razorpay_order_id}",
        )
    except PaymentWorkflowError as exc:
        raise _bad_request(exc)

    fresh = await PaymentService.get(db, ctx.clinic_id, payment.id)
    if fresh is None:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Payment vanished after create")
    return ApiResponse(data=PaymentResponse.from_model(fresh))


@router.get("/{payment_id}", response_model=ApiResponse[PaymentResponse])
async def get_payment(
    payment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PaymentResponse]:
    payment = await PaymentService.get(db, ctx.clinic_id, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return ApiResponse(data=PaymentResponse.from_model(payment))


@router.post("/{payment_id}/reallocate", response_model=ApiResponse[PaymentResponse])
async def reallocate(
    payment_id: UUID,
    payload: PaymentReallocate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PaymentResponse]:
    payment = await PaymentService.get(db, ctx.clinic_id, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    try:
        await reallocate_payment(
            db,
            clinic_id=ctx.clinic_id,
            payment=payment,
            new_allocations=[a.model_dump() for a in payload.allocations],
            changed_by=ctx.user_id,
        )
    except PaymentWorkflowError as exc:
        raise _bad_request(exc)

    fresh = await PaymentService.get(db, ctx.clinic_id, payment_id)
    return ApiResponse(data=PaymentResponse.from_model(fresh))


# --- Refunds ----------------------------------------------------------


@router.get("/{payment_id}/refunds", response_model=ApiResponse[list[RefundResponse]])
async def list_refunds(
    payment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[RefundResponse]]:
    payment = await PaymentService.get(db, ctx.clinic_id, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return ApiResponse(data=[RefundResponse.model_validate(r) for r in payment.refunds])


@router.post("/{payment_id}/refunds", response_model=ApiResponse[RefundResponse], status_code=201)
async def create_refund(
    payment_id: UUID,
    payload: RefundCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.refund"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RefundResponse]:
    payment = await PaymentService.get(db, ctx.clinic_id, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    try:
        refund = await refund_payment(
            db,
            clinic_id=ctx.clinic_id,
            payment=payment,
            amount=payload.amount,
            method=payload.method,
            reason_code=payload.reason_code,
            reason_note=payload.reason_note,
            refunded_by=ctx.user_id,
        )
    except PaymentWorkflowError as exc:
        raise _bad_request(exc)
    return ApiResponse(data=RefundResponse.model_validate(refund))


# --- Ledger / per-budget ---------------------------------------------


@router.get("/patients/{patient_id}/ledger", response_model=ApiResponse[PatientLedger])
async def patient_ledger(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PatientLedger]:
    ledger = await LedgerService.get_patient_ledger(
        db, ctx.clinic_id, patient_id, currency=ctx.clinic.currency
    )
    return ApiResponse(data=ledger)


@router.get(
    "/patients/{patient_id}/pending-charges",
    response_model=ApiResponse[list[dict]],
)
async def patient_pending_charges(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[dict]]:
    """Earned entries not yet covered by net payments (FIFO virtual)."""
    pending = await LedgerService.compute_pending_charges(db, ctx.clinic_id, patient_id)
    return ApiResponse(data=pending)


@router.get(
    "/budgets/{budget_id}/allocations",
    response_model=ApiResponse[list[AllocationResponse]],
)
async def allocations_for_budget(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[AllocationResponse]]:
    rows = await PaymentReadService.get_allocations_for_budget(db, ctx.clinic_id, budget_id)
    return ApiResponse(data=[AllocationResponse.from_model(r) for r in rows])


# --- Cross-module summary + filter endpoints --------------------------
#
# Power the /budgets and /patients list pages (other modules) without
# forcing those modules to depend on payments. The contract lives in
# docs/technical/payments/cross-module-summaries.md.


@router.post(
    "/summary/by-budgets",
    response_model=ApiResponse[BudgetSummariesByIds],
)
async def summary_by_budgets(
    payload: BudgetIdsRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetSummariesByIds]:
    """Bulk per-budget collected/pending/payment_status.

    Cap 100 ids — sized for one page of a list. Off-books safe: never
    touches invoice totals.
    """
    summaries = await PaymentReadService.summaries_by_budgets(db, ctx.clinic_id, payload.budget_ids)
    return ApiResponse(data=BudgetSummariesByIds(summaries=summaries))


@router.post(
    "/summary/by-patients",
    response_model=ApiResponse[PatientSummariesByIds],
)
async def summary_by_patients(
    payload: PatientIdsRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PatientSummariesByIds]:
    """Bulk per-patient total_paid/debt/on_account_balance.

    Cap 100 ids. debt is computed strictly from earned − net_paid (off
    -books safe).
    """
    summaries = await PaymentReadService.summaries_by_patients(
        db, ctx.clinic_id, payload.patient_ids
    )
    return ApiResponse(data=PatientSummariesByIds(summaries=summaries))


@router.get(
    "/filters/budgets-by-status",
    response_model=ApiResponse[FilterIdsResponse],
)
async def filter_budgets_by_status(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: list[Literal["unpaid", "partial", "paid"]] = Query(..., min_length=1),
    patient_id: UUID | None = Query(default=None),
    assigned_professional_id: UUID | None = Query(default=None),
) -> ApiResponse[FilterIdsResponse]:
    """Return the clinic's budget ids whose payment status matches.

    Used by the /budgets page to intersect with its native list when
    the "Cobro" filter is active. Cap 1000 ids — frontend shows a
    toast when ``truncated=true``.
    """
    ids, truncated = await PaymentReadService.budget_ids_by_payment_status(
        db,
        ctx.clinic_id,
        list(status),
        patient_id=patient_id,
        assigned_professional_id=assigned_professional_id,
    )
    return ApiResponse(data=FilterIdsResponse(budget_ids=ids, truncated=truncated))


@router.get(
    "/filters/patients-with-debt",
    response_model=ApiResponse[FilterIdsResponse],
)
async def filter_patients_with_debt(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.record.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    min_debt: Decimal = Query(default=Decimal("0.01"), ge=Decimal("0")),
) -> ApiResponse[FilterIdsResponse]:
    """Return the clinic's patient ids with debt >= ``min_debt``.

    Used by the /patients page when the "Con deuda" filter is active.
    Cap 1000 ids. Off-books safe: debt = earned − net_paid.
    """
    ids, truncated = await PaymentReadService.patient_ids_with_debt(
        db, ctx.clinic_id, min_debt=min_debt
    )
    return ApiResponse(data=FilterIdsResponse(patient_ids=ids, truncated=truncated))


# --- Reports ----------------------------------------------------------


@router.get("/reports/summary", response_model=ApiResponse[PaymentsSummary])
async def reports_summary(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.reports.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(...),
    date_to: date = Query(...),
) -> ApiResponse[PaymentsSummary]:
    data = await PaymentReportsService.summary(
        db, ctx.clinic_id, ctx.clinic.currency, date_from, date_to
    )
    return ApiResponse(data=data)


@router.get("/reports/by-method", response_model=ApiResponse[list[MethodBreakdown]])
async def reports_by_method(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.reports.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(...),
    date_to: date = Query(...),
) -> ApiResponse[list[MethodBreakdown]]:
    data = await PaymentReportsService.by_method(db, ctx.clinic_id, date_from, date_to)
    return ApiResponse(data=data)


@router.get("/reports/by-professional", response_model=ApiResponse[list[ProfessionalBreakdown]])
async def reports_by_professional(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.reports.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(...),
    date_to: date = Query(...),
) -> ApiResponse[list[ProfessionalBreakdown]]:
    data = await PaymentReportsService.by_professional(db, ctx.clinic_id, date_from, date_to)
    return ApiResponse(data=data)


@router.get("/reports/aging-receivables", response_model=ApiResponse[AgingBuckets])
async def reports_aging(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.reports.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AgingBuckets]:
    data = await PaymentReportsService.aging_receivables(db, ctx.clinic_id, ctx.clinic.currency)
    return ApiResponse(data=data)


@router.get("/reports/refunds", response_model=ApiResponse[RefundsReport])
async def reports_refunds(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.reports.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(...),
    date_to: date = Query(...),
) -> ApiResponse[RefundsReport]:
    data = await PaymentReportsService.refunds_report(
        db, ctx.clinic_id, ctx.clinic.currency, date_from, date_to
    )
    return ApiResponse(data=data)


@router.get("/reports/trends", response_model=ApiResponse[PaymentsTrends])
async def reports_trends(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("payments.reports.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(...),
    date_to: date = Query(...),
    granularity: Literal["day", "week", "month", "year"] = "month",
) -> ApiResponse[PaymentsTrends]:
    data = await PaymentReportsService.trends(
        db, ctx.clinic_id, ctx.clinic.currency, date_from, date_to, granularity
    )
    return ApiResponse(data=data)
