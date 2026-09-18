"""HTTP surface for prescriptions.

Mounted under ``/api/v1/prescriptions/*``. Drafts mutate; issued rows
freeze (cancel + reissue instead). No DELETE route — prescriptions are
clinical-legal artifacts, never hard-deleted.
"""

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from .pdf import build_pdf_data, render_html, render_pdf_bytes
from .schemas import (
    PrescriberProfileResponse,
    PrescriberProfileUpsert,
    PrescribeWarnings,
    PrescriptionCreate,
    PrescriptionResponse,
    PrescriptionUpdate,
    TemplateCreate,
    TemplateResponse,
    TemplateUpdate,
)
from .service import PrescriptionService

router = APIRouter()


def _to_response(row, items) -> PrescriptionResponse:
    from .schemas import PrescriptionItemResponse

    return PrescriptionResponse(
        id=row.id,
        patient_id=row.patient_id,
        prescriber_id=row.prescriber_id,
        status=row.status,
        issued_at=row.issued_at,
        notes=row.notes,
        locale=row.locale,
        prescriber_name=row.prescriber_name,
        license_number=row.license_number,
        compliance_data=row.compliance_data,
        items=[PrescriptionItemResponse.model_validate(i) for i in items],
    )


async def _full_response(db, clinic_id, row) -> PrescriptionResponse:
    items = await PrescriptionService._items(db, clinic_id, row.id)
    return _to_response(row, items)


# --- Drafts ---------------------------------------------------------------


@router.get(
    "/patients/{patient_id}/prescriptions",
    response_model=ApiResponse[list[PrescriptionResponse]],
)
async def list_prescriptions(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[PrescriptionResponse]]:
    rows = await PrescriptionService.list_for_patient(db, ctx.clinic_id, patient_id)
    out = [await _full_response(db, ctx.clinic_id, r) for r in rows]
    return ApiResponse(data=out)


@router.post(
    "/patients/{patient_id}/prescriptions",
    response_model=ApiResponse[PrescriptionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_prescription(
    patient_id: UUID,
    data: PrescriptionCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PrescriptionResponse]:
    if data.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Body patient_id must match the path",
        )
    row = await PrescriptionService.create_draft(
        db,
        ctx.clinic_id,
        ctx.user_id,
        patient_id,
        notes=data.notes,
        locale=data.locale,
        items=[item.model_dump() for item in data.items],
    )
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=await _full_response(db, ctx.clinic_id, row))


@router.get(
    "/prescriptions/{prescription_id}",
    response_model=ApiResponse[PrescriptionResponse],
)
async def get_prescription(
    prescription_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PrescriptionResponse]:
    row = await PrescriptionService._get(db, ctx.clinic_id, prescription_id)
    return ApiResponse(data=await _full_response(db, ctx.clinic_id, row))


@router.patch(
    "/prescriptions/{prescription_id}",
    response_model=ApiResponse[PrescriptionResponse],
)
async def update_prescription(
    prescription_id: UUID,
    data: PrescriptionUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PrescriptionResponse]:
    payload = data.model_dump(exclude_unset=True)
    row = await PrescriptionService.update_draft(db, ctx.clinic_id, prescription_id, payload)
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=await _full_response(db, ctx.clinic_id, row))


# --- Issue / cancel ----------------------------------------------------------


@router.post(
    "/prescriptions/{prescription_id}/issue",
    response_model=ApiResponse[PrescriptionResponse],
)
async def issue_prescription(
    prescription_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.issue"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PrescriptionResponse]:
    row = await PrescriptionService.issue(db, ctx.clinic_id, prescription_id, ctx.user_id)
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=await _full_response(db, ctx.clinic_id, row))


@router.post(
    "/prescriptions/{prescription_id}/cancel",
    response_model=ApiResponse[PrescriptionResponse],
)
async def cancel_prescription(
    prescription_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.issue"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PrescriptionResponse]:
    row = await PrescriptionService.cancel(db, ctx.clinic_id, prescription_id)
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=await _full_response(db, ctx.clinic_id, row))


# --- PDF (download/print only, never email) ------------------------------------


@router.get("/prescriptions/{prescription_id}/pdf")
async def download_prescription_pdf(
    prescription_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    from app.modules.patients.service import PatientService

    row = await PrescriptionService._get(db, ctx.clinic_id, prescription_id)
    items = await PrescriptionService._items(db, ctx.clinic_id, row.id)
    patient = await PatientService.get_patient(db, ctx.clinic_id, row.patient_id)
    hook_data: dict = {}
    label_overrides: dict = {}
    hook = None
    try:
        from .hooks import resolve_hook_for_clinic

        hook = await resolve_hook_for_clinic(db, ctx.clinic_id)
        if hook is not None:
            label_overrides = hook.label_overrides()
            # Issue-time side effects must NOT re-run per download: read
            # the stored snapshot and let the hook enhance the payload.
            stored = (row.compliance_data or {}).get(hook.country_code)
            hook_data = stored if isinstance(stored, dict) else {}
    except ImportError:
        pass
    data = build_pdf_data(
        row,
        items,
        patient.full_name if patient else "?",
        {
            "name": ctx.clinic.name,
            "address": ctx.clinic.address if isinstance(ctx.clinic.address, dict) else {},
        },
        hook_data=hook_data,
        label_overrides=label_overrides,
        locale=row.locale or "es",
    )
    if hook is not None:
        data = hook.enhance_pdf_data(data, row) or data
    try:
        pdf = await asyncio.to_thread(render_pdf_bytes, data)
    except ImportError:
        return Response(content=render_html(data), media_type="text/html")
    return Response(content=pdf, media_type="application/pdf")


# --- Warnings (create-form banner, never blocking) -------------------------------


@router.get(
    "/patients/{patient_id}/prescribe-warnings",
    response_model=ApiResponse[PrescribeWarnings],
)
async def prescribe_warnings(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PrescribeWarnings]:
    warnings = await PrescriptionService.prescribe_warnings(db, ctx.clinic_id, patient_id)
    return ApiResponse(data=PrescribeWarnings(**warnings))


# --- Templates (Settings → Clinical) ----------------------------------------------


@router.get("/templates", response_model=ApiResponse[list[TemplateResponse]])
async def list_templates(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[TemplateResponse]]:
    rows = await PrescriptionService.list_templates(db, ctx.clinic_id)
    return ApiResponse(data=[TemplateResponse.model_validate(r) for r in rows])


@router.post(
    "/templates",
    response_model=ApiResponse[TemplateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    data: TemplateCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[TemplateResponse]:
    row = await PrescriptionService.create_template(
        db, ctx.clinic_id, data.name, [i.model_dump() for i in data.items]
    )
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=TemplateResponse.model_validate(row))


@router.patch("/templates/{template_id}", response_model=ApiResponse[TemplateResponse])
async def update_template(
    template_id: UUID,
    data: TemplateUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[TemplateResponse]:
    payload = data.model_dump(exclude_unset=True)
    row = await PrescriptionService.update_template(db, ctx.clinic_id, template_id, payload)
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=TemplateResponse.model_validate(row))


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await PrescriptionService.delete_template(db, ctx.clinic_id, template_id)
    await db.commit()


# --- Prescriber profile (own defaults) ----------------------------------------------


@router.get("/prescriber-profile", response_model=ApiResponse[PrescriberProfileResponse | None])
async def get_prescriber_profile(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PrescriberProfileResponse | None]:
    row = await PrescriptionService.get_prescriber_profile(db, ctx.clinic_id, ctx.user_id)
    return ApiResponse(data=PrescriberProfileResponse.model_validate(row) if row else None)


@router.put("/prescriber-profile", response_model=ApiResponse[PrescriberProfileResponse])
async def upsert_prescriber_profile(
    data: PrescriberProfileUpsert,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("prescriptions.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PrescriberProfileResponse]:
    row = await PrescriptionService.upsert_prescriber_profile(
        db, ctx.clinic_id, ctx.user_id, data.model_dump(exclude_unset=True)
    )
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=PrescriberProfileResponse.model_validate(row))
