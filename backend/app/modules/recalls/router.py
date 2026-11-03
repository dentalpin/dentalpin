"""Recalls HTTP surface — mounted at ``/api/v1/recalls/``.

All endpoints filter by ``clinic_id`` from the request context.
Permissions: ``recalls.{read,write,delete}``.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import (
    ClinicContext,
    get_clinic_context,
    require_permission,
)
from app.core.csv_safety import csv_row
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    AttemptCreate,
    AttemptResponse,
    PatientBriefForRecall,
    RecallCancelRequest,
    RecallCreate,
    RecallDashboardStats,
    RecallDetailResponse,
    RecallLinkAppointmentRequest,
    RecallResponse,
    RecallSettingsResponse,
    RecallSettingsUpdate,
    RecallSnoozeRequest,
    RecallSuggestion,
    RecallUpdate,
)
from .schemas import (
    Status as RecallStatusLiteral,
)
from .service import (
    RecallClosedError,
    RecallFilters,
    RecallService,
    RecallSettingsService,
)

router = APIRouter()


# --- Helpers --------------------------------------------------------------


def _serialise(recall) -> RecallResponse:
    payload = RecallResponse.model_validate(recall)
    if getattr(recall, "patient", None) is not None:
        payload.patient = PatientBriefForRecall.model_validate(recall.patient)
    return payload


# --- List + create --------------------------------------------------------


@router.get("/", response_model=PaginatedApiResponse[RecallResponse])
async def list_recalls(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    month: date | None = Query(default=None, description="Any day in target month"),
    reason: str | None = None,
    professional_id: UUID | None = None,
    status_filter: RecallStatusLiteral | None = Query(default=None, alias="status"),
    priority: str | None = None,
    overdue: bool = False,
    patient_id: UUID | None = None,
    include_archived_patients: bool = False,
    include_do_not_contact: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> PaginatedApiResponse[RecallResponse]:
    filters = RecallFilters(
        month=month,
        reason=reason,
        professional_id=professional_id,
        status=status_filter,
        priority=priority,
        overdue=overdue,
        patient_id=patient_id,
        include_archived_patients=include_archived_patients,
        include_do_not_contact=include_do_not_contact,
    )
    items, total = await RecallService.list(
        db, ctx.clinic_id, filters, page=page, page_size=page_size
    )
    return PaginatedApiResponse(
        data=[_serialise(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/",
    response_model=ApiResponse[RecallResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_recall(
    data: RecallCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RecallResponse]:
    try:
        recall, _created = await RecallService.create(
            db,
            clinic_id=ctx.clinic_id,
            data=data.model_dump(),
            recommended_by=ctx.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await db.commit()
    return ApiResponse(data=_serialise(recall))


@router.get("/stats/dashboard", response_model=ApiResponse[RecallDashboardStats])
async def get_dashboard_stats(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RecallDashboardStats]:
    stats = await RecallService.dashboard_stats(db, ctx.clinic_id)
    return ApiResponse(data=RecallDashboardStats(**stats))


@router.get("/suggestions/next", response_model=ApiResponse[RecallSuggestion | None])
async def suggest_next_recall(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    patient_id: UUID = Query(...),
    treatment_category_key: str | None = Query(default=None),
    treatment_id: UUID | None = Query(default=None),
) -> ApiResponse[RecallSuggestion | None]:
    suggestion = await RecallService.suggest_next_for_treatment(
        db,
        clinic_id=ctx.clinic_id,
        patient_id=patient_id,
        treatment_category_key=treatment_category_key,
        treatment_id=treatment_id,
    )
    if not suggestion:
        return ApiResponse(data=None)
    return ApiResponse(data=RecallSuggestion(**suggestion))


@router.get("/settings", response_model=ApiResponse[RecallSettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RecallSettingsResponse]:
    settings = await RecallSettingsService.get_or_create(db, ctx.clinic_id)
    await db.commit()
    return ApiResponse(data=RecallSettingsResponse.model_validate(settings))


@router.put("/settings", response_model=ApiResponse[RecallSettingsResponse])
async def update_settings(
    data: RecallSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RecallSettingsResponse]:
    settings = await RecallSettingsService.update(
        db, ctx.clinic_id, data.model_dump(exclude_unset=True)
    )
    await db.commit()
    return ApiResponse(data=RecallSettingsResponse.model_validate(settings))


@router.get("/export.csv")
async def export_csv(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    month: date | None = Query(default=None),
    reason: str | None = None,
    status_filter: RecallStatusLiteral | None = Query(default=None, alias="status"),
    priority: str | None = None,
    overdue: bool = False,
    professional_id: UUID | None = None,
) -> StreamingResponse:
    filters = RecallFilters(
        month=month,
        reason=reason,
        status=status_filter,
        priority=priority,
        overdue=overdue,
        professional_id=professional_id,
    )
    rows = await RecallService.export_rows(db, ctx.clinic_id, filters)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "due_month",
            "patient",
            "phone",
            "reason",
            "priority",
            "status",
            "attempts",
            "professional",
            "note",
        ]
    )
    for recall, patient in rows:
        # Patient names arrive through the public lead intake and the note
        # is free text (#611); counts stay numbers.
        writer.writerow(
            csv_row(
                [
                    recall.due_month.isoformat(),
                    f"{patient.first_name} {patient.last_name}".strip(),
                    patient.phone or "",
                    recall.reason,
                    recall.priority,
                    recall.status,
                    recall.contact_attempt_count,
                    str(recall.assigned_professional_id or ""),
                    (recall.reason_note or "").replace("\n", " "),
                ]
            )
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=recalls.csv"},
    )


@router.get("/patients/{patient_id}", response_model=ApiResponse[list[RecallResponse]])
async def list_patient_recalls(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[RecallResponse]]:
    items = await RecallService.list_for_patient(db, ctx.clinic_id, patient_id)
    return ApiResponse(data=[RecallResponse.model_validate(r) for r in items])


# --- Per-id surface ------------------------------------------------------


@router.get("/{recall_id}", response_model=ApiResponse[RecallDetailResponse])
async def get_recall(
    recall_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RecallDetailResponse]:
    recall, attempts = await RecallService.get_with_attempts(db, ctx.clinic_id, recall_id)
    if not recall:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recall not found")
    payload = RecallDetailResponse.model_validate(recall)
    payload.attempts = [AttemptResponse.model_validate(a) for a in attempts]
    return ApiResponse(data=payload)


@router.patch("/{recall_id}", response_model=ApiResponse[RecallResponse])
async def update_recall(
    recall_id: UUID,
    data: RecallUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RecallResponse]:
    recall = await RecallService.update(
        db, ctx.clinic_id, recall_id, data.model_dump(exclude_unset=True)
    )
    if not recall:
        raise HTTPException(status_code=404, detail="Recall not found")
    await db.commit()
    return ApiResponse(data=RecallResponse.model_validate(recall))


@router.post("/{recall_id}/snooze", response_model=ApiResponse[RecallResponse])
async def snooze_recall(
    recall_id: UUID,
    data: RecallSnoozeRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RecallResponse]:
    try:
        recall = await RecallService.snooze(
            db,
            ctx.clinic_id,
            recall_id,
            months=data.months,
            reason_note=data.reason_note,
            by_user=ctx.user_id,
        )
    except RecallClosedError as exc:
        raise HTTPException(status_code=409, detail="Recall is closed") from exc
    if not recall:
        raise HTTPException(status_code=404, detail="Recall not found")
    await db.commit()
    return ApiResponse(data=RecallResponse.model_validate(recall))


@router.post("/{recall_id}/cancel", response_model=ApiResponse[RecallResponse])
async def cancel_recall(
    recall_id: UUID,
    data: RecallCancelRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RecallResponse]:
    try:
        recall = await RecallService.cancel(
            db,
            ctx.clinic_id,
            recall_id,
            note=data.note,
            by_user=ctx.user_id,
        )
    except RecallClosedError as exc:
        raise HTTPException(status_code=409, detail="Recall is closed") from exc
    if not recall:
        raise HTTPException(status_code=404, detail="Recall not found")
    await db.commit()
    return ApiResponse(data=RecallResponse.model_validate(recall))


@router.post("/{recall_id}/done", response_model=ApiResponse[RecallResponse])
async def mark_recall_done(
    recall_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RecallResponse]:
    try:
        recall = await RecallService.mark_done(db, ctx.clinic_id, recall_id, by_user=ctx.user_id)
    except RecallClosedError as exc:
        raise HTTPException(status_code=409, detail="Recall is closed") from exc
    if not recall:
        raise HTTPException(status_code=404, detail="Recall not found")
    await db.commit()
    return ApiResponse(data=RecallResponse.model_validate(recall))


@router.post(
    "/{recall_id}/attempts",
    response_model=ApiResponse[AttemptResponse],
    status_code=status.HTTP_201_CREATED,
)
async def log_attempt(
    recall_id: UUID,
    data: AttemptCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AttemptResponse]:
    if not ctx.user_id:
        raise HTTPException(status_code=400, detail="user_id required to log attempt")
    try:
        result = await RecallService.log_attempt(
            db,
            ctx.clinic_id,
            recall_id,
            attempt_data=data.model_dump(),
            by_user=ctx.user_id,
        )
    except RecallClosedError as exc:
        raise HTTPException(status_code=409, detail="Recall is closed") from exc
    if not result:
        raise HTTPException(status_code=404, detail="Recall not found")
    _, attempt = result
    await db.commit()
    return ApiResponse(data=AttemptResponse.model_validate(attempt))


@router.get("/{recall_id}/attempts", response_model=ApiResponse[list[AttemptResponse]])
async def list_attempts(
    recall_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[AttemptResponse]]:
    attempts = await RecallService.list_attempts(db, ctx.clinic_id, recall_id)
    return ApiResponse(data=[AttemptResponse.model_validate(a) for a in attempts])


@router.post("/{recall_id}/link-appointment", response_model=ApiResponse[RecallResponse])
async def link_appointment(
    recall_id: UUID,
    data: RecallLinkAppointmentRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RecallResponse]:
    recall = await RecallService.link_appointment(db, ctx.clinic_id, recall_id, data.appointment_id)
    if not recall:
        raise HTTPException(status_code=404, detail="Recall not found")
    await db.commit()
    return ApiResponse(data=RecallResponse.model_validate(recall))


@router.delete("/{recall_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recall(
    recall_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("recalls.delete"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    recall = await RecallService.get(db, ctx.clinic_id, recall_id)
    if not recall:
        raise HTTPException(status_code=404, detail="Recall not found")
    await db.delete(recall)
    await db.commit()
    return None
