"""India GST admin + billing-integration router.

Mounted at ``/api/v1/india_gst/`` by the module loader.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .constants import (
    DEFAULT_DENTAL_SAC_CODE,
    gstin_checksum_char,
    gstin_checksum_ok,
    gstin_format_ok,
    state_name,
)
from .models import (
    IndiaGstEinvoiceSubmission,
    IndiaGstInvoiceItem,
    IndiaGstSettings,
)
from .schemas import (
    GstBreakdownResponse,
    GstReportSummaryResponse,
    GstReportTransactionRow,
    IndiaGstCatalogAutoconfigureResponse,
    IndiaGstCatalogDefaultsResponse,
    IndiaGstCatalogItemResponse,
    IndiaGstCatalogItemUpdate,
    IndiaGstEinvoiceResponse,
    IndiaGstEinvoiceRetryError,
    IndiaGstInvoiceDraftUpdate,
    IndiaGstSettingsResponse,
    IndiaGstSettingsUpdate,
    TaxPreviewRequest,
)
from .service import (
    GstLineInput,
    IndiaGstCatalogService,
    compute_gst_breakdown,
    get_or_create_settings,
)

router = APIRouter()


def _settings_response(settings: IndiaGstSettings) -> IndiaGstSettingsResponse:
    payload = IndiaGstSettingsResponse.model_validate(settings, from_attributes=True)
    # Warn (never block) when the supplier GSTIN's leading state code
    # disagrees with clinic_state — a mismatch silently flips the
    # intra/inter-state classification of every invoice (#262).
    mismatch = bool(
        settings.gstin and settings.clinic_state and settings.gstin[:2] != settings.clinic_state
    )
    return payload.model_copy(
        update={
            "clinic_state_name": state_name(settings.clinic_state),
            "gstin_state_mismatch": mismatch,
        }
    )


# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------


@router.get("/settings", response_model=ApiResponse[IndiaGstSettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("india_gst.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[IndiaGstSettingsResponse]:
    settings = await get_or_create_settings(db, ctx.clinic_id)
    await db.commit()
    return ApiResponse(data=_settings_response(settings))


@router.put("/settings", response_model=ApiResponse[IndiaGstSettingsResponse])
async def update_settings(
    body: IndiaGstSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("india_gst.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[IndiaGstSettingsResponse]:
    settings = await get_or_create_settings(db, ctx.clinic_id)

    if body.gstin is not None:
        gstin = body.gstin.strip().upper() or None
        if gstin and not gstin_format_ok(gstin):
            raise HTTPException(status_code=400, detail="Invalid GSTIN format.")
        if gstin and not gstin_checksum_ok(gstin):
            # Right shape, wrong 15th character — almost always a typo
            # in one of the first 14. Caught here, not at filing (#262).
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid GSTIN: the check digit does not match "
                    f"(expected …{gstin_checksum_char(gstin[:14])}). "
                    "Double-check for a typo."
                ),
            )
        settings.gstin = gstin
    if body.trade_name is not None:
        settings.trade_name = body.trade_name.strip() or None
    if body.registration_type is not None:
        settings.registration_type = body.registration_type
    if body.clinic_state is not None:
        settings.clinic_state = body.clinic_state
    if body.turnover_threshold is not None:
        settings.turnover_threshold = body.turnover_threshold
    if body.show_gstin_on_invoice is not None:
        settings.show_gstin_on_invoice = body.show_gstin_on_invoice
    if body.show_sac_on_invoice is not None:
        settings.show_sac_on_invoice = body.show_sac_on_invoice

    await db.commit()
    await db.refresh(settings)
    return ApiResponse(data=_settings_response(settings))


# ----------------------------------------------------------------------------
# Catalog defaults (SAC codes)
# ----------------------------------------------------------------------------


@router.get("/catalog-defaults", response_model=ApiResponse[IndiaGstCatalogDefaultsResponse])
async def get_catalog_defaults(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("india_gst.catalog.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[IndiaGstCatalogDefaultsResponse]:
    from .models import IndiaGstCatalogItem

    configured_q = await db.execute(
        select(IndiaGstCatalogItem).where(IndiaGstCatalogItem.clinic_id == ctx.clinic_id)
    )
    configured = [IndiaGstCatalogItemResponse.model_validate(row) for row in configured_q.scalars()]
    missing = await IndiaGstCatalogService.list_missing_sac(db, ctx.clinic_id)
    return ApiResponse(data=IndiaGstCatalogDefaultsResponse(configured=configured, missing=missing))


@router.post(
    "/catalog-defaults/autoconfigure",
    response_model=ApiResponse[IndiaGstCatalogAutoconfigureResponse],
)
async def autoconfigure_catalog_defaults(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("india_gst.catalog.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[IndiaGstCatalogAutoconfigureResponse]:
    """Assign the default dental SAC to every treatment still missing one.

    Additive only: treatments that already have a default keep it, so this
    is safe to re-run and never silently rewrites an accountant's choice.
    Declared before the ``/{catalog_item_id}`` route would matter only for
    GET/PUT, but keeping it above documents the intent.
    """
    created = await IndiaGstCatalogService.autoconfigure_missing_sac(db, ctx.clinic_id)
    await IndiaGstCatalogService.ensure_gst_vat_type(db, ctx.clinic_id)
    await db.commit()
    return ApiResponse(
        data=IndiaGstCatalogAutoconfigureResponse(
            configured_count=created, sac_code=DEFAULT_DENTAL_SAC_CODE
        )
    )


@router.put(
    "/catalog-defaults/{catalog_item_id}",
    response_model=ApiResponse[IndiaGstCatalogItemResponse],
)
async def update_catalog_default(
    catalog_item_id: UUID,
    body: IndiaGstCatalogItemUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("india_gst.catalog.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[IndiaGstCatalogItemResponse]:
    from app.modules.catalog.models import TreatmentCatalogItem

    item_q = await db.execute(
        select(TreatmentCatalogItem.id).where(
            TreatmentCatalogItem.id == catalog_item_id,
            TreatmentCatalogItem.clinic_id == ctx.clinic_id,
        )
    )
    if item_q.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    row = await IndiaGstCatalogService.upsert(
        db,
        ctx.clinic_id,
        catalog_item_id,
        sac_code=body.sac_code,
        notes=body.notes,
    )
    await db.commit()
    return ApiResponse(data=IndiaGstCatalogItemResponse.model_validate(row))


# ----------------------------------------------------------------------------
# Tax preview (draft-time, stateless, Decimal-safe)
# ----------------------------------------------------------------------------


@router.post("/tax-preview", response_model=ApiResponse[GstBreakdownResponse])
async def tax_preview(
    body: TaxPreviewRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("india_gst.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[GstBreakdownResponse]:
    settings = await get_or_create_settings(db, ctx.clinic_id)
    await db.commit()

    lines = [
        GstLineInput(
            invoice_item_id=item.invoice_item_id,
            vat_rate=item.vat_rate,
            line_tax=item.line_tax,
            sac_code=item.sac_code,
        )
        for item in body.items
    ]
    breakdown = compute_gst_breakdown(
        lines, clinic_state=settings.clinic_state, place_of_supply=body.place_of_supply
    )
    return ApiResponse(data=GstBreakdownResponse(**dataclasses.asdict(breakdown)))


# ----------------------------------------------------------------------------
# Draft invoice GST fields (pre-issue only)
# ----------------------------------------------------------------------------


@router.put("/invoices/{invoice_id}", response_model=ApiResponse[None])
async def update_invoice_gst_fields(
    invoice_id: UUID,
    body: IndiaGstInvoiceDraftUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("billing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[None]:
    from app.modules.billing.models import Invoice

    invoice_q = await db.execute(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.clinic_id == ctx.clinic_id)
        .options(selectinload(Invoice.items))
    )
    invoice = invoice_q.scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status != "draft":
        # 409 conflict per repo convention — the request is authorized,
        # the invoice's state just no longer allows it.
        raise HTTPException(
            status_code=409, detail="GST fields can only be edited on draft invoices."
        )

    if body.place_of_supply is not None:
        cd = dict(invoice.compliance_data or {})
        india = dict(cd.get("IN") or {})
        india["place_of_supply"] = body.place_of_supply
        cd["IN"] = india
        invoice.compliance_data = cd

    if body.items:
        items_by_id = {i.id: i for i in invoice.items}
        for item_update in body.items:
            invoice_item = items_by_id.get(item_update.invoice_item_id)
            if invoice_item is None:
                raise HTTPException(
                    status_code=404, detail=f"Item {item_update.invoice_item_id} not found"
                )

            row_q = await db.execute(
                select(IndiaGstInvoiceItem).where(
                    IndiaGstInvoiceItem.clinic_id == ctx.clinic_id,
                    IndiaGstInvoiceItem.invoice_item_id == invoice_item.id,
                )
            )
            row = row_q.scalar_one_or_none()
            if row is None:
                row = IndiaGstInvoiceItem(
                    clinic_id=ctx.clinic_id, invoice_item_id=invoice_item.id, tax_type="intra"
                )
                db.add(row)

            row.sac_code = item_update.sac_code

    await db.commit()
    return ApiResponse(data=None)


# ----------------------------------------------------------------------------
# E-invoice (scaffolding — see services/einvoice_provider.py)
# ----------------------------------------------------------------------------


@router.get(
    "/invoices/{invoice_id}/einvoice", response_model=ApiResponse[IndiaGstEinvoiceResponse | None]
)
async def get_einvoice_status(
    invoice_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("india_gst.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[IndiaGstEinvoiceResponse | None]:
    result = await db.execute(
        select(IndiaGstEinvoiceSubmission).where(
            IndiaGstEinvoiceSubmission.invoice_id == invoice_id,
            IndiaGstEinvoiceSubmission.clinic_id == ctx.clinic_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return ApiResponse(data=None)
    return ApiResponse(data=IndiaGstEinvoiceResponse.model_validate(row))


@router.post("/invoices/{invoice_id}/einvoice/retry")
async def retry_einvoice(
    invoice_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("india_gst.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Retry an e-invoice submission.

    No provider is configured in v1 — this never requeues or fabricates
    success. Always responds 409 (the app's global HTTPException handler
    flattens ``detail`` to a plain string, per this repo's
    ``ErrorResponse`` convention — see ``app/main.py``) so the frontend
    can render an honest "configure a provider" message rather than a
    retry button that appears to do something.
    """
    result = await db.execute(
        select(IndiaGstEinvoiceSubmission).where(
            IndiaGstEinvoiceSubmission.invoice_id == invoice_id,
            IndiaGstEinvoiceSubmission.clinic_id == ctx.clinic_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No e-invoice record for this invoice")

    # No e-invoice provider exists in v1 — always 409, never a
    # fabricated success. A real GSP/IRP adapter replaces this line.
    raise HTTPException(status_code=409, detail=IndiaGstEinvoiceRetryError().message)


# ----------------------------------------------------------------------------
# Reports / export (india_gst-owned, reads through billing's service API)
# ----------------------------------------------------------------------------


@router.get("/reports/summary", response_model=ApiResponse[GstReportSummaryResponse])
async def report_summary(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("india_gst.reports.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> ApiResponse[GstReportSummaryResponse]:
    from .reports import build_summary

    summary = await build_summary(db, ctx.clinic_id, date_from=date_from, date_to=date_to)
    return ApiResponse(data=summary)


@router.get("/reports/transactions", response_model=PaginatedApiResponse[GstReportTransactionRow])
async def report_transactions(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("india_gst.reports.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> PaginatedApiResponse[GstReportTransactionRow]:
    from .reports import list_transactions

    rows, total = await list_transactions(
        db, ctx.clinic_id, date_from=date_from, date_to=date_to, page=page, page_size=page_size
    )
    return PaginatedApiResponse(data=rows, total=total, page=page, page_size=page_size)


@router.get("/reports/export")
async def report_export(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("india_gst.reports.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    from fastapi.responses import StreamingResponse

    from .reports import build_export_csv

    csv_bytes = await build_export_csv(db, ctx.clinic_id, date_from=date_from, date_to=date_to)
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gst_transactions.csv"},
    )
