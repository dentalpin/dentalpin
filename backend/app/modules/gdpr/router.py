"""gdpr HTTP surface — mounted at ``/api/v1/gdpr/``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    ConsentCreate,
    ConsentResponse,
    DataBreachCreate,
    DataBreachResponse,
    DataBreachUpdate,
    ErasureAuditResponse,
    ErasureRequest,
    ErasureResult,
    ExportResponse,
    GdprRequestCreate,
    GdprRequestResponse,
    GdprRequestUpdate,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
    RetentionPolicyUpdate,
)
from .service import (
    ConsentService,
    DataBreachService,
    ErasureService,
    ExportService,
    GdprService,
    RetentionService,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Data-subject requests (DSR) — Art. 15-21
# ---------------------------------------------------------------------------
@router.get("/requests", response_model=PaginatedApiResponse[GdprRequestResponse])
async def list_requests(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.requests.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(default=None),
    request_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[GdprRequestResponse]:
    items, total = await GdprService.list_requests(
        db, ctx.clinic_id, status=status, request_type=request_type, page=page, page_size=page_size
    )
    return PaginatedApiResponse(
        data=[GdprRequestResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/requests/{request_id}", response_model=ApiResponse[GdprRequestResponse])
async def get_request(
    request_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.requests.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[GdprRequestResponse]:
    row = await GdprService.get_request(db, ctx.clinic_id, request_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return ApiResponse(data=GdprRequestResponse.model_validate(row))


@router.post(
    "/requests",
    response_model=ApiResponse[GdprRequestResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_request(
    data: GdprRequestCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.requests.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[GdprRequestResponse]:
    row = await GdprService.create_request(db, ctx.clinic_id, data)
    return ApiResponse(data=GdprRequestResponse.model_validate(row))


@router.patch("/requests/{request_id}", response_model=ApiResponse[GdprRequestResponse])
async def update_request(
    request_id: UUID,
    data: GdprRequestUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.requests.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[GdprRequestResponse]:
    row = await GdprService.get_request(db, ctx.clinic_id, request_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    row = await GdprService.update_request(db, row, data, resolved_by=ctx.user_id)
    return ApiResponse(data=GdprRequestResponse.model_validate(row))


# NOTE: no DELETE /requests/{id} — DSRs are accountability records
# (Art. 5(2)) and are immutable except for status transitions above.


# ---------------------------------------------------------------------------
# Consents — Art. 7-8
# ---------------------------------------------------------------------------
@router.get("/consents", response_model=PaginatedApiResponse[ConsentResponse])
async def list_consents(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.consents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    patient_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[ConsentResponse]:
    items, total = await ConsentService.list_consents(
        db, ctx.clinic_id, patient_id=patient_id, page=page, page_size=page_size
    )
    return PaginatedApiResponse(
        data=[ConsentResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/consents", response_model=ApiResponse[ConsentResponse], status_code=status.HTTP_201_CREATED
)
async def record_consent(
    data: ConsentCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.consents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ConsentResponse]:
    row = await ConsentService.grant_or_withdraw(db, ctx.clinic_id, data)
    return ApiResponse(data=ConsentResponse.model_validate(row))


# ---------------------------------------------------------------------------
# Retention policies — Art. 5(1)(e)
# ---------------------------------------------------------------------------
@router.get("/retention", response_model=ApiResponse[list[RetentionPolicyResponse]])
async def list_retention(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.retention.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[RetentionPolicyResponse]]:
    rows = await RetentionService.list_active(db, ctx.clinic_id)
    return ApiResponse(data=[RetentionPolicyResponse.model_validate(r) for r in rows])


@router.post(
    "/retention",
    response_model=ApiResponse[RetentionPolicyResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_retention_policy(
    data: RetentionPolicyCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.retention.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RetentionPolicyResponse]:
    row = await RetentionService.create(db, ctx.clinic_id, data)
    return ApiResponse(data=RetentionPolicyResponse.model_validate(row))


@router.patch("/retention/{policy_id}", response_model=ApiResponse[RetentionPolicyResponse])
async def update_retention_policy(
    policy_id: UUID,
    data: RetentionPolicyUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.retention.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RetentionPolicyResponse]:
    row = await RetentionService.get_active_by_id(db, ctx.clinic_id, policy_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    row = await RetentionService.update(db, row, data)
    return ApiResponse(data=RetentionPolicyResponse.model_validate(row))


@router.delete("/retention/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_retention_policy(
    policy_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.retention.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    deleted = await RetentionService.delete(db, ctx.clinic_id, policy_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")


# ---------------------------------------------------------------------------
# Erasure — Art. 17
# ---------------------------------------------------------------------------
@router.post(
    "/erasure", response_model=ApiResponse[ErasureResult], status_code=status.HTTP_201_CREATED
)
async def execute_erasure(
    data: ErasureRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.requests.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ErasureResult]:
    result = await ErasureService.execute(
        db,
        ctx.clinic_id,
        patient_id=data.patient_id,
        categories=data.categories,
        rationale=data.rationale,
        executed_by=ctx.user_id,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return ApiResponse(data=result)


@router.get("/audit", response_model=PaginatedApiResponse[ErasureAuditResponse])
async def list_erasure_audit(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.audit.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[ErasureAuditResponse]:
    items, total = await ErasureService.list_audit(
        db, ctx.clinic_id, page=page, page_size=page_size
    )
    return PaginatedApiResponse(
        data=[ErasureAuditResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Breaches — Art. 33-34
# ---------------------------------------------------------------------------
@router.get("/breaches", response_model=PaginatedApiResponse[DataBreachResponse])
async def list_breaches(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.breaches.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[DataBreachResponse]:
    items, total = await DataBreachService.list(
        db, ctx.clinic_id, status=status, page=page, page_size=page_size
    )
    return PaginatedApiResponse(
        data=[DataBreachResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/breaches/{breach_id}", response_model=ApiResponse[DataBreachResponse])
async def get_breach(
    breach_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.breaches.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DataBreachResponse]:
    row = await DataBreachService.get(db, ctx.clinic_id, breach_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Breach not found")
    return ApiResponse(data=DataBreachResponse.model_validate(row))


@router.post(
    "/breaches", response_model=ApiResponse[DataBreachResponse], status_code=status.HTTP_201_CREATED
)
async def create_breach(
    data: DataBreachCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.breaches.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DataBreachResponse]:
    row = await DataBreachService.create(db, ctx.clinic_id, data)
    return ApiResponse(data=DataBreachResponse.model_validate(row))


@router.patch("/breaches/{breach_id}", response_model=ApiResponse[DataBreachResponse])
async def update_breach(
    breach_id: UUID,
    data: DataBreachUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.breaches.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DataBreachResponse]:
    row = await DataBreachService.get(db, ctx.clinic_id, breach_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Breach not found")
    row = await DataBreachService.update(db, row, data)
    return ApiResponse(data=DataBreachResponse.model_validate(row))


# ---------------------------------------------------------------------------
# Portability export — Art. 20
# ---------------------------------------------------------------------------
@router.get("/export/{patient_id}", response_model=ApiResponse[ExportResponse])
async def export_patient_data(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("gdpr.requests.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ExportResponse]:
    data = await ExportService.export(db, ctx.clinic_id, patient_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return ApiResponse(
        data=ExportResponse(
            patient_id=patient_id,
            clinic_id=ctx.clinic_id,
            data=data,
        )
    )
