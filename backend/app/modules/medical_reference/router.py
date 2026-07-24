"""HTTP surface for medical_reference.

Mounted under ``/api/v1/medical_reference/*``. Three parallel sets of
routes (allergies/medications/diseases) — kept explicit per entity rather
than a single generic router, matching patients_clinical's own style, so
each has its own typed response model.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from .models import ReferenceAllergy, ReferenceDisease, ReferenceMedication
from .schemas import (
    ReferenceAllergyCreate,
    ReferenceAllergyResponse,
    ReferenceAllergyUpdate,
    ReferenceDiseaseCreate,
    ReferenceDiseaseResponse,
    ReferenceDiseaseUpdate,
    ReferenceMedicationCreate,
    ReferenceMedicationResponse,
    ReferenceMedicationUpdate,
)
from .service import MedicalReferenceService

router = APIRouter()


async def _get_or_404(db: AsyncSession, model, item_id: UUID):
    row = await MedicalReferenceService.get(db, model, item_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return row


# --- Allergies --------------------------------------------------------------


@router.get("/allergies", response_model=ApiResponse[list[ReferenceAllergyResponse]])
async def list_allergies(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=500, le=1000),
) -> ApiResponse[list[ReferenceAllergyResponse]]:
    rows = await MedicalReferenceService.search(
        db, ReferenceAllergy, ctx.clinic_id, q, active_only=not include_inactive, limit=limit
    )
    return ApiResponse(data=[ReferenceAllergyResponse.model_validate(r) for r in rows])


@router.post(
    "/allergies", response_model=ApiResponse[ReferenceAllergyResponse], status_code=status.HTTP_201_CREATED
)
async def create_allergy(
    data: ReferenceAllergyCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReferenceAllergyResponse]:
    row = await MedicalReferenceService.create(db, ReferenceAllergy, ctx.clinic_id, data.model_dump())
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=ReferenceAllergyResponse.model_validate(row))


@router.put("/allergies/{item_id}", response_model=ApiResponse[ReferenceAllergyResponse])
async def update_allergy(
    item_id: UUID,
    data: ReferenceAllergyUpdate,
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReferenceAllergyResponse]:
    row = await _get_or_404(db, ReferenceAllergy, item_id)
    row = await MedicalReferenceService.update(db, row, data.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=ReferenceAllergyResponse.model_validate(row))


@router.delete("/allergies/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_allergy(
    item_id: UUID,
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await _get_or_404(db, ReferenceAllergy, item_id)
    await MedicalReferenceService.deactivate(db, row)
    await db.commit()


# --- Medications ------------------------------------------------------------


@router.get("/medications", response_model=ApiResponse[list[ReferenceMedicationResponse]])
async def list_medications(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=500, le=1000),
) -> ApiResponse[list[ReferenceMedicationResponse]]:
    rows = await MedicalReferenceService.search(
        db, ReferenceMedication, ctx.clinic_id, q, active_only=not include_inactive, limit=limit
    )
    return ApiResponse(data=[ReferenceMedicationResponse.model_validate(r) for r in rows])


@router.post(
    "/medications",
    response_model=ApiResponse[ReferenceMedicationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_medication(
    data: ReferenceMedicationCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReferenceMedicationResponse]:
    row = await MedicalReferenceService.create(db, ReferenceMedication, ctx.clinic_id, data.model_dump())
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=ReferenceMedicationResponse.model_validate(row))


@router.put("/medications/{item_id}", response_model=ApiResponse[ReferenceMedicationResponse])
async def update_medication(
    item_id: UUID,
    data: ReferenceMedicationUpdate,
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReferenceMedicationResponse]:
    row = await _get_or_404(db, ReferenceMedication, item_id)
    row = await MedicalReferenceService.update(db, row, data.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=ReferenceMedicationResponse.model_validate(row))


@router.delete("/medications/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_medication(
    item_id: UUID,
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await _get_or_404(db, ReferenceMedication, item_id)
    await MedicalReferenceService.deactivate(db, row)
    await db.commit()


# --- Diseases -----------------------------------------------------------------


@router.get("/diseases", response_model=ApiResponse[list[ReferenceDiseaseResponse]])
async def list_diseases(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=500, le=1000),
) -> ApiResponse[list[ReferenceDiseaseResponse]]:
    rows = await MedicalReferenceService.search(
        db, ReferenceDisease, ctx.clinic_id, q, active_only=not include_inactive, limit=limit
    )
    return ApiResponse(data=[ReferenceDiseaseResponse.model_validate(r) for r in rows])


@router.post(
    "/diseases", response_model=ApiResponse[ReferenceDiseaseResponse], status_code=status.HTTP_201_CREATED
)
async def create_disease(
    data: ReferenceDiseaseCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReferenceDiseaseResponse]:
    row = await MedicalReferenceService.create(db, ReferenceDisease, ctx.clinic_id, data.model_dump())
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=ReferenceDiseaseResponse.model_validate(row))


@router.put("/diseases/{item_id}", response_model=ApiResponse[ReferenceDiseaseResponse])
async def update_disease(
    item_id: UUID,
    data: ReferenceDiseaseUpdate,
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReferenceDiseaseResponse]:
    row = await _get_or_404(db, ReferenceDisease, item_id)
    row = await MedicalReferenceService.update(db, row, data.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=ReferenceDiseaseResponse.model_validate(row))


@router.delete("/diseases/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_disease(
    item_id: UUID,
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await _get_or_404(db, ReferenceDisease, item_id)
    await MedicalReferenceService.deactivate(db, row)
    await db.commit()
