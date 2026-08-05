"""HTTP surface for medical_reference.

Mounted under ``/api/v1/medical_reference/*``. Four parallel sets of
routes (allergies/medications/diseases/surgeries) — kept explicit per
entity rather than a single generic router, matching patients_clinical's
own style, so each has its own typed response model.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db
from app.modules.patients.service import PatientService

from .models import ReferenceAllergy, ReferenceDisease, ReferenceMedication, ReferenceSurgery
from .schemas import (
    PatientFlag,
    ReferenceAllergyCreate,
    ReferenceAllergyResponse,
    ReferenceAllergyUpdate,
    ReferenceContraindicationCreate,
    ReferenceContraindicationResponse,
    ReferenceContraindicationUpdate,
    ReferenceDiseaseCreate,
    ReferenceDiseaseResponse,
    ReferenceDiseaseUpdate,
    ReferenceInteractionCreate,
    ReferenceInteractionResponse,
    ReferenceInteractionUpdate,
    ReferenceMedicationCreate,
    ReferenceMedicationResponse,
    ReferenceMedicationUpdate,
    ReferenceSurgeryCreate,
    ReferenceSurgeryResponse,
    ReferenceSurgeryUpdate,
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


# --- Surgeries ----------------------------------------------------------------


@router.get("/surgeries", response_model=ApiResponse[list[ReferenceSurgeryResponse]])
async def list_surgeries(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=500, le=1000),
) -> ApiResponse[list[ReferenceSurgeryResponse]]:
    rows = await MedicalReferenceService.search(
        db, ReferenceSurgery, ctx.clinic_id, q, active_only=not include_inactive, limit=limit
    )
    return ApiResponse(data=[ReferenceSurgeryResponse.model_validate(r) for r in rows])


@router.post(
    "/surgeries",
    response_model=ApiResponse[ReferenceSurgeryResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_surgery(
    data: ReferenceSurgeryCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReferenceSurgeryResponse]:
    row = await MedicalReferenceService.create(db, ReferenceSurgery, ctx.clinic_id, data.model_dump())
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=ReferenceSurgeryResponse.model_validate(row))


@router.put("/surgeries/{item_id}", response_model=ApiResponse[ReferenceSurgeryResponse])
async def update_surgery(
    item_id: UUID,
    data: ReferenceSurgeryUpdate,
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReferenceSurgeryResponse]:
    row = await _get_or_404(db, ReferenceSurgery, item_id)
    row = await MedicalReferenceService.update(db, row, data.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=ReferenceSurgeryResponse.model_validate(row))


@router.delete("/surgeries/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_surgery(
    item_id: UUID,
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await _get_or_404(db, ReferenceSurgery, item_id)
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


# --- Interactions ---------------------------------------------------------------


@router.get("/interactions", response_model=ApiResponse[list[ReferenceInteractionResponse]])
async def list_interactions(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = Query(default=False),
) -> ApiResponse[list[ReferenceInteractionResponse]]:
    rows = await MedicalReferenceService.list_interactions(
        db, ctx.clinic_id, active_only=not include_inactive
    )
    return ApiResponse(data=[ReferenceInteractionResponse.model_validate(r) for r in rows])


@router.post(
    "/interactions",
    response_model=ApiResponse[ReferenceInteractionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_interaction(
    data: ReferenceInteractionCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReferenceInteractionResponse]:
    row = await MedicalReferenceService.create_interaction(db, ctx.clinic_id, data.model_dump())
    await db.commit()
    rows = await MedicalReferenceService.list_interactions(db, ctx.clinic_id)
    created = next(r for r in rows if r["id"] == row.id)
    return ApiResponse(data=ReferenceInteractionResponse.model_validate(created))


@router.put("/interactions/{item_id}", response_model=ApiResponse[ReferenceInteractionResponse])
async def update_interaction(
    item_id: UUID,
    data: ReferenceInteractionUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReferenceInteractionResponse]:
    row = await MedicalReferenceService.get_interaction(db, item_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    row = await MedicalReferenceService.update(db, row, data.model_dump(exclude_unset=True))
    await db.commit()
    rows = await MedicalReferenceService.list_interactions(db, ctx.clinic_id, active_only=False)
    updated = next(r for r in rows if r["id"] == row.id)
    return ApiResponse(data=ReferenceInteractionResponse.model_validate(updated))


@router.delete("/interactions/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_interaction(
    item_id: UUID,
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await MedicalReferenceService.get_interaction(db, item_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await MedicalReferenceService.deactivate(db, row)
    await db.commit()


# --- Contraindications -----------------------------------------------------------


@router.get(
    "/contraindications", response_model=ApiResponse[list[ReferenceContraindicationResponse]]
)
async def list_contraindications(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = Query(default=False),
) -> ApiResponse[list[ReferenceContraindicationResponse]]:
    rows = await MedicalReferenceService.list_contraindications(
        db, ctx.clinic_id, active_only=not include_inactive
    )
    return ApiResponse(data=[ReferenceContraindicationResponse.model_validate(r) for r in rows])


@router.post(
    "/contraindications",
    response_model=ApiResponse[ReferenceContraindicationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_contraindication(
    data: ReferenceContraindicationCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReferenceContraindicationResponse]:
    row = await MedicalReferenceService.create_contraindication(db, ctx.clinic_id, data.model_dump())
    await db.commit()
    rows = await MedicalReferenceService.list_contraindications(db, ctx.clinic_id)
    created = next(r for r in rows if r["id"] == row.id)
    return ApiResponse(data=ReferenceContraindicationResponse.model_validate(created))


@router.put(
    "/contraindications/{item_id}", response_model=ApiResponse[ReferenceContraindicationResponse]
)
async def update_contraindication(
    item_id: UUID,
    data: ReferenceContraindicationUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ReferenceContraindicationResponse]:
    row = await MedicalReferenceService.get_contraindication(db, item_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    row = await MedicalReferenceService.update(db, row, data.model_dump(exclude_unset=True))
    await db.commit()
    rows = await MedicalReferenceService.list_contraindications(db, ctx.clinic_id, active_only=False)
    updated = next(r for r in rows if r["id"] == row.id)
    return ApiResponse(data=ReferenceContraindicationResponse.model_validate(updated))


@router.delete("/contraindications/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_contraindication(
    item_id: UUID,
    _: Annotated[None, Depends(require_permission("medical_reference.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await MedicalReferenceService.get_contraindication(db, item_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await MedicalReferenceService.deactivate(db, row)
    await db.commit()


# --- Active per-patient flags ----------------------------------------------------


@router.get("/patients/{patient_id}/flags", response_model=ApiResponse[list[PatientFlag]])
async def get_patient_flags(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("medical_reference.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[PatientFlag]]:
    patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    flags = await MedicalReferenceService.get_patient_flags(db, ctx.clinic_id, patient_id)
    return ApiResponse(data=flags)
