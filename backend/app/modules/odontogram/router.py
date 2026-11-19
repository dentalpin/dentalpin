"""FastAPI router for odontogram module."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.patient_access import RecordPatientAccess
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db
from app.modules.patients.models import Patient

from .constants import CONDITION_COLORS, SURFACES, ToothCondition, is_valid_tooth_number
from .schemas import (
    BulkUpdateRequest,
    HistoricalOdontogramResponse,
    HistoricalToothRecordResponse,
    HistoricalTreatmentResponse,
    HistoryEntryWithUser,
    OdontogramResponse,
    TimelineDateEntry,
    TimelineResponse,
    ToothRecordResponse,
    ToothRecordUpdate,
    ToothRecordWithTreatmentsResponse,
    TreatmentCreate,
    TreatmentPerform,
    TreatmentResponse,
    TreatmentUpdate,
)
from .service import (
    OdontogramService,
    TreatmentAlreadyPerformedError,
    TreatmentService,
    build_treatment_response,
)

router = APIRouter()


async def validate_patient_access(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> Patient:
    from sqlalchemy import select

    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == clinic_id,
            Patient.status != "archived",
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


# ============================================================================
# Tooth record endpoints
# ============================================================================


@router.get(
    "/patients/{patient_id}/odontogram",
    response_model=ApiResponse[OdontogramResponse],
)
async def get_odontogram(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    record_access: RecordPatientAccess,
) -> ApiResponse[OdontogramResponse]:
    await validate_patient_access(db, ctx.clinic_id, patient_id)
    teeth = await OdontogramService.get_patient_odontogram(db, ctx.clinic_id, patient_id)
    treatments, _total = await TreatmentService.list_patient_treatments(
        db=db, clinic_id=ctx.clinic_id, patient_id=patient_id, page=1, page_size=500
    )
    response = OdontogramResponse(
        patient_id=patient_id,
        teeth=[ToothRecordResponse.model_validate(t) for t in teeth],
        treatments=[
            TreatmentResponse.model_validate(build_treatment_response(t)) for t in treatments
        ],
        condition_colors=CONDITION_COLORS,
        available_conditions=[c.value for c in ToothCondition],
        surfaces=SURFACES,
    )
    await record_access(patient_id, "odontogram")
    return ApiResponse(data=response)


@router.get(
    "/patients/{patient_id}/teeth/{tooth_number}",
    response_model=ApiResponse[ToothRecordResponse],
)
async def get_tooth(
    patient_id: UUID,
    tooth_number: int,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    record_access: RecordPatientAccess,
) -> ApiResponse[ToothRecordResponse]:
    await validate_patient_access(db, ctx.clinic_id, patient_id)
    if not is_valid_tooth_number(tooth_number):
        raise HTTPException(status_code=400, detail=f"Invalid tooth number: {tooth_number}")
    tooth = await OdontogramService.get_tooth_record(db, ctx.clinic_id, patient_id, tooth_number)
    if not tooth:
        raise HTTPException(
            status_code=404, detail=f"Tooth {tooth_number} not found for this patient"
        )
    await record_access(patient_id, "odontogram")
    return ApiResponse(data=ToothRecordResponse.model_validate(tooth))


@router.put(
    "/patients/{patient_id}/teeth/{tooth_number}",
    response_model=ApiResponse[ToothRecordResponse],
)
async def create_or_update_tooth(
    patient_id: UUID,
    tooth_number: int,
    data: ToothRecordUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ToothRecordResponse]:
    await validate_patient_access(db, ctx.clinic_id, patient_id)
    if not is_valid_tooth_number(tooth_number):
        raise HTTPException(status_code=400, detail=f"Invalid tooth number: {tooth_number}")
    surface_updates = None
    if data.surface_updates:
        surface_updates = [u.model_dump() for u in data.surface_updates]
    tooth = await OdontogramService.create_or_update_tooth(
        db=db,
        clinic_id=ctx.clinic_id,
        patient_id=patient_id,
        tooth_number=tooth_number,
        user_id=ctx.user_id,
        general_condition=data.general_condition,
        surface_updates=surface_updates,
        notes=data.notes,
        is_displaced=data.is_displaced,
        is_rotated=data.is_rotated,
        displacement_notes=data.displacement_notes,
    )
    return ApiResponse(data=ToothRecordResponse.model_validate(tooth))


@router.patch(
    "/patients/{patient_id}/teeth/bulk",
    response_model=ApiResponse[list[ToothRecordResponse]],
)
async def bulk_update_teeth(
    patient_id: UUID,
    data: BulkUpdateRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[ToothRecordResponse]]:
    await validate_patient_access(db, ctx.clinic_id, patient_id)
    for u in data.updates:
        if not is_valid_tooth_number(u.tooth_number):
            raise HTTPException(status_code=400, detail=f"Invalid tooth number: {u.tooth_number}")
    updates = []
    for u in data.updates:
        d = {
            "tooth_number": u.tooth_number,
            "general_condition": u.general_condition,
            "notes": u.notes,
        }
        if u.surface_updates:
            d["surface_updates"] = [s.model_dump() for s in u.surface_updates]
        updates.append(d)
    teeth = await OdontogramService.bulk_update_teeth(
        db=db,
        clinic_id=ctx.clinic_id,
        patient_id=patient_id,
        user_id=ctx.user_id,
        updates=updates,
    )
    return ApiResponse(data=[ToothRecordResponse.model_validate(t) for t in teeth])


@router.patch(
    "/patients/{patient_id}/teeth/{tooth_number}",
    response_model=ApiResponse[ToothRecordResponse],
)
async def partial_update_tooth(
    patient_id: UUID,
    tooth_number: int,
    data: ToothRecordUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ToothRecordResponse]:
    return await create_or_update_tooth(patient_id, tooth_number, data, ctx, _, db)


@router.get(
    "/patients/{patient_id}/teeth/{tooth_number}/history",
    response_model=PaginatedApiResponse[HistoryEntryWithUser],
)
async def get_tooth_history(
    patient_id: UUID,
    tooth_number: int,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    record_access: RecordPatientAccess,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedApiResponse[HistoryEntryWithUser]:
    await validate_patient_access(db, ctx.clinic_id, patient_id)
    if not is_valid_tooth_number(tooth_number):
        raise HTTPException(status_code=400, detail=f"Invalid tooth number: {tooth_number}")
    history, total = await OdontogramService.get_tooth_history(
        db, ctx.clinic_id, patient_id, tooth_number, page, page_size
    )
    items = []
    for h in history:
        item = HistoryEntryWithUser.model_validate(h)
        if h.user:
            item.changed_by_name = f"{h.user.first_name} {h.user.last_name}"
        items.append(item)
    await record_access(patient_id, "odontogram")
    return PaginatedApiResponse(data=items, total=total, page=page, page_size=page_size)


@router.get(
    "/patients/{patient_id}/history",
    response_model=PaginatedApiResponse[HistoryEntryWithUser],
)
async def get_patient_odontogram_history(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    record_access: RecordPatientAccess,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedApiResponse[HistoryEntryWithUser]:
    await validate_patient_access(db, ctx.clinic_id, patient_id)
    history, total = await OdontogramService.get_patient_history(
        db, ctx.clinic_id, patient_id, page, page_size
    )
    items = []
    for h in history:
        item = HistoryEntryWithUser.model_validate(h)
        if h.user:
            item.changed_by_name = f"{h.user.first_name} {h.user.last_name}"
        items.append(item)
    await record_access(patient_id, "odontogram")
    return PaginatedApiResponse(data=items, total=total, page=page, page_size=page_size)


@router.get(
    "/patients/{patient_id}/odontogram/timeline",
    response_model=ApiResponse[TimelineResponse],
)
async def get_odontogram_timeline(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    record_access: RecordPatientAccess,
) -> ApiResponse[TimelineResponse]:
    await validate_patient_access(db, ctx.clinic_id, patient_id)
    dates = await OdontogramService.get_timeline_dates(db, ctx.clinic_id, patient_id)
    await record_access(patient_id, "odontogram")
    return ApiResponse(
        data=TimelineResponse(dates=[TimelineDateEntry(**d) for d in dates], total=len(dates))
    )


@router.get(
    "/patients/{patient_id}/odontogram/at",
    response_model=ApiResponse[HistoricalOdontogramResponse],
)
async def get_odontogram_at_date(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    record_access: RecordPatientAccess,
    target_date: date = Query(..., alias="date"),
) -> ApiResponse[HistoricalOdontogramResponse]:
    await validate_patient_access(db, ctx.clinic_id, patient_id)
    historical = await OdontogramService.get_odontogram_at_date(
        db, ctx.clinic_id, patient_id, target_date
    )
    await record_access(patient_id, "odontogram")
    return ApiResponse(
        data=HistoricalOdontogramResponse(
            patient_id=str(patient_id),
            teeth=[HistoricalToothRecordResponse.model_validate(t) for t in historical["teeth"]],
            treatments=[
                HistoricalTreatmentResponse.model_validate(t) for t in historical["treatments"]
            ],
            condition_colors=CONDITION_COLORS,
            available_conditions=[c.value for c in ToothCondition],
            surfaces=SURFACES,
        )
    )


# ============================================================================
# Treatment endpoints (single or multi-tooth, unified)
# ============================================================================


@router.post(
    "/patients/{patient_id}/treatments",
    response_model=ApiResponse[TreatmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_treatment(
    patient_id: UUID,
    data: TreatmentCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.treatments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[TreatmentResponse]:
    """Create a Treatment.

    Tooth, multi-tooth (uniform and bridge), global_mouth and global_arch flows all
    go through this endpoint. `scope` is derived from tooth count when omitted for
    non-global treatments; globals must pass `scope` explicitly.
    """
    await validate_patient_access(db, ctx.clinic_id, patient_id)
    # Schema `validate_shape` always resolves `scope` (raising if ambiguous).
    assert data.scope is not None
    try:
        treatment = await TreatmentService.create(
            db=db,
            clinic_id=ctx.clinic_id,
            patient_id=patient_id,
            user_id=ctx.user_id,
            catalog_item_id=data.catalog_item_id,
            clinical_type=data.clinical_type,
            tooth_numbers=data.tooth_numbers,
            teeth=data.teeth,
            common_surfaces=data.surfaces,
            status=data.status,
            notes=data.notes,
            budget_item_id=data.budget_item_id,
            source_module=data.source_module,
            scope=data.scope,
            arch=data.arch,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=TreatmentResponse.model_validate(build_treatment_response(treatment)))


@router.get(
    "/patients/{patient_id}/treatments",
    response_model=PaginatedApiResponse[TreatmentResponse],
)
async def list_patient_treatments(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.treatments.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    record_access: RecordPatientAccess,
    status_filter: str | None = Query(default=None, alias="status"),
    clinical_type: str | None = Query(default=None),
    tooth_number: int | None = Query(default=None),
    catalog_item_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedApiResponse[TreatmentResponse]:
    await validate_patient_access(db, ctx.clinic_id, patient_id)
    treatments, total = await TreatmentService.list_patient_treatments(
        db=db,
        clinic_id=ctx.clinic_id,
        patient_id=patient_id,
        status=status_filter,
        clinical_type=clinical_type,
        tooth_number=tooth_number,
        catalog_item_id=catalog_item_id,
        page=page,
        page_size=page_size,
    )
    await record_access(patient_id, "odontogram")
    return PaginatedApiResponse(
        data=[TreatmentResponse.model_validate(build_treatment_response(t)) for t in treatments],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/treatments/{treatment_id}",
    response_model=ApiResponse[TreatmentResponse],
)
async def get_treatment(
    treatment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.treatments.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    record_access: RecordPatientAccess,
) -> ApiResponse[TreatmentResponse]:
    treatment = await TreatmentService.get_treatment(db, ctx.clinic_id, treatment_id)
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")
    await record_access(treatment.patient_id, "odontogram")
    return ApiResponse(data=TreatmentResponse.model_validate(build_treatment_response(treatment)))


@router.put(
    "/treatments/{treatment_id}",
    response_model=ApiResponse[TreatmentResponse],
)
async def update_treatment(
    treatment_id: UUID,
    data: TreatmentUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.treatments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[TreatmentResponse]:
    treatment = await TreatmentService.update(
        db=db,
        clinic_id=ctx.clinic_id,
        treatment_id=treatment_id,
        user_id=ctx.user_id,
        status=data.status,
        notes=data.notes,
        surfaces=data.surfaces,
    )
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")
    return ApiResponse(data=TreatmentResponse.model_validate(build_treatment_response(treatment)))


@router.delete("/treatments/{treatment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_treatment(
    treatment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.treatments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    deleted = await TreatmentService.delete(db, ctx.clinic_id, treatment_id, ctx.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Treatment not found")


@router.patch(
    "/treatments/{treatment_id}/perform",
    response_model=ApiResponse[TreatmentResponse],
)
async def perform_treatment(
    treatment_id: UUID,
    data: TreatmentPerform,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.treatments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[TreatmentResponse]:
    try:
        treatment = await TreatmentService.perform(
            db=db,
            clinic_id=ctx.clinic_id,
            treatment_id=treatment_id,
            user_id=ctx.user_id,
            notes=data.notes,
        )
    except TreatmentAlreadyPerformedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")
    return ApiResponse(data=TreatmentResponse.model_validate(build_treatment_response(treatment)))


@router.get(
    "/patients/{patient_id}/teeth/{tooth_number}/full",
    response_model=ApiResponse[ToothRecordWithTreatmentsResponse],
)
async def get_tooth_with_treatments(
    patient_id: UUID,
    tooth_number: int,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("odontogram.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    record_access: RecordPatientAccess,
) -> ApiResponse[ToothRecordWithTreatmentsResponse]:
    await validate_patient_access(db, ctx.clinic_id, patient_id)
    if not is_valid_tooth_number(tooth_number):
        raise HTTPException(status_code=400, detail=f"Invalid tooth number: {tooth_number}")
    tooth, treatments = await OdontogramService.get_tooth_with_treatments(
        db, ctx.clinic_id, patient_id, tooth_number
    )
    if not tooth:
        raise HTTPException(status_code=404, detail=f"Tooth {tooth_number} not found")
    response = ToothRecordWithTreatmentsResponse.model_validate(tooth)
    response.treatments = [
        TreatmentResponse.model_validate(build_treatment_response(t)) for t in treatments
    ]
    await record_access(patient_id, "odontogram")
    return ApiResponse(data=response)
