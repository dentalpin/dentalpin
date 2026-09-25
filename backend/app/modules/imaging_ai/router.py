"""imaging_ai HTTP surface — mounted at ``/api/v1/imaging_ai/``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import AiJobQueueRequest, AiJobResponse, DicomDocumentResponse
from .service import AiJobService

router = APIRouter()


async def _get_job_or_404(db: AsyncSession, clinic_id: UUID, job_id: UUID):
    job = await AiJobService.get_job(db, clinic_id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post(
    "/patients/{patient_id}/ai-jobs",
    response_model=ApiResponse[AiJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def queue_job(
    patient_id: UUID,
    data: AiJobQueueRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_ai.jobs.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AiJobResponse]:
    """Record an AI run and return immediately (202). Execution happens on
    the scheduler tick — the request never blocks on the model, and the
    agent path (no identity) lands as a proposal until confirmed."""
    try:
        job = await AiJobService.queue_job(
            db,
            ctx.clinic_id,
            patient_id,
            ctx.user_id,
            data.document_id,
            series_document_ids=data.series_document_ids,
            backend=data.backend,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient or document not found"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ApiResponse(data=AiJobResponse.model_validate(job))


@router.post("/ai-jobs/{job_id}/confirm", response_model=ApiResponse[AiJobResponse])
async def confirm_job(
    job_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_ai.jobs.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AiJobResponse]:
    """Clinician confirm: authorizes a proposed run (stamps the confirmer)
    or records the review of finished draft artifacts. Anything else
    answers 409."""
    job = await _get_job_or_404(db, ctx.clinic_id, job_id)
    try:
        job = await AiJobService.confirm_job(db, job, ctx.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ApiResponse(data=job)


@router.get(
    "/patients/{patient_id}/dicom-documents",
    response_model=ApiResponse[list[DicomDocumentResponse]],
)
async def dicom_documents(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_ai.jobs.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[DicomDocumentResponse]]:
    """DICOM candidates for the series picker (clinic + patient scoped)."""
    docs = await AiJobService.list_dicom_documents(db, ctx.clinic_id, patient_id)
    return ApiResponse(
        data=[
            d
            for d in (DicomDocumentResponse.model_validate(x) for x in docs)
            if d.mime_type == "application/dicom" or d.original_filename.lower().endswith(".dcm")
        ]
    )


@router.get(
    "/patients/{patient_id}/ai-jobs",
    response_model=PaginatedApiResponse[AiJobResponse],
)
async def list_jobs(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_ai.jobs.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[AiJobResponse]:
    items, total = await AiJobService.list_jobs(
        db, ctx.clinic_id, patient_id, page=page, page_size=page_size
    )
    return PaginatedApiResponse(
        data=[AiJobResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/ai-jobs/{job_id}", response_model=ApiResponse[AiJobResponse])
async def get_job(
    job_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_ai.jobs.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AiJobResponse]:
    job = await _get_job_or_404(db, ctx.clinic_id, job_id)
    return ApiResponse(data=AiJobResponse.model_validate(job))


@router.delete("/ai-jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(
    job_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_ai.jobs.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Cancel a proposed or queued job. Anything already running finishes;
    terminal states answer 409 (mirrors the migration_import execute guard)."""
    job = await _get_job_or_404(db, ctx.clinic_id, job_id)
    try:
        await AiJobService.cancel_job(db, job)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
