"""Billing module API router."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db
from app.modules.budget.service import lookup_linked_plan
from app.modules.payments.schemas import PaymentResponse

from .hooks import BillingHookRegistry
from .models import Invoice
from .schemas import (
    BillingPartyUpdate,
    BillingSettingsResponse,
    BillingSettingsUpdate,
    CreditNoteCreate,
    InvoiceCreate,
    InvoiceDetailResponse,
    InvoiceFromBudgetCreate,
    InvoiceHistoryResponse,
    InvoiceIssueRequest,
    InvoiceItemCreate,
    InvoiceItemResponse,
    InvoiceItemUpdate,
    InvoiceListResponse,
    InvoicePaymentApply,
    InvoicePaymentDetailResponse,
    InvoicePaymentResponse,
    InvoiceResponse,
    InvoiceSendRequest,
    InvoiceSeriesCreate,
    InvoiceSeriesResponse,
    InvoiceSeriesUpdate,
    InvoiceUpdate,
    PatientBillingSummary,
    SeriesResetRequest,
)
from .service import (
    InvoiceHistoryService,
    InvoiceItemService,
    InvoicePaymentService,
    InvoiceSeriesService,
    InvoiceService,
    compute_paid_summaries_for_invoices,
    compute_paid_summary,
    vat_legal_notes_for_invoice,
)
from .workflow import InvoiceWorkflowError, InvoiceWorkflowService


def _attach_paid_summary(
    response: InvoiceResponse | InvoiceListResponse | InvoiceDetailResponse,
    paid: tuple,
) -> None:
    """In-place set ``total_paid`` / ``balance_due`` on a response."""
    total_paid, balance_due = paid
    response.total_paid = total_paid
    response.balance_due = balance_due


router = APIRouter()


# ============================================================================
# Invoice Series Endpoints
# ============================================================================


@router.get("/series", response_model=ApiResponse[list[InvoiceSeriesResponse]])
async def list_series(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    series_type: str | None = Query(default=None),
    active_only: bool = Query(default=True),
) -> ApiResponse[list[InvoiceSeriesResponse]]:
    """List invoice series for the clinic."""
    series = await InvoiceSeriesService.list_series(
        db, ctx.clinic_id, series_type=series_type, active_only=active_only
    )
    return ApiResponse(data=[InvoiceSeriesResponse.model_validate(s) for s in series])


@router.post("/series", response_model=ApiResponse[InvoiceSeriesResponse], status_code=201)
async def create_series(
    data: InvoiceSeriesCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceSeriesResponse]:
    """Create a new invoice series."""
    try:
        series = await InvoiceSeriesService.create_series(db, ctx.clinic_id, data.model_dump())
        await db.commit()
        return ApiResponse(data=InvoiceSeriesResponse.model_validate(series))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/series/{series_id}", response_model=ApiResponse[InvoiceSeriesResponse])
async def update_series(
    series_id: UUID,
    data: InvoiceSeriesUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceSeriesResponse]:
    """Update an invoice series."""
    from sqlalchemy import select

    from .models import InvoiceSeries

    result = await db.execute(
        select(InvoiceSeries).where(
            InvoiceSeries.id == series_id,
            InvoiceSeries.clinic_id == ctx.clinic_id,
        )
    )
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    try:
        series = await InvoiceSeriesService.update_series(
            db, series, data.model_dump(exclude_unset=True), changed_by=ctx.user_id
        )
        await db.commit()
        return ApiResponse(data=InvoiceSeriesResponse.model_validate(series))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/series/{series_id}/reset", response_model=ApiResponse[InvoiceSeriesResponse])
async def reset_series_counter(
    series_id: UUID,
    data: SeriesResetRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceSeriesResponse]:
    """Reset series counter to a new number.

    The new number must be greater than the highest sequential_number
    of any invoice in this series to prevent duplicate invoice numbers.
    """
    from sqlalchemy import select

    from .models import InvoiceSeries

    result = await db.execute(
        select(InvoiceSeries).where(
            InvoiceSeries.id == series_id,
            InvoiceSeries.clinic_id == ctx.clinic_id,
        )
    )
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    try:
        series = await InvoiceSeriesService.reset_series_counter(
            db, series, data.new_number, ctx.user_id
        )
        await db.commit()
        return ApiResponse(data=InvoiceSeriesResponse.model_validate(series))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Invoice CRUD Endpoints
# ============================================================================


VALID_COMPLIANCE_SEVERITIES = {"ok", "warning", "pending", "error"}


@router.get("/invoices", response_model=PaginatedApiResponse[InvoiceListResponse])
async def list_invoices(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    patient_id: UUID | None = None,
    status: list[str] | None = Query(default=None),
    date_from: date | None = None,
    date_to: date | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    overdue: bool | None = None,
    search: str | None = None,
    budget_id: UUID | None = None,
    is_credit_note: bool | None = None,
    compliance_severity: list[str] | None = Query(
        default=None,
        description=(
            "Filter by compliance severity (any country). One of: "
            "ok, warning, pending, error. Whitelist-validated."
        ),
    ),
    sort: str | None = Query(default=None, max_length=50),
) -> PaginatedApiResponse[InvoiceListResponse]:
    """List invoices with filtering and pagination."""
    if compliance_severity:
        bad = set(compliance_severity) - VALID_COMPLIANCE_SEVERITIES
        if bad:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid compliance_severity values: {sorted(bad)}",
            )
    invoices, total = await InvoiceService.list_invoices(
        db,
        ctx.clinic_id,
        page=page,
        page_size=page_size,
        patient_id=patient_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        due_from=due_from,
        due_to=due_to,
        overdue=overdue,
        search=search,
        budget_id=budget_id,
        is_credit_note=is_credit_note,
        compliance_severity=compliance_severity,
        sort=sort,
    )
    items = [InvoiceListResponse.model_validate(i) for i in invoices]
    summaries = await compute_paid_summaries_for_invoices(
        db, ctx.clinic_id, [i.id for i in invoices]
    )
    for inv, resp in zip(invoices, items):
        _attach_paid_summary(resp, summaries.get(inv.id, (0, inv.total)))
    return PaginatedApiResponse(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/invoices/{invoice_id}", response_model=ApiResponse[InvoiceDetailResponse])
async def get_invoice(
    invoice_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceDetailResponse]:
    """Get invoice details with items and payments."""
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=True, include_payments=True
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    response = InvoiceDetailResponse.model_validate(invoice)
    if invoice.budget_id:
        response.treatment_plan = await lookup_linked_plan(db, ctx.clinic_id, invoice.budget_id)
    summaries = await compute_paid_summaries_for_invoices(db, ctx.clinic_id, [invoice.id])
    _attach_paid_summary(response, summaries.get(invoice.id, (0, invoice.total)))
    return ApiResponse(data=response)


@router.post("/invoices", response_model=ApiResponse[InvoiceResponse], status_code=201)
async def create_invoice(
    data: InvoiceCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceResponse]:
    """Create a new invoice manually.

    Draft invoices don't store billing data - it comes from patient dynamically.
    When issued, billing data is snapshotted from patient.
    """
    try:
        notes = {
            "internal_notes": data.internal_notes,
            "public_notes": data.public_notes,
        }

        invoice = await InvoiceService.create_invoice(
            db,
            clinic_id=ctx.clinic_id,
            created_by=ctx.user_id,
            patient_id=data.patient_id,
            series_id=data.series_id,
            payment_term_days=data.payment_term_days,
            due_date=data.due_date,
            notes=notes,
        )

        # Add items if provided
        for item_data in data.items:
            await InvoiceItemService.create_item(db, ctx.clinic_id, invoice, item_data.model_dump())

        await db.commit()

        # Reload with relationships for response
        invoice = await InvoiceService.get_invoice(
            db, ctx.clinic_id, invoice.id, include_items=False, include_payments=False
        )

        return ApiResponse(data=InvoiceResponse.model_validate(invoice))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/invoices/from-budget/{budget_id}",
    response_model=ApiResponse[InvoiceResponse],
    status_code=201,
)
async def create_invoice_from_budget(
    budget_id: UUID,
    data: InvoiceFromBudgetCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceResponse]:
    """Create an invoice from a budget with partial invoicing support.

    Draft invoices don't store billing data - it comes from patient dynamically.
    When issued, billing data is snapshotted from patient.
    """
    try:
        notes = {
            "internal_notes": data.internal_notes,
            "public_notes": data.public_notes,
        }

        items = [
            {"budget_item_id": item.budget_item_id, "quantity": item.quantity}
            for item in data.items
        ]

        invoice = await InvoiceService.create_from_budget(
            db,
            clinic_id=ctx.clinic_id,
            created_by=ctx.user_id,
            budget_id=budget_id,
            items=items,
            payment_term_days=data.payment_term_days,
            due_date=data.due_date,
            notes=notes,
        )

        await db.commit()

        # Reload with relationships for response
        invoice = await InvoiceService.get_invoice(
            db, ctx.clinic_id, invoice.id, include_items=False, include_payments=False
        )

        return ApiResponse(data=InvoiceResponse.model_validate(invoice))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/invoices/{invoice_id}", response_model=ApiResponse[InvoiceResponse])
async def update_invoice(
    invoice_id: UUID,
    data: InvoiceUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceResponse]:
    """Update an invoice (only drafts).

    Draft invoices can have patient changed. Billing data comes from patient.
    """
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=False, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        update_data = data.model_dump(exclude_unset=True)
        invoice = await InvoiceService.update_invoice(db, invoice, ctx.user_id, update_data)
        await db.commit()

        # Reload to get updated patient data
        invoice = await InvoiceService.get_invoice(
            db, ctx.clinic_id, invoice_id, include_items=False, include_payments=False
        )
        return ApiResponse(data=InvoiceResponse.model_validate(invoice))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/invoices/{invoice_id}/billing-party",
    response_model=ApiResponse[InvoiceResponse],
)
async def update_billing_party(
    invoice_id: UUID,
    data: BillingPartyUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceResponse]:
    """Edit billing party (NIF / name / address) on an issued invoice.

    Allowed only when:

    * The invoice is still ``draft`` (no compliance record yet), OR
    * The compliance hook says the latest fiscal record is correctable
      (Verifactu: ``rejected`` / ``failed_validation``).

    On success, triggers an automatic regenerate of the compliance
    record (Verifactu Subsanación) so the user does not need a second
    click in the queue.

    Optimistic lock via ``expected_updated_at`` — 409 on mismatch.
    """

    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=False, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        await InvoiceWorkflowService.update_billing_party(
            db,
            invoice,
            new_name=data.billing_name,
            new_tax_id=data.billing_tax_id,
            new_address=data.billing_address,
            expected_updated_at=data.expected_updated_at,
            changed_by=ctx.user_id,
        )
        await db.commit()
    except InvoiceWorkflowError as e:
        # 409 when optimistic-lock mismatch, 422 otherwise.
        status = 409 if "concurrent" in str(e).lower() else 422
        raise HTTPException(status_code=status, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=False, include_payments=False
    )
    return ApiResponse(data=InvoiceResponse.model_validate(invoice))


@router.delete("/invoices/{invoice_id}", status_code=204)
async def delete_invoice(
    invoice_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft delete an invoice (only drafts)."""
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=False, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        await InvoiceService.delete_invoice(db, invoice, ctx.user_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Invoice Item Endpoints
# ============================================================================


@router.post(
    "/invoices/{invoice_id}/items",
    response_model=ApiResponse[InvoiceItemResponse],
    status_code=201,
)
async def add_invoice_item(
    invoice_id: UUID,
    data: InvoiceItemCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceItemResponse]:
    """Add an item to an invoice."""
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=True, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if not InvoiceWorkflowService.can_edit(invoice):
        raise HTTPException(status_code=400, detail="Can only edit draft invoices")

    try:
        item = await InvoiceItemService.create_item(db, ctx.clinic_id, invoice, data.model_dump())
        await db.commit()
        return ApiResponse(data=InvoiceItemResponse.model_validate(item))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/invoices/{invoice_id}/items/{item_id}",
    response_model=ApiResponse[InvoiceItemResponse],
)
async def update_invoice_item(
    invoice_id: UUID,
    item_id: UUID,
    data: InvoiceItemUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceItemResponse]:
    """Update an invoice item."""
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=True, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if not InvoiceWorkflowService.can_edit(invoice):
        raise HTTPException(status_code=400, detail="Can only edit draft invoices")

    item = next((i for i in invoice.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        item = await InvoiceItemService.update_item(
            db, ctx.clinic_id, item, invoice, data.model_dump(exclude_unset=True)
        )
        await db.commit()
        return ApiResponse(data=InvoiceItemResponse.model_validate(item))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/invoices/{invoice_id}/items/{item_id}", status_code=204)
async def delete_invoice_item(
    invoice_id: UUID,
    item_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete an invoice item."""
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=True, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if not InvoiceWorkflowService.can_edit(invoice):
        raise HTTPException(status_code=400, detail="Can only edit draft invoices")

    item = next((i for i in invoice.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    await InvoiceItemService.delete_item(db, item, invoice)
    await db.commit()


# ============================================================================
# Workflow Endpoints
# ============================================================================


@router.post("/invoices/{invoice_id}/issue", response_model=ApiResponse[InvoiceResponse])
async def issue_invoice(
    invoice_id: UUID,
    data: InvoiceIssueRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceResponse]:
    """Issue an invoice or credit note (transition from draft to issued)."""
    from sqlalchemy import select

    from .models import Invoice

    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=True, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Serialize concurrent issue of the same draft (audit S3/C4, #97): lock
    # the row and refresh status, so a second request sees the committed
    # "issued" state and the workflow's draft-only guard rejects it —
    # instead of both burning a sequential number + chaining a duplicate
    # AEAT record.
    await db.execute(
        select(Invoice.id)
        .where(Invoice.id == invoice_id, Invoice.clinic_id == ctx.clinic_id)
        .with_for_update()
    )
    await db.refresh(invoice, attribute_names=["status"])

    # If this is a credit note, load the original invoice for the hook
    original_invoice = None
    if invoice.credit_note_for_id:
        original_invoice = await InvoiceService.get_invoice(
            db,
            ctx.clinic_id,
            invoice.credit_note_for_id,
            include_items=False,
            include_payments=False,
        )

    try:
        # Get compliance hook if available
        hook = None
        clinic = invoice.clinic
        if clinic:
            hook = BillingHookRegistry.get_for_clinic(clinic)

        hook_callback = None
        if hook:
            # Validate required fields
            for field in hook.get_required_fields():
                value = getattr(invoice, field, None)
                if not value:
                    raise InvoiceWorkflowError(f"Field '{field}' is required")

            # Validate before issue
            is_valid, error = await hook.validate_before_issue(invoice, db)
            if not is_valid:
                raise InvoiceWorkflowError(error)

            # Set up hook callback (for regular invoices only)
            if not invoice.credit_note_for_id:

                async def hook_callback(inv, db_session):
                    return await hook.on_invoice_issued(inv, db_session)

        invoice = await InvoiceWorkflowService.issue_invoice(
            db, invoice, ctx.user_id, issue_date=data.issue_date, hook_callback=hook_callback
        )

        # For credit notes, execute the credit note hook after issue
        if hook and original_invoice:
            compliance_data = await hook.on_credit_note_issued(invoice, original_invoice, db)
            if compliance_data:
                invoice.compliance_data = invoice.compliance_data or {}
                invoice.compliance_data.update(compliance_data)
                await db.flush()

        await db.commit()
        return ApiResponse(data=InvoiceResponse.model_validate(invoice))
    except InvoiceWorkflowError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/invoices/{invoice_id}/send-email", response_model=ApiResponse[InvoiceResponse])
async def send_invoice_email(
    invoice_id: UUID,
    data: InvoiceSendRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceResponse]:
    """Send an invoice to the patient (email or WhatsApp via the gateway).

    Only issued/partial/paid invoices can be sent (not drafts or voided).
    """
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=True, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Can only send non-draft invoices
    if invoice.status not in ["issued", "partial", "paid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot send invoice with status '{invoice.status}'. Invoice must be issued first.",
        )

    # Check the patient has the contact the chosen channel needs
    send_method = data.resolved_send_method
    patient = invoice.patient
    if send_method == "email" and (not patient or not patient.email):
        raise HTTPException(
            status_code=400,
            detail="Cannot send email: patient has no email address",
        )
    if send_method == "whatsapp" and (not patient or not patient.phone):
        raise HTTPException(
            status_code=400,
            detail="Cannot send WhatsApp: patient has no phone number",
        )

    recipient_email = patient.email if patient and send_method == "email" else None

    # Publish event for notifications module
    from app.core.events import EventType, event_bus

    await event_bus.publish(
        EventType.INVOICE_SENT,
        {
            "clinic_id": str(ctx.clinic_id),
            "invoice_id": str(invoice.id),
            "patient_id": str(invoice.patient_id),
            "send_method": send_method,
            "recipient_email": recipient_email,
            "custom_message": data.custom_message,
        },
        db=db,
    )

    # Add history entry
    await InvoiceHistoryService.add_entry(
        db,
        clinic_id=invoice.clinic_id,
        invoice_id=invoice.id,
        action="sent",
        changed_by=ctx.user_id,
        previous_state={},
        new_state={
            "send_method": send_method,
            "recipient_email": recipient_email,
        },
    )

    await db.commit()

    return ApiResponse(data=InvoiceResponse.model_validate(invoice))


@router.post("/invoices/{invoice_id}/void", response_model=ApiResponse[InvoiceResponse])
async def void_invoice(
    invoice_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str | None = None,
) -> ApiResponse[InvoiceResponse]:
    """Void an invoice (only drafts)."""
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=False, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        invoice = await InvoiceWorkflowService.void_invoice(db, invoice, ctx.user_id, reason)
        await db.commit()
        return ApiResponse(data=InvoiceResponse.model_validate(invoice))
    except InvoiceWorkflowError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/invoices/{invoice_id}/credit-note",
    response_model=ApiResponse[InvoiceResponse],
    status_code=201,
)
async def create_credit_note(
    invoice_id: UUID,
    data: CreditNoteCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoiceResponse]:
    """Create a credit note (rectificativa) for an invoice in draft status.

    The credit note is created in draft status so it can be edited before
    being issued. Use the /issue endpoint to finalize the credit note.
    """
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=True, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        items = None
        if data.items:
            items = [
                {"invoice_item_id": item.invoice_item_id, "quantity": item.quantity}
                for item in data.items
            ]

        credit_note = await InvoiceWorkflowService.create_credit_note(
            db,
            original_invoice=invoice,
            created_by=ctx.user_id,
            reason=data.reason,
            items=items,
        )
        await db.commit()

        # Reload with relationships for response
        credit_note = await InvoiceService.get_invoice(
            db, ctx.clinic_id, credit_note.id, include_items=False, include_payments=False
        )

        return ApiResponse(data=InvoiceResponse.model_validate(credit_note))
    except InvoiceWorkflowError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Invoice ↔ Payment Endpoints
# ============================================================================
#
# Payment lifecycle (create, refund, reallocate, list across clinic)
# lives in the payments module. Here billing exposes:
#
# - GET  /invoices/{id}/payments       — payment links for one invoice
# - POST /invoices/{id}/payments       — orchestrator: create Payment +
#                                        InvoicePayment in one go (the
#                                        common "factura+cobro" flow)
#
# To register an anticipo (against a budget, no invoice yet) or to
# refund a payment, use ``/api/v1/payments/*`` directly.


@router.get(
    "/invoices/{invoice_id}/payments",
    response_model=ApiResponse[list[InvoicePaymentDetailResponse]],
)
async def list_invoice_payments(
    invoice_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[InvoicePaymentDetailResponse]]:
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=False, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    rows = await InvoicePaymentService.list_for_invoice(db, ctx.clinic_id, invoice_id)
    return ApiResponse(
        data=[
            InvoicePaymentDetailResponse(
                **InvoicePaymentResponse.model_validate(r).model_dump(),
                payment=PaymentResponse.from_model(r.payment),
            )
            for r in rows
        ]
    )


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=ApiResponse[InvoicePaymentResponse],
    status_code=201,
)
async def apply_payment_to_invoice(
    invoice_id: UUID,
    payload: InvoicePaymentApply,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InvoicePaymentResponse]:
    """Create a Payment and impute it to this invoice atomically.

    Convenience for the common case ``record the cobro al facturar``.
    For anticipos that don't yet have an invoice, use POST
    ``/api/v1/payments`` and later reallocate.
    """
    # Lazy imports: billing imports payments (depends), but payments
    # doesn't import billing — keeping the top-level imports clean
    # prevents circular initialisation through catalog/budget.
    from sqlalchemy import select

    from app.modules.payments.workflow import PaymentWorkflowError, record_payment

    from .models import Invoice, InvoicePayment
    from .payment_bridge import lock_budget

    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=False, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not InvoiceWorkflowService.can_record_payment(invoice):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot record payment for invoice with status '{invoice.status}'",
        )

    # Serialize concurrent payments against this invoice (audit S3/C2, #97):
    # lock the invoice row so two requests can't both read the full balance
    # and each record a payment, over-collecting past the total. Lock
    # order is budget → invoice (see ``payment_bridge.lock_budget``).
    if invoice.budget_id is not None:
        await lock_budget(db, ctx.clinic_id, invoice.budget_id)
    await db.execute(
        select(Invoice.id)
        .where(Invoice.id == invoice_id, Invoice.clinic_id == ctx.clinic_id)
        .with_for_update()
    )

    total_paid, balance_due = await compute_paid_summary(db, ctx.clinic_id, invoice_id)
    if payload.amount > balance_due:
        raise HTTPException(
            status_code=400,
            detail=f"Payment amount ({payload.amount}) exceeds balance due ({balance_due})",
        )

    # Invoices born from a quote collect *against the quote*: the
    # allocation targets ``invoice.budget_id`` and the transactional
    # ``payment.allocated`` handler (``payment_bridge``) creates the
    # ``invoice_payments`` link, preferring this invoice. Manual invoices
    # keep an ``on_account`` allocation + explicit link (issue #178).
    from_budget = invoice.budget_id is not None
    if from_budget:
        allocations = [
            {"target_type": "budget", "target_id": invoice.budget_id, "amount": payload.amount}
        ]
    else:
        allocations = [{"target_type": "on_account", "amount": payload.amount}]

    try:
        payment = await record_payment(
            db,
            clinic_id=ctx.clinic_id,
            currency=ctx.clinic.currency,
            patient_id=invoice.patient_id,
            amount=payload.amount,
            method=payload.method,
            payment_date=payload.payment_date,
            recorded_by=ctx.user_id,
            allocations=allocations,
            reference=payload.reference,
            notes=payload.notes,
            context={"prefer_invoice_id": str(invoice_id)},
        )
    except PaymentWorkflowError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if from_budget:
        link_row = await db.execute(
            select(InvoicePayment).where(
                InvoicePayment.invoice_id == invoice_id,
                InvoicePayment.payment_id == payment.id,
            )
        )
        link = link_row.scalar_one()
    else:
        link = InvoicePayment(
            clinic_id=ctx.clinic_id,
            invoice_id=invoice_id,
            payment_id=payment.id,
            amount=payload.amount,
            created_by=ctx.user_id,
        )
        db.add(link)
        await db.flush()
        await InvoiceWorkflowService.recalc_invoice_status(db, invoice, actor_id=ctx.user_id)

    await db.commit()

    return ApiResponse(data=InvoicePaymentResponse.model_validate(link))


# ============================================================================
# History Endpoints
# ============================================================================


@router.get(
    "/invoices/{invoice_id}/history",
    response_model=ApiResponse[list[InvoiceHistoryResponse]],
)
async def get_invoice_history(
    invoice_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[InvoiceHistoryResponse]]:
    """Get invoice history/audit log."""
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=False, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    history = await InvoiceHistoryService.list_history(db, ctx.clinic_id, invoice_id)
    return ApiResponse(data=[InvoiceHistoryResponse.model_validate(h) for h in history])


# ============================================================================
# PDF Endpoints
# ============================================================================


async def _merge_vat_legal_notes(
    db: AsyncSession,
    clinic_id: UUID,
    invoice: Invoice,
    extra_pdf_data: dict | None,
) -> dict | None:
    """Prepend the lines' VAT statutory clauses to the legal-notices block.

    E.g. the Spanish dental exemption (art. 20.Uno.5º LIVA) carried by
    the exempt VAT type (#204). Hook-supplied notices keep their spot
    after the VAT clauses.
    """
    notes = await vat_legal_notes_for_invoice(db, clinic_id, invoice)
    if not notes:
        return extra_pdf_data
    merged = dict(extra_pdf_data or {})
    merged["legal_notices"] = [*notes, *(merged.get("legal_notices") or [])]
    return merged


@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    locale: str = Query(default="es", pattern="^(es|en|ta)$"),
) -> Response:
    """Download invoice as PDF."""
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=True, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Get clinic for branding
    from app.core.auth.models import Clinic

    clinic = await db.get(Clinic, ctx.clinic_id)

    from .hooks import BillingHookRegistry
    from .pdf import InvoicePDFService

    # Country compliance modules (e.g. Veri*Factu) inject QR + legal
    # notices via the registered hook. Billing stays country-agnostic
    # — it only forwards the resulting dict to the PDF service.
    hook = BillingHookRegistry.get_for_clinic(clinic) if clinic else None
    extra_pdf_data = hook.enhance_pdf_data({}, invoice) if hook else None
    extra_pdf_data = await _merge_vat_legal_notes(db, ctx.clinic_id, invoice, extra_pdf_data)

    total_paid, balance_due = await compute_paid_summary(db, ctx.clinic_id, invoice.id)
    pdf_bytes = await InvoicePDFService.generate_pdf(
        invoice,
        clinic,
        is_preview=False,
        locale=locale,
        extra_pdf_data=extra_pdf_data,
        total_paid=total_paid,
        balance_due=balance_due,
    )

    # Generate filename
    if invoice.invoice_number:
        filename = f"factura_{invoice.invoice_number}.pdf"
    else:
        filename = f"factura_borrador_{str(invoice.id)[:8]}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/invoices/{invoice_id}/pdf/preview")
async def preview_invoice_pdf(
    invoice_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    locale: str = Query(default="es", pattern="^(es|en|ta)$"),
) -> Response:
    """Preview invoice PDF (with watermark for drafts)."""
    invoice = await InvoiceService.get_invoice(
        db, ctx.clinic_id, invoice_id, include_items=True, include_payments=False
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Get clinic for branding
    from app.core.auth.models import Clinic

    clinic = await db.get(Clinic, ctx.clinic_id)

    from .hooks import BillingHookRegistry
    from .pdf import InvoicePDFService

    hook = BillingHookRegistry.get_for_clinic(clinic) if clinic else None
    extra_pdf_data = hook.enhance_pdf_data({}, invoice) if hook else None
    extra_pdf_data = await _merge_vat_legal_notes(db, ctx.clinic_id, invoice, extra_pdf_data)

    total_paid, balance_due = await compute_paid_summary(db, ctx.clinic_id, invoice.id)
    pdf_bytes = await InvoicePDFService.generate_pdf(
        invoice,
        clinic,
        is_preview=True,
        locale=locale,
        extra_pdf_data=extra_pdf_data,
        total_paid=total_paid,
        balance_due=balance_due,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


# ============================================================================
# Settings Endpoints
# ============================================================================


@router.get("/settings", response_model=ApiResponse[BillingSettingsResponse])
async def get_billing_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BillingSettingsResponse]:
    """Get billing settings for the clinic."""
    from sqlalchemy import select

    from app.core.auth.models import Clinic

    result = await db.execute(select(Clinic).where(Clinic.id == ctx.clinic_id))
    clinic = result.scalar_one_or_none()

    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    settings = clinic.settings or {}
    billing_settings = settings.get("billing", {})

    return ApiResponse(
        data=BillingSettingsResponse(
            default_payment_term_days=billing_settings.get("default_payment_term_days", 30),
            invoice_footer_text=billing_settings.get("invoice_footer_text"),
            bank_account_info=billing_settings.get("bank_account_info"),
        )
    )


@router.put("/settings", response_model=ApiResponse[BillingSettingsResponse])
async def update_billing_settings(
    data: BillingSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[BillingSettingsResponse]:
    """Update billing settings for the clinic."""
    from sqlalchemy import select

    from app.core.auth.models import Clinic

    result = await db.execute(select(Clinic).where(Clinic.id == ctx.clinic_id))
    clinic = result.scalar_one_or_none()

    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    settings = clinic.settings or {}
    billing_settings = settings.get("billing", {})

    if data.default_payment_term_days is not None:
        billing_settings["default_payment_term_days"] = data.default_payment_term_days
    if data.invoice_footer_text is not None:
        billing_settings["invoice_footer_text"] = data.invoice_footer_text
    if data.bank_account_info is not None:
        billing_settings["bank_account_info"] = data.bank_account_info

    settings["billing"] = billing_settings
    clinic.settings = settings

    await db.commit()

    return ApiResponse(
        data=BillingSettingsResponse(
            default_payment_term_days=billing_settings.get("default_payment_term_days", 30),
            invoice_footer_text=billing_settings.get("invoice_footer_text"),
            bank_account_info=billing_settings.get("bank_account_info"),
        )
    )


# ============================================================================
# Patient Billing Summary
# ============================================================================


@router.get("/patients/{patient_id}/summary", response_model=ApiResponse[PatientBillingSummary])
async def get_patient_billing_summary(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PatientBillingSummary]:
    """Get billing summary for a specific patient.

    Returns aggregated metrics for budgets and invoices.
    """
    from app.modules.reports.services import BillingReportService

    summary = await BillingReportService.get_patient_summary(db, ctx.clinic_id, patient_id)
    return ApiResponse(data=PatientBillingSummary(**summary))
