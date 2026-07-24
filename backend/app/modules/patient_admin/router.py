"""HTTP surface for patient_admin.

Mounted under ``/api/v1/patient_admin/*`` (module name has no
underscore/hyphen mismatch risk here — the frontend composable must use
this exact literal, per the lab_orders lesson).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db
from app.modules.patients.service import PatientService

from .schemas import (
    INVERSE_RELATIONSHIP_TYPE,
    PatientRelationshipCreate,
    PatientRelationshipResponse,
    PatientRelationshipUpdate,
)
from .service import PatientAdminService

router = APIRouter()


async def _ensure_patient(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> None:
    patient = await PatientService.get_patient(db, clinic_id, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")


# --- Relationships -------------------------------------------------------


@router.get(
    "/patients/{patient_id}/relationships",
    response_model=ApiResponse[list[PatientRelationshipResponse]],
)
async def list_relationships(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patient_admin.relationships.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[PatientRelationshipResponse]]:
    await _ensure_patient(db, ctx.clinic_id, patient_id)
    rows = await PatientAdminService.list_relationships_for_patient(db, ctx.clinic_id, patient_id)
    return ApiResponse(data=[PatientRelationshipResponse.model_validate(r) for r in rows])


@router.post(
    "/patients/{patient_id}/relationships",
    response_model=ApiResponse[PatientRelationshipResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_relationship(
    patient_id: UUID,
    data: PatientRelationshipCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patient_admin.relationships.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PatientRelationshipResponse]:
    await _ensure_patient(db, ctx.clinic_id, patient_id)
    row = await PatientAdminService.create_relationship(
        db, ctx.clinic_id, patient_id, data.model_dump()
    )
    await db.commit()
    await db.refresh(row)
    related = await PatientService.get_patient(db, ctx.clinic_id, row.related_patient_id)
    return ApiResponse(
        data=PatientRelationshipResponse(
            id=row.id,
            patient_id=row.patient_id,
            related_patient_id=row.related_patient_id,
            related_patient_name=related.full_name if related else "—",
            relationship_type=row.relationship_type,
            notes=row.notes,
            created_at=row.created_at,
        )
    )


@router.put(
    "/patients/{patient_id}/relationships/{relationship_id}",
    response_model=ApiResponse[PatientRelationshipResponse],
)
async def update_relationship(
    patient_id: UUID,
    relationship_id: UUID,
    data: PatientRelationshipUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patient_admin.relationships.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PatientRelationshipResponse]:
    await _ensure_patient(db, ctx.clinic_id, patient_id)
    row = await PatientAdminService.get_relationship(db, relationship_id)
    if row is None or patient_id not in (row.patient_id, row.related_patient_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    row = await PatientAdminService.update_relationship(
        db, row, data.model_dump(exclude_unset=True)
    )
    await db.commit()
    await db.refresh(row)
    other_id = row.related_patient_id if row.patient_id == patient_id else row.patient_id
    other = await PatientService.get_patient(db, ctx.clinic_id, other_id)
    label = (
        row.relationship_type
        if row.patient_id == patient_id
        else INVERSE_RELATIONSHIP_TYPE.get(row.relationship_type, row.relationship_type)
    )
    return ApiResponse(
        data=PatientRelationshipResponse(
            id=row.id,
            patient_id=patient_id,
            related_patient_id=other_id,
            related_patient_name=other.full_name if other else "—",
            relationship_type=label,
            notes=row.notes,
            created_at=row.created_at,
        )
    )


@router.delete(
    "/patients/{patient_id}/relationships/{relationship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_relationship(
    patient_id: UUID,
    relationship_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patient_admin.relationships.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _ensure_patient(db, ctx.clinic_id, patient_id)
    row = await PatientAdminService.get_relationship(db, relationship_id)
    if row is None or patient_id not in (row.patient_id, row.related_patient_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    await PatientAdminService.delete_relationship(db, row)
    await db.commit()
