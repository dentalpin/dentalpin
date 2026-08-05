"""Medications HTTP surface.

Mounted under ``/api/v1/medications/*`` by the module registry (it
applies the ``/api/v1/<manifest name>`` prefix externally, same as
patients) — this router intentionally has NO prefix of its own, and
collection routes use "" not "/" (matches patients/router.py exactly).
Permissions: ``medications.read`` / ``medications.write``.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .models import MedicationForm
from .schemas import MedicationCreate, MedicationResponse, MedicationUpdate
from .service import MedicationService

router = APIRouter()


@router.get("", response_model=PaginatedApiResponse[MedicationResponse])
async def list_medications(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medications.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    name: str | None = Query(default=None, max_length=255),
    form: MedicationForm | None = Query(default=None),
    is_prescribed: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=1000),
) -> PaginatedApiResponse[MedicationResponse]:
    medications, total = await MedicationService.list_medications(
        db,
        ctx.clinic_id,
        name=name,
        form=form,
        is_prescribed=is_prescribed,
        page=page,
        page_size=page_size,
    )
    return PaginatedApiResponse(
        data=[MedicationResponse.model_validate(m) for m in medications],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=ApiResponse[MedicationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_medication(
    data: MedicationCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medications.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[MedicationResponse]:
    medication = await MedicationService.create_medication(
        db, ctx.clinic_id, data.model_dump(exclude_unset=True)
    )
    return ApiResponse(data=MedicationResponse.model_validate(medication))


@router.get("/{medication_id}", response_model=ApiResponse[MedicationResponse])
async def get_medication(
    medication_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medications.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[MedicationResponse]:
    medication = await MedicationService.get_medication(db, ctx.clinic_id, medication_id)
    if not medication:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")
    return ApiResponse(data=MedicationResponse.model_validate(medication))


@router.put("/{medication_id}", response_model=ApiResponse[MedicationResponse])
async def update_medication(
    medication_id: UUID,
    data: MedicationUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medications.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[MedicationResponse]:
    medication = await MedicationService.get_medication(db, ctx.clinic_id, medication_id)
    if not medication:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")
    medication = await MedicationService.update_medication(
        db, medication, data.model_dump(exclude_unset=True)
    )
    return ApiResponse(data=MedicationResponse.model_validate(medication))


@router.delete("/{medication_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medication(
    medication_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medications.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    medication = await MedicationService.get_medication(db, ctx.clinic_id, medication_id)
    if not medication:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")
    await MedicationService.delete_medication(db, medication)
