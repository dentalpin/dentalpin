"""imaging_viewer HTTP surface — mounted at ``/api/v1/imaging_viewer/``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    AnnotationCreateRequest,
    AnnotationResponse,
    ImagingStudyResponse,
    RvgApproveRequest,
    RvgImportResponse,
    RvgLinkResponse,
    RvgRejectRequest,
    RvgScanRequest,
    StudyIndexRequest,
)
from .service import (
    AnnotationService,
    ImagingStudyService,
    RvgConflictError,
    RvgService,
    UnrenderableStudyError,
)

router = APIRouter()


@router.get(
    "/patients/{patient_id}/studies",
    response_model=PaginatedApiResponse[ImagingStudyResponse],
)
async def list_studies(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.studies.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_archived: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[ImagingStudyResponse]:
    items, total = await ImagingStudyService.list_studies(
        db,
        ctx.clinic_id,
        patient_id,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )
    return PaginatedApiResponse(
        data=[ImagingStudyResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/studies/{study_id}", response_model=ApiResponse[ImagingStudyResponse])
async def get_study(
    study_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.studies.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ImagingStudyResponse]:
    study = await ImagingStudyService.get_study(db, ctx.clinic_id, study_id)
    if not study:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    return ApiResponse(data=ImagingStudyResponse.model_validate(study))


@router.post(
    "/patients/{patient_id}/studies/index",
    response_model=ApiResponse[ImagingStudyResponse],
    status_code=status.HTTP_201_CREATED,
)
async def index_study(
    patient_id: UUID,
    data: StudyIndexRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.studies.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ImagingStudyResponse] | JSONResponse:
    try:
        study, created = await ImagingStudyService.index_study(
            db,
            ctx.clinic_id,
            patient_id,
            data.document_id,
            study_uid=data.study_uid,
            modality=data.modality,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not created:
        # Idempotent re-index: same document, same row — 200, not 201.
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=ApiResponse(data=ImagingStudyResponse.model_validate(study)).model_dump(
                mode="json"
            ),
        )
    return ApiResponse(data=ImagingStudyResponse.model_validate(study))


@router.get("/studies/{study_id}/render")
async def render_study(
    study_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.studies.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Render the study to PNG for the viewer + annotation canvas.

    Same-clinic only (LookupError → 404, never a cross-tenant oracle).
    Undecodable pixels → 422 (re-upload, don't retry).
    """
    try:
        content = await ImagingStudyService.render_study_png(db, ctx.clinic_id, study_id)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    except UnrenderableStudyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return Response(
        content=content,
        media_type="image/png",
        headers={"Content-Length": str(len(content))},
    )


@router.delete("/studies/{study_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_study(
    study_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.studies.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    study = await ImagingStudyService.get_study(db, ctx.clinic_id, study_id)
    if not study:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    await ImagingStudyService.archive_study(db, study)


# ---------------------------------------------------------------------------
# RVG watch-folder import queue (T1). Same studies.read/write gates as the
# viewer: scanning/listing needs read, deciding (approve/reject/unlink)
# needs write. Approval materializes a media document + study index.
# ---------------------------------------------------------------------------


def _rvg_watch_path(ctx: ClinicContext) -> str:
    import os

    root = os.environ.get("DENTALPIN_RVG_WATCH_DIR", "")
    if not root:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RVG watch folder is not configured (DENTALPIN_RVG_WATCH_DIR)",
        )
    return os.path.join(root, str(ctx.clinic_id))


@router.post("/rvg/scan", response_model=ApiResponse[dict])
async def rvg_scan(
    data: RvgScanRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.rvg.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    """Scan the clinic's watch folder now (scheduler-independent trigger)."""
    path = _rvg_watch_path(ctx)
    counts = await RvgService.scan_watch_dir(
        db, ctx.clinic_id, path, limit=50, retry_failed=data.retry_failed
    )
    return ApiResponse(data=counts)


@router.get("/rvg/imports", response_model=PaginatedApiResponse[RvgImportResponse])
async def rvg_list_imports(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.rvg.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[RvgImportResponse]:
    items, total = await RvgService.list_imports(
        db, ctx.clinic_id, status=status_filter, page=page, page_size=page_size
    )
    return PaginatedApiResponse(
        data=[RvgImportResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/rvg/imports/{import_id}", response_model=ApiResponse[RvgImportResponse])
async def rvg_get_import(
    import_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.rvg.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RvgImportResponse]:
    row = await RvgService.get_import(db, ctx.clinic_id, import_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")
    return ApiResponse(data=RvgImportResponse.model_validate(row))


@router.post(
    "/rvg/imports/{import_id}/approve",
    response_model=ApiResponse[RvgImportResponse],
)
async def rvg_approve_import(
    import_id: UUID,
    data: RvgApproveRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.rvg.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RvgImportResponse]:
    """Approve a pending import: document + study are created, the DICOM
    identity is linked so future files auto-import."""
    row = await RvgService.get_import(db, ctx.clinic_id, import_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")
    raw = RvgService.read_source_bytes(ctx.clinic_id, row.filename)
    try:
        decided = await RvgService.approve(
            db, ctx.clinic_id, import_id, data.patient_id, ctx.user_id, raw=raw
        )
    except RvgConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    RvgService.retire_source_file(ctx.clinic_id, decided.filename)
    return ApiResponse(data=RvgImportResponse.model_validate(decided))


@router.post(
    "/rvg/imports/{import_id}/reject",
    response_model=ApiResponse[RvgImportResponse],
)
async def rvg_reject_import(
    import_id: UUID,
    data: RvgRejectRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.rvg.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RvgImportResponse]:
    try:
        decided = await RvgService.reject(db, ctx.clinic_id, import_id, reason=data.reason)
    except RvgConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return ApiResponse(data=RvgImportResponse.model_validate(decided))


@router.get("/rvg/links", response_model=ApiResponse[list[RvgLinkResponse]])
async def rvg_list_links(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.rvg.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[RvgLinkResponse]]:
    links = await RvgService.list_links(db, ctx.clinic_id)
    return ApiResponse(data=[RvgLinkResponse.model_validate(i) for i in links])


@router.delete("/rvg/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def rvg_delete_link(
    link_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.rvg.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if not await RvgService.delete_link(db, ctx.clinic_id, link_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")


# ---------------------------------------------------------------------------
# Human annotation overlays (T2). Same studies gates: read to view, write
# to draw. Overlays never mutate the original bytes; delete archives (L7).
# ---------------------------------------------------------------------------


@router.get(
    "/studies/{study_id}/annotations",
    response_model=ApiResponse[list[AnnotationResponse]],
)
async def list_annotations(
    study_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.studies.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[AnnotationResponse]]:
    try:
        rows = await AnnotationService.list(db, ctx.clinic_id, study_id)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    return ApiResponse(data=[AnnotationResponse.model_validate(i) for i in rows])


@router.post(
    "/studies/{study_id}/annotations",
    response_model=ApiResponse[AnnotationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    study_id: UUID,
    data: AnnotationCreateRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.studies.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AnnotationResponse]:
    try:
        row = await AnnotationService.create(
            db, ctx.clinic_id, study_id, ctx.user_id, data.kind, data.payload
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ApiResponse(data=AnnotationResponse.model_validate(row))


@router.delete("/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_annotation(
    annotation_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("imaging_viewer.studies.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if not await AnnotationService.archive(db, ctx.clinic_id, annotation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found")
