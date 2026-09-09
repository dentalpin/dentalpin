"""sdi_it HTTP surface — mounted at ``/api/v1/sdi_it/``.

Manual transport (this PR): the admin lists records, downloads the
FPR12 XML, marks it exported once uploaded to the SDI, imports the
receipt XML the SDI returns, and requeues a rejected invoice with the
same number and date (spec: scarto ⇒ re-send within 5 days).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db
from app.modules.billing.models import Invoice

from .hook import get_settings, requeue
from .models import SdiItRecord, SdiItSettings
from .schemas import (
    ReceiptImport,
    ReceiptImportResult,
    SdiRecordResponse,
    SdiSettingsResponse,
    SdiSettingsUpdate,
)
from .services.receipts import STATE_FOR_RECEIPT, ReceiptError, parse_receipt
from .services.xml_builder import SdiBuildError

router = APIRouter()

_TERMINAL = {"delivered", "undeliverable"}


def _settings_response(s: SdiItSettings | None) -> SdiSettingsResponse:
    return SdiSettingsResponse(
        enabled=bool(s and s.enabled),
        transport=s.transport if s else "manual",
        regime_fiscale=s.regime_fiscale if s else "RF01",
        bollo_virtuale=s.bollo_virtuale if s else True,
        riferimento_normativo=(
            s.riferimento_normativo if s else "Esente IVA art. 10 n. 18 DPR 633/72"
        ),
        progressivo_invio=s.progressivo_invio if s else 0,
        last_receipt_at=s.last_receipt_at if s else None,
        last_error=s.last_error if s else None,
    )


@router.get("/settings", response_model=ApiResponse[SdiSettingsResponse])
async def get_sdi_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sdi_it.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SdiSettingsResponse]:
    return ApiResponse(data=_settings_response(await get_settings(db, ctx.clinic_id)))


@router.put("/settings", response_model=ApiResponse[SdiSettingsResponse])
async def update_sdi_settings(
    data: SdiSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sdi_it.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SdiSettingsResponse]:
    s = await get_settings(db, ctx.clinic_id)
    if s is None:
        s = SdiItSettings(clinic_id=ctx.clinic_id, enabled=False)
        db.add(s)
    for field in ("transport", "regime_fiscale", "bollo_virtuale", "riferimento_normativo"):
        value = getattr(data, field)
        if value is not None:
            setattr(s, field, value)
    if data.enabled is not None:
        s.enabled = data.enabled
        if data.enabled:
            s.last_error = None
    await db.commit()
    await db.refresh(s)
    return ApiResponse(data=_settings_response(s))


async def _record(db: AsyncSession, clinic_id: UUID, record_id: UUID) -> SdiItRecord:
    row = (
        await db.execute(
            select(SdiItRecord).where(
                SdiItRecord.id == record_id, SdiItRecord.clinic_id == clinic_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record SDI non trovato")
    return row


@router.get("/records", response_model=PaginatedApiResponse[SdiRecordResponse])
async def list_records(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sdi_it.records.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    state: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedApiResponse[SdiRecordResponse]:
    base = select(SdiItRecord).where(SdiItRecord.clinic_id == ctx.clinic_id)
    if state:
        base = base.where(SdiItRecord.state == state)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                base.order_by(SdiItRecord.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return PaginatedApiResponse(
        data=[SdiRecordResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/records/{record_id}/xml")
async def download_record_xml(
    record_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sdi_it.records.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    row = await _record(db, ctx.clinic_id, record_id)
    return Response(
        content=row.xml_payload,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{row.file_name}"'},
    )


@router.post("/records/{record_id}/exported", response_model=ApiResponse[SdiRecordResponse])
async def mark_exported(
    record_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sdi_it.records.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SdiRecordResponse]:
    """The admin uploaded the file to the SDI (portal/PEC): await the receipt."""
    row = await _record(db, ctx.clinic_id, record_id)
    if row.state not in ("pending", "exported"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Il record è in stato {row.state}")
    row.state = "exported"
    row.attempts += 1
    row.sent_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=SdiRecordResponse.model_validate(row))


@router.post("/records/{record_id}/requeue", response_model=ApiResponse[SdiRecordResponse])
async def requeue_record(
    record_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sdi_it.records.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SdiRecordResponse]:
    """After a scarto: rebuild the file from the (corrected) invoice with the
    same number and date and a new progressivo; the old record stays as history."""
    row = await _record(db, ctx.clinic_id, record_id)
    if row.state != "rejected":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Solo un record scartato può essere reinviato"
        )
    settings = await get_settings(db, ctx.clinic_id)
    if settings is None or not settings.enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Modulo SDI non attivo")
    invoice = (
        await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.items), selectinload(Invoice.credit_note_for))
            .where(Invoice.id == row.invoice_id, Invoice.clinic_id == ctx.clinic_id)
        )
    ).scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fattura non trovata")
    try:
        new = await requeue(
            db,
            row,
            invoice,
            settings,
            original=invoice.credit_note_for if row.tipo_documento == "TD04" else None,
        )
    except SdiBuildError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await db.commit()
    await db.refresh(new)
    return ApiResponse(data=SdiRecordResponse.model_validate(new))


@router.post("/receipts", response_model=ApiResponse[ReceiptImportResult])
async def import_receipt(
    data: ReceiptImport,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sdi_it.records.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReceiptImportResult]:
    """Apply an SDI receipt (RC/NS/MC) to the record its ``NomeFile`` names."""
    try:
        receipt = parse_receipt(data.xml, receipt_file_name=data.file_name)
    except ReceiptError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    new_state = STATE_FOR_RECEIPT.get(receipt.type)
    if new_state is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Ricevuta {receipt.type} non applicabile a una fattura FPR12",
        )
    if not receipt.nome_file:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La ricevuta non indica il NomeFile")
    stem = receipt.nome_file.rsplit(".", 1)[0]
    row = (
        (
            await db.execute(
                select(SdiItRecord)
                .where(
                    SdiItRecord.clinic_id == ctx.clinic_id,
                    SdiItRecord.file_name.in_(
                        (receipt.nome_file, f"{stem}.xml", f"{stem}.xml.p7m")
                    ),
                )
                .order_by(SdiItRecord.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Nessun record per il file {receipt.nome_file}"
        )
    if row.state in _TERMINAL and row.receipt_type == receipt.type:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ricevuta già importata")
    now = datetime.now(UTC)
    row.state = new_state
    row.receipt_type = receipt.type
    row.receipt_xml = data.xml
    row.receipt_at = now
    row.sdi_identifier = receipt.identificativo_sdi or row.sdi_identifier
    row.finished_at = now
    if receipt.type == "NS":
        row.error_code = ", ".join(c for c, _ in receipt.errors)[:60] or "NS"
        row.error_message = "; ".join(f"{c}: {d}" for c, d in receipt.errors)[:2000] or receipt.note
    else:
        row.error_code = None
        row.error_message = receipt.note if receipt.type == "MC" else None
    settings = await get_settings(db, ctx.clinic_id)
    if settings is not None:
        settings.last_receipt_at = now
    await db.commit()
    return ApiResponse(
        data=ReceiptImportResult(
            record_id=row.id,
            receipt_type=receipt.type,
            state=row.state,
            errors=[{"code": c, "description": d} for c, d in receipt.errors],
        )
    )
