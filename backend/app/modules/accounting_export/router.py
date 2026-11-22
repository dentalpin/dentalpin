"""Accounting export routes — mounted at /api/v1/accounting_export/."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import (
    ClinicContext,
    get_clinic_context,
    require_permission,
)
from app.core.schemas import ApiResponse
from app.core.utils.dates import clinic_zone_for
from app.database import get_db

from .schemas import ExportPreview
from .service import EXPORTABLE_STATUSES, AccountingExportService

router = APIRouter()

_SAMPLE = 10


def _statuses(status: list[str] | None) -> list[str] | None:
    """Whitelist requested statuses; drafts can never leak through."""
    if not status:
        return None
    allowed = [s for s in status if s in EXPORTABLE_STATUSES]
    return allowed or None


@router.get("/preview", response_model=ApiResponse[ExportPreview])
async def preview(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("accounting_export.export.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    status: list[str] | None = Query(default=None),
) -> ApiResponse[ExportPreview]:
    invoices = await AccountingExportService.fetch(
        db, ctx.clinic_id, date_from, date_to, _statuses(status)
    )
    inv_rows = AccountingExportService.invoice_rows(invoices)
    pay_rows = AccountingExportService.payment_rows(
        invoices, await clinic_zone_for(db, ctx.clinic_id)
    )
    base, cuota, total = AccountingExportService.totals(inv_rows)
    return ApiResponse(
        data=ExportPreview(
            invoice_count=len(inv_rows),
            payment_count=len(pay_rows),
            total_base=base,
            total_cuota=cuota,
            total=total,
            sample_invoices=inv_rows[:_SAMPLE],
            sample_payments=pay_rows[:_SAMPLE],
        )
    )


@router.get("/run")
async def run(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("accounting_export.export.run"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    separator: str = Query(default=",", pattern="^[,;]$"),
) -> Response:
    invoices = await AccountingExportService.fetch(
        db, ctx.clinic_id, date_from, date_to, _statuses(status)
    )
    content = AccountingExportService.build_zip(
        invoices, separator, await clinic_zone_for(db, ctx.clinic_id)
    )
    suffix = f"{date_from or 'inicio'}_{date_to or 'fin'}"
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="gestoria_{suffix}.zip"'},
    )
