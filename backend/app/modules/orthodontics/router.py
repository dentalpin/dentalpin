"""Orthodontics routes (issue #270, slice-a)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import (
    ClinicContext,
    get_clinic_context,
    require_permission,
)
from app.core.schemas import ApiResponse
from app.database import get_db

from .schemas import (
    OrthoCaseCreate,
    OrthoCaseResponse,
    OrthoCaseStatusChange,
    OrthoCaseUpdate,
    OrthoControlCreate,
    OrthoControlResponse,
    OrthoControlUpdate,
    OrthoSettingsResponse,
)
from .service import (
    OrthoCaseService,
    OrthoControlService,
    OrthoSettingsService,
    validate_hygiene,
    validate_wire,
)

router = APIRouter(tags=["orthodontics"])


def _case_response(case, annotation: dict) -> OrthoCaseResponse:
    response = OrthoCaseResponse.model_validate(case)
    response.control_count = annotation["control_count"]
    response.last_control_at = annotation["last_control_at"]
    response.next_due = annotation["next_due"]
    return response


def _control_response(control) -> OrthoControlResponse:
    from .service import _control_next_due

    response = OrthoControlResponse.model_validate(control)
    response.next_due = _control_next_due(control)
    return response


@router.post("/cases", response_model=ApiResponse[OrthoCaseResponse], status_code=201)
async def create_case(
    data: OrthoCaseCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("orthodontics.cases.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[OrthoCaseResponse]:
    try:
        case, annotation = await OrthoCaseService.create(db, ctx.clinic_id, data)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=_case_response(case, annotation))


@router.get("/cases", response_model=ApiResponse[list[OrthoCaseResponse]])
async def list_cases(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("orthodontics.cases.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    patient_id: UUID | None = None,
    case_status: str | None = Query(default=None, alias="status"),
) -> ApiResponse[list[OrthoCaseResponse]]:
    try:
        if patient_id is not None:
            rows = await OrthoCaseService.list_for_patient(db, ctx.clinic_id, patient_id)
        else:
            rows = await OrthoCaseService.list_active(db, ctx.clinic_id, case_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=[_case_response(c, a) for c, a in rows])


@router.get("/cases/{case_id}", response_model=ApiResponse[OrthoCaseResponse])
async def get_case(
    case_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("orthodontics.cases.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[OrthoCaseResponse]:
    found = await OrthoCaseService.get(db, ctx.clinic_id, case_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Case not found")
    case, annotation = found
    return ApiResponse(data=_case_response(case, annotation))


@router.patch("/cases/{case_id}", response_model=ApiResponse[OrthoCaseResponse])
async def update_case(
    case_id: UUID,
    data: OrthoCaseUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("orthodontics.cases.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[OrthoCaseResponse]:
    try:
        found = await OrthoCaseService.update(db, ctx.clinic_id, case_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if found is None:
        raise HTTPException(status_code=404, detail="Case not found")
    case, annotation = found
    return ApiResponse(data=_case_response(case, annotation))


@router.post("/cases/{case_id}/status", response_model=ApiResponse[OrthoCaseResponse])
async def change_case_status(
    case_id: UUID,
    data: OrthoCaseStatusChange,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("orthodontics.cases.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[OrthoCaseResponse]:
    try:
        found = await OrthoCaseService.change_status(
            db, ctx.clinic_id, case_id, data.status, data.status_note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if found is None:
        raise HTTPException(status_code=404, detail="Case not found")
    case, annotation = found
    return ApiResponse(data=_case_response(case, annotation))


@router.post(
    "/cases/{case_id}/controls",
    response_model=ApiResponse[OrthoControlResponse],
    status_code=201,
)
async def register_control(
    case_id: UUID,
    data: OrthoControlCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("orthodontics.controls.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[OrthoControlResponse]:
    try:
        await validate_wire(db, ctx.clinic_id, data.upper_wire)
        await validate_wire(db, ctx.clinic_id, data.lower_wire)
        await validate_hygiene(data.hygiene)
        control = await OrthoControlService.register(
            db, ctx.clinic_id, case_id, data, performed_by=ctx.user_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=_control_response(control))


@router.get("/cases/{case_id}/controls", response_model=ApiResponse[list[OrthoControlResponse]])
async def list_controls(
    case_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("orthodontics.cases.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[OrthoControlResponse]]:
    controls = await OrthoControlService.list_for_case(db, ctx.clinic_id, case_id)
    if controls is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return ApiResponse(data=[_control_response(c) for c in controls])


@router.patch("/controls/{control_id}", response_model=ApiResponse[OrthoControlResponse])
async def update_control(
    control_id: UUID,
    data: OrthoControlUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("orthodontics.controls.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[OrthoControlResponse]:
    try:
        if data.upper_wire is not None:
            await validate_wire(db, ctx.clinic_id, data.upper_wire)
        if data.lower_wire is not None:
            await validate_wire(db, ctx.clinic_id, data.lower_wire)
        await validate_hygiene(data.hygiene)
        control = await OrthoControlService.update(db, ctx.clinic_id, control_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if control is None:
        raise HTTPException(status_code=404, detail="Control not found")
    return ApiResponse(data=_control_response(control))


@router.get("/settings", response_model=ApiResponse[OrthoSettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("orthodontics.cases.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[OrthoSettingsResponse]:
    settings = await OrthoSettingsService.get_or_seed(db, ctx.clinic_id)
    return ApiResponse(data=OrthoSettingsResponse.model_validate(settings))
