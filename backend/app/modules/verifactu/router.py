"""Verifactu admin router.

Mounted at ``/api/v1/verifactu/`` by the module loader.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.models import Clinic
from app.core.auth.rbac import has_permission_for
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .models import (
    VerifactuCertificate,
    VerifactuRecord,
    VerifactuRecordAttempt,
    VerifactuSettings,
    VerifactuVatClassification,
)
from .schemas import (
    CertificateUploadResponse,
    NifCheckResponse,
    ProducerDefaultsResponse,
    ProducerInfoUpdate,
    VatClassificationItem,
    VatClassificationListResponse,
    VatClassificationUpdate,
    VerifactuCertificateResponse,
    VerifactuHealthResponse,
    VerifactuQueueItem,
    VerifactuRecordAttemptResponse,
    VerifactuRecordDetailResponse,
    VerifactuRecordResponse,
    VerifactuSettingsResponse,
    VerifactuSettingsUpdate,
)
from .services import certificate, encryption, iva_classifier, nif_validator, sistema_informatico

router = APIRouter()


# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------


async def _get_or_create_settings(db: AsyncSession, clinic_id) -> VerifactuSettings:
    result = await db.execute(
        select(VerifactuSettings).where(VerifactuSettings.clinic_id == clinic_id)
    )
    s = result.scalar_one_or_none()
    if s is None:
        s = VerifactuSettings(
            clinic_id=clinic_id,
            enabled=False,
            environment="test",
            numero_instalacion=str(uuid4()),
        )
        db.add(s)
        await db.flush()
    return s


async def _has_active_cert(db: AsyncSession, clinic_id) -> bool:
    result = await db.execute(
        select(VerifactuCertificate.id).where(
            VerifactuCertificate.clinic_id == clinic_id,
            VerifactuCertificate.is_active.is_(True),
        )
    )
    return result.first() is not None


async def _clinic_emisor(db: AsyncSession, clinic_id) -> tuple[str | None, str | None]:
    """Return ``(nif_emisor, nombre_razon_emisor)`` derived from the clinic.

    Verifactu uses ``clinic.tax_id`` as the issuer NIF and prefers the
    legal name (``legal_name``) over the commercial ``name`` for
    ``NombreRazonEmisor``. Both modules and the wizard read this through
    the same path, so the clinic stays the single source of truth.
    """

    result = await db.execute(
        select(Clinic.tax_id, Clinic.legal_name, Clinic.name).where(Clinic.id == clinic_id)
    )
    row = result.first()
    if row is None:
        return None, None
    tax_id, legal_name, name = row
    nif = (tax_id or "").strip().upper() or None
    razon = (legal_name or name or "").strip() or None
    return nif, razon


async def _build_settings_response(
    db: AsyncSession, settings: VerifactuSettings, clinic_id
) -> VerifactuSettingsResponse:
    nif, razon = await _clinic_emisor(db, clinic_id)
    payload = VerifactuSettingsResponse.model_validate(settings, from_attributes=True)
    return payload.model_copy(
        update={
            "nif_emisor": nif,
            "nombre_razon_emisor": razon,
            "has_active_certificate": await _has_active_cert(db, clinic_id),
        }
    )


@router.get("/settings", response_model=ApiResponse[VerifactuSettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VerifactuSettingsResponse]:
    s = await _get_or_create_settings(db, ctx.clinic_id)
    await db.commit()
    return ApiResponse(data=await _build_settings_response(db, s, ctx.clinic_id))


@router.put("/settings", response_model=ApiResponse[VerifactuSettingsResponse])
async def update_settings(
    body: VerifactuSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VerifactuSettingsResponse]:
    s = await _get_or_create_settings(db, ctx.clinic_id)
    if body.enabled is not None:
        s.enabled = body.enabled
    if body.environment is not None:
        # Promoting from ``test`` → ``prod`` is destructive: every
        # subsequent invoice becomes part of the clinic's official
        # AEAT fiscal ledger. Require an explicit
        # ``verifactu.environment.promote`` grant on top of the
        # general ``settings.configure`` permission.
        is_promoting_to_prod = body.environment == "prod" and s.environment != "prod"
        if is_promoting_to_prod and not await has_permission_for(
            db, ctx.clinic_id, ctx.role, "verifactu.environment.promote"
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "No tienes permiso para promover Verifactu a producción. "
                    "Pide al administrador de la clínica que realice este paso."
                ),
            )
        s.environment = body.environment

    nif, _ = await _clinic_emisor(db, ctx.clinic_id)

    if s.enabled and not nif:
        raise HTTPException(
            status_code=400,
            detail=(
                "Configura el CIF/NIF de la clínica en Configuración → "
                "Información de la clínica antes de activar Verifactu."
            ),
        )
    if s.enabled and (not s.producer_nif or not s.producer_name):
        raise HTTPException(
            status_code=400,
            detail=("Configura el productor del SIF en el asistente antes de activar Verifactu."),
        )
    if s.enabled and s.declaracion_responsable_signed_at is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Debes firmar la declaración responsable del productor antes de activar Verifactu."
            ),
        )
    if s.enabled and not await _has_active_cert(db, ctx.clinic_id):
        raise HTTPException(
            status_code=400,
            detail="Sube un certificado digital antes de activar Verifactu.",
        )

    # When Verifactu is active for this clinic, ensure
    # ``clinic.settings.country = 'ES'`` so the billing hook registry
    # routes invoices through the Verifactu compliance pipeline. The
    # field is the single source of truth used by
    # ``BillingHookRegistry.get_for_clinic``.
    if s.enabled:
        clinic_q = await db.execute(select(Clinic).where(Clinic.id == ctx.clinic_id))
        clinic = clinic_q.scalar_one_or_none()
        if clinic is not None:
            current_settings = dict(clinic.settings or {})
            if current_settings.get("country") != "ES":
                current_settings["country"] = "ES"
                clinic.settings = current_settings

    await db.commit()
    await db.refresh(s)
    return ApiResponse(data=await _build_settings_response(db, s, ctx.clinic_id))


# ----------------------------------------------------------------------------
# Producer (SIF) wizard
# ----------------------------------------------------------------------------


@router.get("/producer/defaults", response_model=ApiResponse[ProducerDefaultsResponse])
async def get_producer_defaults(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.read"))],
) -> ApiResponse[ProducerDefaultsResponse]:
    """Return env-var defaults the wizard should prefill in the form."""

    return ApiResponse(data=ProducerDefaultsResponse(**sistema_informatico.producer_defaults()))


@router.put("/producer", response_model=ApiResponse[VerifactuSettingsResponse])
async def update_producer(
    body: ProducerInfoUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VerifactuSettingsResponse]:
    """Set the SIF producer for this clinic and (optionally) sign the
    declaración responsable.

    The signature timestamp + user are recorded so we can prove who and
    when in case of an AEAT inspection. We do not generate the PDF here
    — the frontend renders and exports it from the rendered fields.
    """

    from datetime import UTC, datetime

    s = await _get_or_create_settings(db, ctx.clinic_id)
    s.producer_nif = body.producer_nif.strip().upper()
    s.producer_name = body.producer_name.strip()
    s.producer_id_sistema = body.producer_id_sistema.strip().upper()
    s.producer_version = body.producer_version.strip()

    if body.sign_declaracion and s.declaracion_responsable_signed_at is None:
        s.declaracion_responsable_signed_at = datetime.now(UTC)
        s.declaracion_responsable_signed_by = ctx.user_id

    await db.commit()
    await db.refresh(s)
    return ApiResponse(data=await _build_settings_response(db, s, ctx.clinic_id))


@router.delete("/producer/declaracion", response_model=ApiResponse[VerifactuSettingsResponse])
async def revoke_producer_declaracion(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VerifactuSettingsResponse]:
    """Revoke the signed declaración responsable so the producer fields
    can be edited again.

    Side effects:

    * Clears ``declaracion_responsable_signed_at`` /
      ``declaracion_responsable_signed_by``.
    * Forces ``enabled=False`` — Verifactu cannot run without an active
      signature, so we lock submissions until the user re-signs.

    The previously-signed declaration loses legal value once revoked.
    The action is auditable through the user record and the timestamp
    of any new signature that follows.
    """

    s = await _get_or_create_settings(db, ctx.clinic_id)
    s.declaracion_responsable_signed_at = None
    s.declaracion_responsable_signed_by = None
    s.enabled = False
    await db.commit()
    await db.refresh(s)
    return ApiResponse(data=await _build_settings_response(db, s, ctx.clinic_id))


# ----------------------------------------------------------------------------
# Certificate
# ----------------------------------------------------------------------------


@router.post("/certificate", response_model=ApiResponse[CertificateUploadResponse])
async def upload_certificate(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(description="Archivo .pfx / .p12")],
    password: Annotated[str, Form(description="Contraseña del PFX")],
) -> ApiResponse[CertificateUploadResponse]:
    pfx_bytes = await file.read()
    if not pfx_bytes:
        raise HTTPException(status_code=400, detail="Archivo vacío")

    try:
        info = certificate.parse_and_validate(pfx_bytes, password)
    except certificate.CertificateError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Deactivate any prior active cert.
    await db.execute(
        update(VerifactuCertificate)
        .where(
            VerifactuCertificate.clinic_id == ctx.clinic_id,
            VerifactuCertificate.is_active.is_(True),
        )
        .values(is_active=False)
    )

    cert = VerifactuCertificate(
        clinic_id=ctx.clinic_id,
        pfx_encrypted=encryption.encrypt_bytes(pfx_bytes),
        password_encrypted=encryption.encrypt_password(password),
        subject_cn=info.subject_cn,
        issuer_cn=info.issuer_cn,
        nif_titular=info.nif_titular,
        valid_from=info.valid_from,
        valid_until=info.valid_until,
        is_active=True,
        uploaded_by=ctx.user_id,
    )
    db.add(cert)
    await db.commit()
    await db.refresh(cert)

    return ApiResponse(
        data=CertificateUploadResponse(
            id=cert.id,
            subject_cn=cert.subject_cn,
            issuer_cn=cert.issuer_cn,
            nif_titular=cert.nif_titular,
            valid_from=cert.valid_from,
            valid_until=cert.valid_until,
            is_active=cert.is_active,
        )
    )


@router.get("/certificate", response_model=ApiResponse[VerifactuCertificateResponse | None])
async def get_active_certificate(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VerifactuCertificateResponse | None]:
    result = await db.execute(
        select(VerifactuCertificate).where(
            VerifactuCertificate.clinic_id == ctx.clinic_id,
            VerifactuCertificate.is_active.is_(True),
        )
    )
    cert = result.scalar_one_or_none()
    return ApiResponse(data=VerifactuCertificateResponse.model_validate(cert) if cert else None)


@router.get(
    "/certificate/history",
    response_model=ApiResponse[list[VerifactuCertificateResponse]],
)
async def list_certificate_history(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[VerifactuCertificateResponse]]:
    result = await db.execute(
        select(VerifactuCertificate)
        .where(VerifactuCertificate.clinic_id == ctx.clinic_id)
        .order_by(VerifactuCertificate.created_at.desc())
    )
    return ApiResponse(
        data=[VerifactuCertificateResponse.model_validate(c) for c in result.scalars()]
    )


@router.delete("/certificate/{cert_id}", response_model=ApiResponse[None])
async def deactivate_certificate(
    cert_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[None]:
    await db.execute(
        update(VerifactuCertificate)
        .where(
            VerifactuCertificate.id == cert_id,
            VerifactuCertificate.clinic_id == ctx.clinic_id,
        )
        .values(is_active=False)
    )
    await db.commit()
    return ApiResponse(data=None)


# ----------------------------------------------------------------------------
# Records (libro fiscal)
# ----------------------------------------------------------------------------


@router.get("/records", response_model=PaginatedApiResponse[VerifactuRecordResponse])
async def list_records(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.records.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    state: str | None = None,
    tipo_factura: str | None = None,
    invoice_id: UUID | None = None,
) -> PaginatedApiResponse[VerifactuRecordResponse]:
    conditions = [VerifactuRecord.clinic_id == ctx.clinic_id]
    if state:
        conditions.append(VerifactuRecord.state == state)
    if tipo_factura:
        conditions.append(VerifactuRecord.tipo_factura == tipo_factura)
    if invoice_id:
        conditions.append(VerifactuRecord.invoice_id == invoice_id)

    total_q = await db.execute(select(func.count(VerifactuRecord.id)).where(*conditions))
    total = total_q.scalar_one()

    rows = await db.execute(
        select(VerifactuRecord)
        .where(*conditions)
        .order_by(VerifactuRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return PaginatedApiResponse(
        data=[VerifactuRecordResponse.model_validate(r) for r in rows.scalars()],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/records/{record_id}", response_model=ApiResponse[VerifactuRecordDetailResponse])
async def get_record(
    record_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.records.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VerifactuRecordDetailResponse]:
    result = await db.execute(
        select(VerifactuRecord).where(
            VerifactuRecord.id == record_id,
            VerifactuRecord.clinic_id == ctx.clinic_id,
        )
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(status_code=404)
    return ApiResponse(data=VerifactuRecordDetailResponse.model_validate(rec))


@router.get("/records/{record_id}/xml", response_class=PlainTextResponse)
async def get_record_xml(
    record_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.records.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> str:
    result = await db.execute(
        select(VerifactuRecord.xml_payload).where(
            VerifactuRecord.id == record_id,
            VerifactuRecord.clinic_id == ctx.clinic_id,
        )
    )
    xml = result.scalar_one_or_none()
    if xml is None:
        raise HTTPException(status_code=404)
    return xml


# ----------------------------------------------------------------------------
# Queue
# ----------------------------------------------------------------------------


@router.get("/queue", response_model=ApiResponse[list[VerifactuQueueItem]])
async def list_queue(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.queue.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    state: str | None = Query(
        default=None, pattern=r"^(pending|sending|rejected|failed_transient|failed_validation)?$"
    ),
) -> ApiResponse[list[VerifactuQueueItem]]:
    base = select(VerifactuRecord).where(VerifactuRecord.clinic_id == ctx.clinic_id)
    if state:
        base = base.where(VerifactuRecord.state == state)
    else:
        base = base.where(
            VerifactuRecord.state.in_(
                ("pending", "sending", "rejected", "failed_transient", "failed_validation")
            )
        )
    base = base.order_by(VerifactuRecord.created_at.desc()).limit(500)
    rows = await db.execute(base)
    from .services.error_messages import friendly_error

    items: list[VerifactuQueueItem] = []
    for r in rows.scalars():
        friendly = friendly_error(r.aeat_codigo_error, r.aeat_descripcion_error)
        item = VerifactuQueueItem.model_validate(r)
        item = item.model_copy(
            update={
                "aeat_descripcion_error_es": friendly["message"],
                "aeat_error_field": friendly["field"],
                "aeat_error_cta": friendly["suggested_cta"],
            }
        )
        items.append(item)
    return ApiResponse(data=items)


@router.post("/queue/{record_id}/retry", response_model=ApiResponse[VerifactuRecordResponse])
async def retry_record(
    record_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.queue.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    regenerate: Annotated[bool, Query(description="Re-render XML from current data")] = True,
) -> ApiResponse[VerifactuRecordResponse]:
    """Retry a queued Verifactu record.

    Default behaviour (``regenerate=true``) for ``rejected`` /
    ``failed_validation`` records: re-render the XML and recompute the
    huella from current Clinic + Invoice + Settings, then re-queue as
    Subsanación. Use ``regenerate=false`` for debug to send the stored
    XML verbatim — sometimes useful when the rejection was actually a
    transient AEAT issue mis-coded as ``Incorrecto``.

    For ``failed_transient`` records the XML is always reused — the
    rejection was at the transport layer, not a data problem.
    """

    result = await db.execute(
        select(VerifactuRecord).where(
            VerifactuRecord.id == record_id,
            VerifactuRecord.clinic_id == ctx.clinic_id,
        )
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(status_code=404)
    if rec.state == "accepted":
        raise HTTPException(status_code=400, detail="Registro ya aceptado")

    code = rec.aeat_codigo_error or 0
    is_business_transient = rec.state == "failed_transient" and (code == -2 or code >= 1000)
    is_regenable = rec.state in ("rejected", "failed_validation") or is_business_transient
    if regenerate and is_regenable:
        from .hook import regenerate_record

        try:
            rec = await regenerate_record(db, rec)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        await db.commit()
        await db.refresh(rec)
    else:
        rec.state = "pending"
        rec.subsanacion = True
        if rec.aeat_estado_registro == "Incorrecto":
            rec.rechazo_previo = True
        await db.commit()
        await db.refresh(rec)
    return ApiResponse(data=VerifactuRecordResponse.model_validate(rec))


@router.post("/queue/retry-all", response_model=ApiResponse[dict])
async def retry_all_rejected(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.queue.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    """Bulk-regenerate every ``rejected`` record for the current clinic.

    Use case: clinic activated Verifactu with a mistyped NIF and 50
    invoices got rejected at once. Admin fixes the NIF in clinic
    settings then triggers this endpoint to re-queue them all in one
    click. Capped at 200 records per call to bound the transaction.
    """

    from .hook import regenerate_record

    rows_q = await db.execute(
        select(VerifactuRecord)
        .where(
            VerifactuRecord.clinic_id == ctx.clinic_id,
            VerifactuRecord.state.in_(("rejected", "failed_validation")),
        )
        .order_by(VerifactuRecord.created_at.asc())
        .limit(200)
    )
    rows = list(rows_q.scalars())
    regenerated = 0
    failed: list[dict] = []
    for rec in rows:
        try:
            await regenerate_record(db, rec)
            regenerated += 1
        except ValueError as exc:
            failed.append({"record_id": str(rec.id), "error": str(exc)})
    await db.commit()
    return ApiResponse(
        data={
            "regenerated": regenerated,
            "failed": failed,
            "remaining": max(0, len(rows) - regenerated),
        }
    )


@router.get(
    "/records/{record_id}/attempts",
    response_model=ApiResponse[list[VerifactuRecordAttemptResponse]],
)
async def list_record_attempts(
    record_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.records.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[VerifactuRecordAttemptResponse]]:
    """Historical attempts (XMLs + huellas) for a record (art. 8 RD 1007/2023)."""

    rec_q = await db.execute(
        select(VerifactuRecord.id).where(
            VerifactuRecord.id == record_id,
            VerifactuRecord.clinic_id == ctx.clinic_id,
        )
    )
    if rec_q.scalar_one_or_none() is None:
        raise HTTPException(status_code=404)

    attempts_q = await db.execute(
        select(VerifactuRecordAttempt)
        .where(VerifactuRecordAttempt.record_id == record_id)
        .order_by(VerifactuRecordAttempt.attempt_no.asc())
    )
    return ApiResponse(
        data=[VerifactuRecordAttemptResponse.model_validate(a) for a in attempts_q.scalars()]
    )


@router.get("/nif-check", response_model=ApiResponse[NifCheckResponse])
async def check_nif(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.read"))],
    value: Annotated[str, Query(description="NIF/CIF to validate")],
) -> ApiResponse[NifCheckResponse]:
    """On-blur NIF check used by the frontend.

    Returns ``is_valid=False`` plus a Spanish warning when the value
    does not pass mod-23 validation. Advisory only — neither blocks
    saving nor invoice issuing.
    """

    return ApiResponse(
        data=NifCheckResponse(
            is_valid=nif_validator.is_valid_spanish_nif(value),
            warning=nif_validator.nif_warning(value),
        )
    )


@router.post("/queue/process-now", response_model=ApiResponse[dict])
async def process_now(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.queue.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    from .services.submission_queue import process_clinic

    count = await process_clinic(db, ctx.clinic_id)
    return ApiResponse(data={"processed": count})


# ----------------------------------------------------------------------------
# Health
# ----------------------------------------------------------------------------


@router.get("/health", response_model=ApiResponse[VerifactuHealthResponse])
async def health(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VerifactuHealthResponse]:
    s = await _get_or_create_settings(db, ctx.clinic_id)
    cert = await db.execute(
        select(VerifactuCertificate).where(
            VerifactuCertificate.clinic_id == ctx.clinic_id,
            VerifactuCertificate.is_active.is_(True),
        )
    )
    active_cert = cert.scalar_one_or_none()

    pending_q = await db.execute(
        select(func.count()).where(
            VerifactuRecord.clinic_id == ctx.clinic_id,
            VerifactuRecord.state.in_(("pending", "sending", "failed_transient")),
        )
    )
    rejected_q = await db.execute(
        select(func.count()).where(
            VerifactuRecord.clinic_id == ctx.clinic_id,
            VerifactuRecord.state == "rejected",
        )
    )

    await db.commit()
    return ApiResponse(
        data=VerifactuHealthResponse(
            enabled=s.enabled,
            environment=s.environment,
            has_certificate=active_cert is not None,
            certificate_valid_until=active_cert.valid_until if active_cert else None,
            last_aeat_response_at=s.last_aeat_response_at,
            next_send_after=s.next_send_after,
            pending_count=pending_q.scalar_one(),
            rejected_count=rejected_q.scalar_one(),
        )
    )


# ----------------------------------------------------------------------------
# VAT mapping (clasificación AEAT por tipo de IVA)
# ----------------------------------------------------------------------------


def _infer_classification(rate: float) -> tuple[str, str | None]:
    """Heuristic-derived AEAT classification used when no override exists.

    Mirrors :func:`services.iva_classifier.classify` for the rate-only
    case: positive rate → ``S1``; zero rate → ``N1``. Exempt (E1)
    requires explicit user choice via the override since the catalog
    schema doesn't carry the legal cause.
    """

    rate_d = Decimal(str(rate or 0))
    try:
        cls = iva_classifier.classify(vat_rate=rate_d, is_exento_sanitario=False)
    except ValueError:
        return "S1", None
    return cls.calificacion_operacion or "EXENTO", cls.causa_exencion


@router.get(
    "/vat-mapping",
    response_model=ApiResponse[VatClassificationListResponse],
)
async def list_vat_mapping(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VatClassificationListResponse]:
    """Return every VAT type for the clinic with its current AEAT mapping."""

    from app.modules.catalog.models import VatType

    vat_q = await db.execute(
        select(VatType)
        .where(VatType.clinic_id == ctx.clinic_id, VatType.is_active.is_(True))
        .order_by(VatType.rate.desc())
    )
    vat_types = list(vat_q.scalars())

    overrides_q = await db.execute(
        select(VerifactuVatClassification).where(
            VerifactuVatClassification.clinic_id == ctx.clinic_id
        )
    )
    overrides = {row.vat_type_id: row for row in overrides_q.scalars()}

    items: list[VatClassificationItem] = []
    for vt in vat_types:
        inferred, inferred_cause = _infer_classification(vt.rate)
        ov = overrides.get(vt.id)
        label = (vt.names or {}).get("es") or (vt.names or {}).get("en") or "?"
        items.append(
            VatClassificationItem(
                vat_type_id=vt.id,
                label=label,
                rate=Decimal(str(vt.rate or 0)),
                is_default=bool(vt.is_default),
                inferred_classification=inferred,
                inferred_exemption_cause=inferred_cause,
                override_classification=ov.classification if ov else None,
                override_exemption_cause=ov.exemption_cause if ov else None,
                override_notes=ov.notes if ov else None,
            )
        )

    return ApiResponse(data=VatClassificationListResponse(items=items))


@router.put(
    "/vat-mapping/{vat_type_id}",
    response_model=ApiResponse[VatClassificationItem],
)
async def upsert_vat_mapping(
    vat_type_id: UUID,
    body: VatClassificationUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("verifactu.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VatClassificationItem]:
    """Set or clear the AEAT classification override for a VAT type."""

    from app.modules.catalog.models import VatType

    # Validate the vat_type belongs to this clinic.
    vt_q = await db.execute(
        select(VatType).where(VatType.id == vat_type_id, VatType.clinic_id == ctx.clinic_id)
    )
    vt = vt_q.scalar_one_or_none()
    if vt is None:
        raise HTTPException(status_code=404, detail="vat_type no encontrado")

    existing_q = await db.execute(
        select(VerifactuVatClassification).where(
            VerifactuVatClassification.clinic_id == ctx.clinic_id,
            VerifactuVatClassification.vat_type_id == vat_type_id,
        )
    )
    existing = existing_q.scalar_one_or_none()

    if body.classification is None:
        # Clear the override — fall back to heuristic.
        if existing is not None:
            await db.delete(existing)
        await db.commit()
    else:
        if existing is None:
            existing = VerifactuVatClassification(
                clinic_id=ctx.clinic_id,
                vat_type_id=vat_type_id,
                classification=body.classification,
                exemption_cause=body.exemption_cause
                if body.classification.startswith("E")
                else None,
                notes=body.notes,
            )
            db.add(existing)
        else:
            existing.classification = body.classification
            existing.exemption_cause = (
                body.exemption_cause if body.classification.startswith("E") else None
            )
            existing.notes = body.notes
        await db.commit()

    inferred, inferred_cause = _infer_classification(vt.rate)
    label = (vt.names or {}).get("es") or (vt.names or {}).get("en") or "?"
    return ApiResponse(
        data=VatClassificationItem(
            vat_type_id=vt.id,
            label=label,
            rate=Decimal(str(vt.rate or 0)),
            is_default=bool(vt.is_default),
            inferred_classification=inferred,
            inferred_exemption_cause=inferred_cause,
            override_classification=body.classification,
            override_exemption_cause=body.exemption_cause
            if body.classification and body.classification.startswith("E")
            else None,
            override_notes=body.notes,
        )
    )
