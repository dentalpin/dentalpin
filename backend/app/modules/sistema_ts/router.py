"""sistema_ts HTTP surface — mounted at ``/api/v1/sistema_ts/``."""

from __future__ import annotations

import base64
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.email.encryption import encrypt_password
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db
from app.modules.catalog.models import TreatmentCatalogItem
from app.modules.patients.models import Patient

from .models import (
    SistemaTsDocument,
    SistemaTsItemType,
    SistemaTsPatientOpposition,
    SistemaTsSettings,
)
from .schemas import (
    ItemTypeResponse,
    ItemTypeUpdate,
    OppositionResponse,
    OppositionUpdate,
    QueueProcessResult,
    TsDocumentResponse,
    TsSettingsResponse,
    TsSettingsUpdate,
)
from .services import submission_queue
from .services.codice_fiscale import normalise_codice_fiscale
from .services.crypto import CertificateError, certificate_expiry, load_certificate
from .services.documents import DocumentError, queue_variazioni_for_patient

router = APIRouter()


def annual_deadline(year: int) -> date:
    """DM 29 ottobre 2025: expenses of year N are due by 31 January N+1."""
    return date(year + 1, 1, 31)


async def get_settings(db: AsyncSession, clinic_id: UUID) -> SistemaTsSettings | None:
    return (
        await db.execute(select(SistemaTsSettings).where(SistemaTsSettings.clinic_id == clinic_id))
    ).scalar_one_or_none()


async def _assert_in_clinic(db: AsyncSession, model, row_id: UUID, clinic_id: UUID) -> None:
    """Cross-clinic ids resolve to 404, never an oracle."""
    exists = (
        await db.execute(select(model.id).where(model.id == row_id, model.clinic_id == clinic_id))
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Non trovato")


async def _year_counts(db: AsyncSession, clinic_id: UUID, year: int) -> tuple[int, int, int]:
    base = (
        select(func.count())
        .select_from(SistemaTsDocument)
        .where(
            SistemaTsDocument.clinic_id == clinic_id,
            SistemaTsDocument.operation == "inserimento",
            SistemaTsDocument.data_emissione >= date(year, 1, 1),
            SistemaTsDocument.data_emissione <= date(year, 12, 31),
        )
    )
    unsent = (
        await db.execute(base.where(SistemaTsDocument.state.in_(("pending", "sending", "failed"))))
    ).scalar_one()
    accepted = (
        await db.execute(
            base.where(SistemaTsDocument.state.in_(("accepted", "accepted_with_warnings")))
        )
    ).scalar_one()
    rejected = (await db.execute(base.where(SistemaTsDocument.state == "rejected"))).scalar_one()
    return unsent, accepted, rejected


async def _settings_response(
    db: AsyncSession, clinic_id: UUID, s: SistemaTsSettings | None
) -> TsSettingsResponse:
    year = datetime.now(UTC).year
    unsent, accepted, rejected = await _year_counts(db, clinic_id, year)
    expiry = None
    try:
        cert = base64.b64decode(s.certificate_b64) if s and s.certificate_b64 else None
        expiry = certificate_expiry(cert)
    except (CertificateError, ValueError):
        expiry = None
    return TsSettingsResponse(
        enabled=bool(s and s.enabled),
        environment=s.environment if s else "test",
        username=s.username if s else None,
        has_password=bool(s and s.password_encrypted),
        has_pincode=bool(s and s.pincode_encrypted),
        has_custom_certificate=bool(s and s.certificate_b64),
        certificate_expires_at=expiry,
        cf_proprietario=s.cf_proprietario if s else None,
        codice_regione=s.codice_regione if s else None,
        codice_asl=s.codice_asl if s else None,
        codice_ssa=s.codice_ssa if s else None,
        dispositivo=s.dispositivo if s else "1",
        default_tipo_spesa=s.default_tipo_spesa if s else "SR",
        sync_from=s.sync_from if s else None,
        last_response_at=s.last_response_at if s else None,
        next_send_after=s.next_send_after if s else None,
        last_error=s.last_error if s else None,
        year=year,
        deadline=annual_deadline(year),
        unsent_count=unsent,
        accepted_count=accepted,
        rejected_count=rejected,
    )


@router.get("/settings", response_model=ApiResponse[TsSettingsResponse])
async def get_ts_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sistema_ts.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[TsSettingsResponse]:
    return ApiResponse(
        data=await _settings_response(db, ctx.clinic_id, await get_settings(db, ctx.clinic_id))
    )


@router.put("/settings", response_model=ApiResponse[TsSettingsResponse])
async def update_ts_settings(
    data: TsSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sistema_ts.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[TsSettingsResponse]:
    s = await get_settings(db, ctx.clinic_id)
    if s is None:
        s = SistemaTsSettings(clinic_id=ctx.clinic_id, enabled=False, environment="test")
        db.add(s)
    for field in (
        "environment",
        "username",
        "codice_regione",
        "codice_asl",
        "codice_ssa",
        "dispositivo",
        "default_tipo_spesa",
        "sync_from",
    ):
        value = getattr(data, field)
        if value is not None:
            setattr(s, field, value)
    if data.cf_proprietario is not None:
        cf = normalise_codice_fiscale(data.cf_proprietario)
        if cf is None and not (data.cf_proprietario.isdigit() and len(data.cf_proprietario) == 11):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Codice fiscale del proprietario non valido"
            )
        s.cf_proprietario = cf or data.cf_proprietario
    if data.password:
        s.password_encrypted = encrypt_password(data.password)
    if data.pincode:
        s.pincode_encrypted = encrypt_password(data.pincode)
    if data.certificate_b64:
        try:
            load_certificate(base64.b64decode(data.certificate_b64))
        except (CertificateError, ValueError) as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"Certificato non valido: {exc}"
            ) from exc
        s.certificate_b64 = data.certificate_b64
    if data.clear_certificate:
        s.certificate_b64 = None
    if data.enabled is not None:
        if data.enabled and not submission_queue.credentials_ok(s):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Per attivare servono utente, password, pincode e codice fiscale del proprietario.",
            )
        s.enabled = data.enabled
        if data.enabled:
            s.last_error = None
            s.next_send_after = None
    await db.commit()
    await db.refresh(s)
    return ApiResponse(data=await _settings_response(db, ctx.clinic_id, s))


@router.get("/documents", response_model=PaginatedApiResponse[TsDocumentResponse])
async def list_documents(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sistema_ts.documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    state: Annotated[str | None, Query()] = None,
    year: Annotated[int | None, Query(ge=2015, le=2100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedApiResponse[TsDocumentResponse]:
    base = select(SistemaTsDocument).where(SistemaTsDocument.clinic_id == ctx.clinic_id)
    if state:
        base = base.where(SistemaTsDocument.state == state)
    if year:
        base = base.where(
            SistemaTsDocument.data_emissione >= date(year, 1, 1),
            SistemaTsDocument.data_emissione <= date(year, 12, 31),
        )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                base.order_by(SistemaTsDocument.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return PaginatedApiResponse(
        data=[TsDocumentResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/documents/by-invoice/{invoice_id}", response_model=ApiResponse[list[TsDocumentResponse]]
)
async def documents_for_invoice(
    invoice_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sistema_ts.documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[TsDocumentResponse]]:
    rows = (
        (
            await db.execute(
                select(SistemaTsDocument)
                .where(
                    SistemaTsDocument.clinic_id == ctx.clinic_id,
                    SistemaTsDocument.invoice_id == invoice_id,
                )
                .order_by(SistemaTsDocument.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return ApiResponse(data=[TsDocumentResponse.model_validate(r) for r in rows])


@router.post("/documents/{document_id}/retry", response_model=ApiResponse[TsDocumentResponse])
async def retry_document(
    document_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sistema_ts.documents.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[TsDocumentResponse]:
    """Put a rejected/failed document back in the queue (after fixing the data)."""
    row = (
        await db.execute(
            select(SistemaTsDocument).where(
                SistemaTsDocument.id == document_id, SistemaTsDocument.clinic_id == ctx.clinic_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento non trovato")
    if row.state not in ("rejected", "failed"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Il documento è in stato {row.state}")
    row.state = "pending"
    row.next_attempt_at = None
    row.error_message = None
    row.finished_at = None
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=TsDocumentResponse.model_validate(row))


@router.post("/queue/process-now", response_model=ApiResponse[QueueProcessResult])
async def process_now(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sistema_ts.documents.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[QueueProcessResult]:
    s = await get_settings(db, ctx.clinic_id)
    if s is not None:
        s.next_send_after = None
        await db.commit()
    return ApiResponse(
        data=QueueProcessResult(**await submission_queue.process_clinic(db, ctx.clinic_id))
    )


@router.get("/opposition/{patient_id}", response_model=ApiResponse[OppositionResponse])
async def get_opposition(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sistema_ts.opposition.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[OppositionResponse]:
    await _assert_in_clinic(db, Patient, patient_id, ctx.clinic_id)
    row = (
        await db.execute(
            select(SistemaTsPatientOpposition).where(
                SistemaTsPatientOpposition.clinic_id == ctx.clinic_id,
                SistemaTsPatientOpposition.patient_id == patient_id,
            )
        )
    ).scalar_one_or_none()
    return ApiResponse(
        data=OppositionResponse(
            patient_id=patient_id,
            opposed=bool(row and row.revoked_at is None),
            opposed_since=row.opposed_since if row else None,
            revoked_at=row.revoked_at if row else None,
            note=row.note if row else None,
        )
    )


@router.put("/opposition/{patient_id}", response_model=ApiResponse[OppositionResponse])
async def set_opposition(
    patient_id: UUID,
    data: OppositionUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sistema_ts.opposition.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[OppositionResponse]:
    """Record (or revoke) the patient's opposizione; accepted documents of
    the patient are re-sent as ``variazione`` with the new flag."""
    await _assert_in_clinic(db, Patient, patient_id, ctx.clinic_id)
    row = (
        await db.execute(
            select(SistemaTsPatientOpposition).where(
                SistemaTsPatientOpposition.clinic_id == ctx.clinic_id,
                SistemaTsPatientOpposition.patient_id == patient_id,
            )
        )
    ).scalar_one_or_none()
    today = datetime.now(UTC).date()
    if data.opposed:
        if row is None:
            row = SistemaTsPatientOpposition(
                clinic_id=ctx.clinic_id,
                patient_id=patient_id,
                opposed_since=today,
                recorded_by=ctx.user.id,
            )
            db.add(row)
        else:
            row.revoked_at = None
            row.opposed_since = row.opposed_since or today
        row.note = data.note
    elif row is not None and row.revoked_at is None:
        row.revoked_at = today
        row.note = data.note or row.note
    await db.flush()
    settings = await get_settings(db, ctx.clinic_id)
    if settings is not None and settings.enabled:
        try:
            await queue_variazioni_for_patient(db, settings, patient_id)
        except DocumentError:
            pass  # identity incomplete: the worker will report it in last_error
    await db.commit()
    return ApiResponse(
        data=OppositionResponse(
            patient_id=patient_id,
            opposed=bool(row and row.revoked_at is None),
            opposed_since=row.opposed_since if row else None,
            revoked_at=row.revoked_at if row else None,
            note=row.note if row else None,
        )
    )


@router.get("/item-types", response_model=ApiResponse[list[ItemTypeResponse]])
async def list_item_types(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sistema_ts.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[ItemTypeResponse]]:
    rows = (
        (
            await db.execute(
                select(SistemaTsItemType).where(SistemaTsItemType.clinic_id == ctx.clinic_id)
            )
        )
        .scalars()
        .all()
    )
    return ApiResponse(
        data=[
            ItemTypeResponse(
                catalog_item_id=r.catalog_item_id,
                tipo_spesa=r.tipo_spesa,
                flag_tipo_spesa=r.flag_tipo_spesa,
            )
            for r in rows
        ]
    )


@router.put("/item-types/{catalog_item_id}", response_model=ApiResponse[ItemTypeResponse])
async def set_item_type(
    catalog_item_id: UUID,
    data: ItemTypeUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sistema_ts.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ItemTypeResponse]:
    await _assert_in_clinic(db, TreatmentCatalogItem, catalog_item_id, ctx.clinic_id)
    row = (
        await db.execute(
            select(SistemaTsItemType).where(
                SistemaTsItemType.clinic_id == ctx.clinic_id,
                SistemaTsItemType.catalog_item_id == catalog_item_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = SistemaTsItemType(
            clinic_id=ctx.clinic_id, catalog_item_id=catalog_item_id, tipo_spesa=data.tipo_spesa
        )
        db.add(row)
    row.tipo_spesa = data.tipo_spesa
    row.flag_tipo_spesa = data.flag_tipo_spesa
    await db.commit()
    return ApiResponse(
        data=ItemTypeResponse(
            catalog_item_id=catalog_item_id,
            tipo_spesa=row.tipo_spesa,
            flag_tipo_spesa=row.flag_tipo_spesa,
        )
    )
