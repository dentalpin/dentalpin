"""Patient HTTP surface.

Mounts under ``/api/v1/patients/*``. Permissions live in the
``patients.*`` namespace: ``patients.read`` and ``patients.write``.

Medical history, emergency contact, legal guardian and alerts live in
the ``patients_clinical`` module after Fase B.4.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .csv_import import CsvImportError, import_patients, validate_patient_csv
from .schemas import (
    PatientCreate,
    PatientExtendedResponse,
    PatientExtendedUpdate,
    PatientImportReport,
    PatientResponse,
    PatientUpdate,
)
from .service import PatientService

router = APIRouter()


@router.get("/recent", response_model=ApiResponse[list[PatientResponse]])
async def get_recent_patients(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patients.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=8, ge=1, le=20),
) -> ApiResponse[list[PatientResponse]]:
    """Get recent patients (by last visit or creation date)."""
    patients = await PatientService.get_recent_patients(db, ctx.clinic_id, limit)
    return ApiResponse(data=[PatientResponse.model_validate(p) for p in patients])


@router.get("", response_model=PaginatedApiResponse[PatientResponse])
async def list_patients(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patients.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    patient_ids: list[UUID] | None = Query(default=None),
    city: str | None = Query(default=None, max_length=100),
    do_not_contact: bool | None = Query(default=None),
    include_archived: bool = Query(default=False),
    sort: str | None = Query(default=None, max_length=50),
) -> PaginatedApiResponse[PatientResponse]:
    """List patients with optional search + filters.

    ``patient_ids`` is the intersection vector used by cross-module
    filters such as "with debt > 0" (resolved server-side by the
    payments module, then passed in here).
    """
    patients, total = await PatientService.list_patients(
        db,
        ctx.clinic_id,
        search,
        page,
        page_size,
        patient_ids=patient_ids,
        city=city,
        do_not_contact=do_not_contact,
        include_archived=include_archived,
        sort=sort,
    )
    return PaginatedApiResponse(
        data=[PatientResponse.model_validate(p) for p in patients],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=ApiResponse[PatientResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_patient(
    data: PatientCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patients.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PatientResponse]:
    """Create a new patient."""
    patient = await PatientService.create_patient(
        db, ctx.clinic_id, data.model_dump(exclude_unset=True)
    )
    return ApiResponse(data=PatientResponse.model_validate(patient))


@router.post(
    "/import.csv",
    response_model=ApiResponse[PatientImportReport],
    status_code=status.HTTP_200_OK,
)
async def import_patients_csv(
    file: Annotated[UploadFile, File()],
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patients.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    dry_run: bool = Query(default=True),
) -> ApiResponse[PatientImportReport]:
    """Import patients from CSV. Dry-run (default) validates only; with
    ``dry_run=false`` valid rows are created and per-row events fire."""
    content = await file.read()
    try:
        valid, errors, total = validate_patient_csv(content)
    except CsvImportError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    created = 0
    if not dry_run and valid:
        patients = await import_patients(db, ctx.clinic_id, valid)
        created = len(patients)
    return ApiResponse(
        data=PatientImportReport(total=total, valid=len(valid), created=created, errors=errors)
    )


@router.get("/{patient_id}", response_model=ApiResponse[PatientResponse])
async def get_patient(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patients.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PatientResponse]:
    """Get a patient by ID."""
    patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return ApiResponse(data=PatientResponse.model_validate(patient))


@router.put("/{patient_id}", response_model=ApiResponse[PatientResponse])
async def update_patient(
    patient_id: UUID,
    data: PatientUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patients.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PatientResponse]:
    """Update a patient."""
    patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    patient = await PatientService.update_patient(db, patient, data.model_dump(exclude_unset=True))
    return ApiResponse(data=PatientResponse.model_validate(patient))


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patients.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft delete (archive) a patient."""
    patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    await PatientService.archive_patient(db, patient)


# --- Extended info ------------------------------------------------------


@router.get("/{patient_id}/extended", response_model=ApiResponse[PatientExtendedResponse])
async def get_patient_extended(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patients.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PatientExtendedResponse]:
    """Get patient with extended identity/demographics info."""
    patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return ApiResponse(data=PatientExtendedResponse.model_validate(patient))


@router.put("/{patient_id}/extended", response_model=ApiResponse[PatientExtendedResponse])
async def update_patient_extended(
    patient_id: UUID,
    data: PatientExtendedUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patients.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PatientExtendedResponse]:
    """Update patient with extended demographic fields."""
    patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    patient = await PatientService.update_patient(db, patient, data.model_dump(exclude_unset=True))
    return ApiResponse(data=PatientExtendedResponse.model_validate(patient))
