"""Budget module API router."""

from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.events import event_bus
from app.core.events.types import EventType
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .pdf import BudgetPDFService
from .schemas import (
    BudgetAcceptRequest,
    BudgetCancelRequest,
    BudgetCreate,
    BudgetDetailResponse,
    BudgetHistoryResponse,
    BudgetItemCreate,
    BudgetItemResponse,
    BudgetItemUpdate,
    BudgetListResponse,
    BudgetRejectRequest,
    BudgetResponse,
    BudgetSendRequest,
    BudgetUpdate,
    BudgetVersionListResponse,
    BudgetVersionResponse,
    SignatureMetaResponse,
    TreatmentPlanBrief,
)
from .service import BudgetHistoryService, BudgetItemService, BudgetService
from .workflow import BudgetWorkflowError, BudgetWorkflowService

router = APIRouter()


# ============================================================================
# Budget CRUD Endpoints
# ============================================================================


@router.get("/budgets", response_model=PaginatedApiResponse[BudgetListResponse])
async def list_budgets(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    patient_id: UUID | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    created_by: UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    expired: bool | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    budget_ids: list[UUID] | None = Query(default=None),
    assigned_professional_id: UUID | None = Query(default=None),
    valid_until_before: date | None = Query(default=None),
    valid_until_after: date | None = Query(default=None),
    sort: str | None = Query(default=None, max_length=50),
) -> PaginatedApiResponse[BudgetListResponse]:
    """List budgets with filtering and pagination.

    ``budget_ids`` is the intersection vector for cross-module filters
    such as "payment status = unpaid" — resolved server-side by the
    payments module then passed in here.
    """
    budgets, total = await BudgetService.list_budgets(
        db,
        ctx.clinic_id,
        page=page,
        page_size=page_size,
        patient_id=patient_id,
        status=status,
        created_by=created_by,
        date_from=date_from,
        date_to=date_to,
        expired=expired,
        search=search,
        budget_ids=budget_ids,
        assigned_professional_id=assigned_professional_id,
        valid_until_before=valid_until_before,
        valid_until_after=valid_until_after,
        sort=sort,
    )
    return PaginatedApiResponse(
        data=[BudgetListResponse.model_validate(b) for b in budgets],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/budgets/{budget_id}", response_model=ApiResponse[BudgetDetailResponse])
async def get_budget(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetDetailResponse]:
    """Get a budget by ID with full details."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    # Reverse lookup of the linked treatment plan via raw SQL — the
    # treatment_plans table is owned by the treatment_plan module and
    # we deliberately avoid importing its ORM model from here (ADR 0003).
    # plan_number_snapshot / plan_status_snapshot on Budget already
    # cover the common card/list use cases; this fetch is only for the
    # detail endpoint where we expose the live plan id + title.
    from sqlalchemy import text

    plan_row = (
        await db.execute(
            text(
                "SELECT id, plan_number, title, status "
                "FROM treatment_plans "
                "WHERE budget_id = :budget_id "
                "  AND clinic_id = :clinic_id "
                "  AND deleted_at IS NULL "
                "LIMIT 1"
            ),
            {"budget_id": budget_id, "clinic_id": ctx.clinic_id},
        )
    ).first()

    response_data = BudgetDetailResponse.model_validate(budget)
    if plan_row:
        response_data.treatment_plan = TreatmentPlanBrief(
            id=plan_row.id,
            plan_number=plan_row.plan_number,
            title=plan_row.title,
            status=plan_row.status,
        )

    return ApiResponse(data=response_data)


@router.post(
    "/budgets",
    response_model=ApiResponse[BudgetDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_budget(
    data: BudgetCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetDetailResponse]:
    """Create a new budget."""
    # Verify patient exists
    from app.modules.patients.models import Patient

    patient = await db.get(Patient, data.patient_id)
    if not patient or patient.clinic_id != ctx.clinic_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient not found",
        )

    budget = await BudgetService.create_budget(db, ctx.clinic_id, ctx.user_id, data.model_dump())

    # Reload with relationships
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget.id, include_items=True)
    return ApiResponse(data=BudgetDetailResponse.model_validate(budget))


@router.put("/budgets/{budget_id}", response_model=ApiResponse[BudgetDetailResponse])
async def update_budget(
    budget_id: UUID,
    data: BudgetUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetDetailResponse]:
    """Update a budget (only allowed in draft status)."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    try:
        budget = await BudgetService.update_budget(
            db, budget, data.model_dump(exclude_unset=True), ctx.user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Reload with relationships
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget.id, include_items=True)
    return ApiResponse(data=BudgetDetailResponse.model_validate(budget))


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete a budget."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=False)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    await BudgetService.delete_budget(db, budget, ctx.user_id)


# ============================================================================
# Budget Items Endpoints
# ============================================================================


@router.post(
    "/budgets/{budget_id}/items",
    response_model=ApiResponse[BudgetItemResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_budget_item(
    budget_id: UUID,
    data: BudgetItemCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetItemResponse]:
    """Add an item to a budget."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    try:
        item = await BudgetService.add_item(db, budget, data.model_dump(), ctx.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ApiResponse(data=BudgetItemResponse.model_validate(item))


@router.put(
    "/budgets/{budget_id}/items/{item_id}",
    response_model=ApiResponse[BudgetItemResponse],
)
async def update_budget_item(
    budget_id: UUID,
    item_id: UUID,
    data: BudgetItemUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetItemResponse]:
    """Update a budget item."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    if budget.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Items can only be updated in draft budgets",
        )

    # Find item
    item = next((i for i in budget.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Budget item not found")

    item = await BudgetItemService.update_item(db, item, data.model_dump(exclude_unset=True))

    # Recalculate budget totals
    await BudgetService._recalculate_totals(db, budget)

    return ApiResponse(data=BudgetItemResponse.model_validate(item))


@router.delete(
    "/budgets/{budget_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_budget_item(
    budget_id: UUID,
    item_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Remove an item from a budget."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    # Find item
    item = next((i for i in budget.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Budget item not found")

    try:
        await BudgetService.remove_item(db, budget, item, ctx.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# Workflow Endpoints
# ============================================================================


@router.post("/budgets/{budget_id}/send", response_model=ApiResponse[BudgetResponse])
async def send_budget(
    budget_id: UUID,
    data: BudgetSendRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetResponse]:
    """Mark budget as sent to patient.

    Can be sent via email or marked as manually delivered (printed/handed).
    Email sending is handled by the notifications module via the budget.sent event.
    """
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    try:
        # Determine send method
        send_method = "email" if data.send_email else "manual"
        recipient_email = None

        if data.send_email:
            # Get patient email for sending
            from app.modules.patients.models import Patient

            patient = await db.get(Patient, budget.patient_id)
            if not patient or not patient.email:
                raise BudgetWorkflowError("Patient has no email address")
            recipient_email = patient.email

        # This will publish the budget.sent event, which the notifications
        # module will handle (sending email if send_method="email" and
        # the clinic has budget_sent notifications enabled)
        budget = await BudgetWorkflowService.send_budget(
            db,
            budget,
            ctx.user_id,
            send_method=send_method,
            recipient_email=recipient_email,
            custom_message=data.custom_message,
        )

    except BudgetWorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ApiResponse(data=BudgetResponse.model_validate(budget))


@router.post("/budgets/{budget_id}/accept", response_model=ApiResponse[BudgetResponse])
async def accept_budget(
    budget_id: UUID,
    data: BudgetAcceptRequest,
    request: Request,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetResponse]:
    """Accept entire budget with signature.

    All items in the budget are accepted together. Partial acceptance is not supported.
    """
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    # Get client info for audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        budget = await BudgetWorkflowService.accept_budget(
            db,
            budget,
            data.signature.model_dump(),
            ctx.user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except BudgetWorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ApiResponse(data=BudgetResponse.model_validate(budget))


@router.post("/budgets/{budget_id}/reject", response_model=ApiResponse[BudgetResponse])
async def reject_budget(
    budget_id: UUID,
    data: BudgetRejectRequest,
    request: Request,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetResponse]:
    """Reject a budget."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    # Get client info for audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    signature_data = data.signature.model_dump() if data.signature else None

    try:
        budget = await BudgetWorkflowService.reject_budget(
            db,
            budget,
            ctx.user_id,
            data.reason,
            signature_data=signature_data,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except BudgetWorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ApiResponse(data=BudgetResponse.model_validate(budget))


@router.post("/budgets/{budget_id}/cancel", response_model=ApiResponse[BudgetResponse])
async def cancel_budget(
    budget_id: UUID,
    data: BudgetCancelRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetResponse]:
    """Cancel a budget."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    try:
        budget = await BudgetWorkflowService.cancel_budget(db, budget, ctx.user_id, data.reason)
    except BudgetWorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ApiResponse(data=BudgetResponse.model_validate(budget))


# ============================================================================
# Workflow extensions: renegotiate, accept-in-clinic, resend, set-public-code
# ============================================================================


from pydantic import BaseModel, Field  # noqa: E402


class _RenegotiateNoBody(BaseModel):
    """Empty body for /renegotiate (kept for OpenAPI clarity)."""


class _AcceptInClinicBody(BaseModel):
    signer_name: str = Field(..., min_length=1, max_length=200)
    signature_data: dict | None = Field(default=None)


class _SetPublicCodeBody(BaseModel):
    code: str = Field(..., min_length=4, max_length=6, pattern="^[0-9]+$")


class _SendReminderBody(BaseModel):
    milestone_days: int = Field(default=0, ge=0, le=365)


@router.post("/budgets/{budget_id}/renegotiate", response_model=ApiResponse[BudgetResponse])
async def renegotiate_budget(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.renegotiate"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetResponse]:
    """Cancel a sent budget so reception can edit the plan and reissue.

    Publishes ``budget.renegotiated`` so the linked treatment_plan
    handler reopens the companion plan back to ``draft``.
    """
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    try:
        budget = await BudgetWorkflowService.cancel_for_renegotiation(db, budget, ctx.user_id)
    except BudgetWorkflowError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ApiResponse(data=BudgetResponse.model_validate(budget))


@router.post(
    "/budgets/{budget_id}/accept-in-clinic",
    response_model=ApiResponse[BudgetResponse],
)
async def accept_budget_in_clinic(
    budget_id: UUID,
    body: _AcceptInClinicBody,
    request: Request,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.accept_in_clinic"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetResponse]:
    """Reception captures patient acceptance with optional tablet signature."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    sig_payload = {
        "signed_by_name": body.signer_name,
        "relationship_to_patient": "patient",
        "signature_method": "drawn" if body.signature_data else "click_accept",
        "signature_data": body.signature_data,
    }
    try:
        budget = await BudgetWorkflowService.accept_budget(
            db,
            budget,
            signature_data=sig_payload,
            accepted_by=ctx.user_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            accepted_via="in_clinic",
        )
    except BudgetWorkflowError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ApiResponse(data=BudgetResponse.model_validate(budget))


@router.post("/budgets/{budget_id}/resend", response_model=ApiResponse[BudgetResponse])
async def resend_budget(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetResponse]:
    """Clone a finished (rejected/expired/cancelled) budget to a
    fresh draft (version+1) with a brand-new public token. Reception
    can then edit and send the new draft. The linked plan's
    ``budget_id`` follows the new version via ``budget.superseded``."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if budget.status not in ("rejected", "expired", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail="Only rejected, expired or cancelled budgets can be resent",
        )
    new_budget = await BudgetWorkflowService.clone_to_new_draft(db, budget, ctx.user_id)
    plan_ref = await BudgetWorkflowService._lookup_plan(db, budget.id)
    response = ApiResponse(data=BudgetResponse.model_validate(new_budget))

    # Sole deviation from the publish-before-commit pattern: the
    # treatment_plan handler must point an FK at the new budget row from
    # its own session. Published pre-commit, that row is invisible → FK
    # violation the bus would swallow → relink silently lost. Commit
    # first (get_db's trailing commit becomes a no-op), then publish.
    await db.commit()
    if plan_ref is not None:
        await event_bus.publish(
            EventType.BUDGET_SUPERSEDED,
            {
                "clinic_id": str(budget.clinic_id),
                "budget_id": str(budget.id),
                "new_budget_id": str(new_budget.id),
                "patient_id": str(budget.patient_id),
                "plan_id": str(plan_ref.id),
                "version": new_budget.version,
                "resent_by": str(ctx.user_id),
                "occurred_at": datetime.now(UTC).isoformat(),
            },
        )
    return response


@router.post(
    "/budgets/{budget_id}/send-reminder",
    response_model=ApiResponse[BudgetResponse],
)
async def send_budget_reminder(
    budget_id: UUID,
    body: _SendReminderBody,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetResponse]:
    """Manual reminder dispatch — reception can prod the patient
    outside the cron schedule."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if budget.status != "sent":
        raise HTTPException(status_code=400, detail="Reminders only apply to sent budgets")
    budget = await BudgetWorkflowService.send_reminder(
        db, budget, milestone_days=body.milestone_days
    )
    return ApiResponse(data=BudgetResponse.model_validate(budget))


@router.post(
    "/budgets/{budget_id}/set-public-code",
    response_model=ApiResponse[BudgetResponse],
)
async def set_public_code(
    budget_id: UUID,
    body: _SetPublicCodeBody,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetResponse]:
    """Configure the manual code for a public link when the patient
    has neither phone nor DOB on file. The code is hashed; reception
    is expected to share it verbally with the patient."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    try:
        budget = await BudgetWorkflowService.set_public_code(db, budget, body.code)
    except BudgetWorkflowError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ApiResponse(data=BudgetResponse.model_validate(budget))


@router.post(
    "/budgets/{budget_id}/unlock-public",
    response_model=ApiResponse[BudgetResponse],
)
async def unlock_public_link(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetResponse]:
    """Clear the lockout on the public link so the patient can retry."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    budget = await BudgetWorkflowService.unlock_public(db, budget)
    return ApiResponse(data=BudgetResponse.model_validate(budget))


# ============================================================================
# Existing duplicate (kept for legacy paths) and the rest follow.
# ============================================================================


@router.post(
    "/budgets/{budget_id}/duplicate",
    response_model=ApiResponse[BudgetDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_budget(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetDetailResponse]:
    """Create a new version of a budget."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    new_budget = await BudgetService.duplicate_budget(db, budget, ctx.user_id)

    # Reload with relationships
    new_budget = await BudgetService.get_budget(
        db, ctx.clinic_id, new_budget.id, include_items=True
    )
    return ApiResponse(data=BudgetDetailResponse.model_validate(new_budget))


# ============================================================================
# Versions and History Endpoints
# ============================================================================


@router.get(
    "/budgets/{budget_id}/versions",
    response_model=ApiResponse[BudgetVersionListResponse],
)
async def get_budget_versions(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BudgetVersionListResponse]:
    """Get all versions of a budget."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=False)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    versions = await BudgetService.get_versions(db, ctx.clinic_id, budget.budget_number)

    version_responses = [
        BudgetVersionResponse(
            id=v.id,
            version=v.version,
            status=v.status,
            total=v.total,
            created_at=v.created_at,
            is_current=(v.id == budget_id),
        )
        for v in versions
    ]

    return ApiResponse(
        data=BudgetVersionListResponse(
            budget_number=budget.budget_number,
            versions=version_responses,
            current_version=budget.version,
        )
    )


@router.get(
    "/budgets/{budget_id}/history",
    response_model=ApiResponse[list[BudgetHistoryResponse]],
)
async def get_budget_history(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[BudgetHistoryResponse]]:
    """Get history/audit log for a budget."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=False)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    history = await BudgetHistoryService.get_history(db, ctx.clinic_id, budget_id)

    return ApiResponse(data=[BudgetHistoryResponse.model_validate(h) for h in history])


# ============================================================================
# PDF Endpoints
# ============================================================================


@router.get("/budgets/{budget_id}/pdf")
async def download_budget_pdf(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    locale: str = Query(default="es", pattern="^(es|en)$"),
) -> Response:
    """Download budget as PDF."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    # Get clinic for branding
    from app.core.auth.models import Clinic

    clinic = await db.get(Clinic, ctx.clinic_id)

    pdf_bytes = await BudgetPDFService.generate_pdf(
        budget,
        clinic,
        is_preview=False,
        locale=locale,
    )

    filename = f"presupuesto_{budget.budget_number}_v{budget.version}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/budgets/{budget_id}/pdf/signed")
async def download_signed_budget_pdf(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    locale: str = Query(default="es", pattern="^(es|en)$"),
) -> Response:
    """Download the signed PDF for an accepted budget.

    Returns 404 when no signature exists yet. Renders the same
    template as the unsigned PDF but with the signature image and
    audit metadata burned in.
    """
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    from .models import BudgetSignature

    sig_q = (
        select(BudgetSignature)
        .where(
            BudgetSignature.budget_id == budget_id,
            BudgetSignature.clinic_id == ctx.clinic_id,
            BudgetSignature.signature_type == "full_acceptance",
        )
        .order_by(BudgetSignature.signed_at.desc())
        .limit(1)
    )
    signature = (await db.execute(sig_q)).scalar_one_or_none()
    if signature is None:
        raise HTTPException(status_code=404, detail="Budget has not been signed")

    from app.core.auth.models import Clinic

    clinic = await db.get(Clinic, ctx.clinic_id)
    pdf_bytes = await BudgetPDFService.generate_pdf(
        budget,
        clinic,
        is_preview=False,
        locale=locale,
        signature=signature,
    )

    filename = f"presupuesto_{budget.budget_number}_v{budget.version}_firmado.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/budgets/{budget_id}/signature",
    response_model=ApiResponse[SignatureMetaResponse],
)
async def get_budget_signature_meta(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SignatureMetaResponse]:
    """Return the latest acceptance signature without the raw PNG.

    Powers the staff signature card. 404 when not signed yet.
    """
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=False)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    from .models import BudgetSignature

    sig_q = (
        select(BudgetSignature)
        .where(
            BudgetSignature.budget_id == budget_id,
            BudgetSignature.clinic_id == ctx.clinic_id,
            BudgetSignature.signature_type == "full_acceptance",
        )
        .order_by(BudgetSignature.signed_at.desc())
        .limit(1)
    )
    signature = (await db.execute(sig_q)).scalar_one_or_none()
    if signature is None:
        raise HTTPException(status_code=404, detail="Budget has not been signed")

    return ApiResponse(data=SignatureMetaResponse.model_validate(signature))


@router.get("/budgets/{budget_id}/pdf/preview")
async def preview_budget_pdf(
    budget_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("budget.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    locale: str = Query(default="es", pattern="^(es|en)$"),
) -> Response:
    """Preview budget PDF (with watermark for drafts)."""
    budget = await BudgetService.get_budget(db, ctx.clinic_id, budget_id, include_items=True)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    # Get clinic for branding
    from app.core.auth.models import Clinic

    clinic = await db.get(Clinic, ctx.clinic_id)

    pdf_bytes = await BudgetPDFService.generate_pdf(
        budget,
        clinic,
        is_preview=True,
        locale=locale,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )
