"""FastAPI routes for the documents module.

Routes mounted at ``/api/v1/documents/`` by the plugin loader.
Every route takes ``ctx`` and ``require_permission`` for multi-tenancy
and RBAC.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import (
    ClinicContext,
    get_clinic_context,
    require_permission,
)
from app.core.patient_access import RecordPatientAccess
from app.core.pdf_locales import PDF_LOCALE_PATTERN
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from . import service
from .schemas import (
    DocumentCreate,
    DocumentGenerateRequest,
    DocumentResponse,
    DocumentUpdate,
    LetterheadSettings,
)

router = APIRouter()


@router.get(
    "/settings/letterhead",
    response_model=ApiResponse[LetterheadSettings],
)
async def get_letterhead_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.clinic.read"))],
) -> ApiResponse[LetterheadSettings]:
    """Return the clinic's current letterhead overrides.

    Unset fields are returned as ``null`` — the renderer falls back to
    the clinic's native profile for those. The endpoint is clinic-scoped
    via ``ctx`` and needs no database access.
    """
    settings_block = {}
    if isinstance(ctx.clinic.settings, dict):
        settings_block = ctx.clinic.settings.get("documents") or {}
        settings_block = settings_block.get("letterhead") or {}
    return ApiResponse(data=LetterheadSettings.model_validate(settings_block))


@router.put(
    "/settings/letterhead",
    response_model=ApiResponse[LetterheadSettings],
)
async def set_letterhead_settings(
    data: LetterheadSettings,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.clinic.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[LetterheadSettings]:
    """Persist letterhead overrides under ``clinic.settings``.

    Stored namespaced as ``settings["documents"]["letterhead"]`` so it
    never collides with other modules' clinic settings (budget, …).
    """
    current = ctx.clinic.settings or {}
    doc_block = dict(current.get("documents") or {})
    # Only keys present in the payload are stored — absent ones fall
    # back to the clinic profile at render time.
    stored = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    doc_block["letterhead"] = stored
    current["documents"] = doc_block
    ctx.clinic.settings = current
    await db.flush()
    return ApiResponse(data=LetterheadSettings.model_validate(stored))


@router.get(
    "",
    response_model=PaginatedApiResponse[DocumentResponse],
)
async def list_documents(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    record_access: RecordPatientAccess,
    patient_id: uuid.UUID | None = Query(default=None),
    document_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[DocumentResponse]:
    """List documents with optional filters."""
    items, total = await service.DocumentService.list_documents(
        db,
        ctx.clinic_id,
        patient_id=patient_id,
        document_type=document_type,
        status=status,
        page=page,
        page_size=page_size,
    )
    if patient_id is not None and items:
        await record_access(patient_id, "documents")
    return PaginatedApiResponse(
        data=[DocumentResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{document_id}",
    response_model=ApiResponse[DocumentResponse],
)
async def get_document(
    document_id: uuid.UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    record_access: RecordPatientAccess,
) -> ApiResponse[DocumentResponse]:
    """Get a single document."""
    doc = await service.DocumentService.get_document(db, ctx.clinic_id, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await record_access(doc.patient_id, "documents")
    return ApiResponse(data=DocumentResponse.model_validate(doc))


@router.get(
    "/{document_id}/download",
    response_class=Response,
)
async def download_document(
    document_id: uuid.UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    record_access: RecordPatientAccess,
) -> Response:
    """Download a generated document as branded PDF.

    Streams the file rendered at generation time. Returns 404 when the
    document is unknown, not yet generated, or its file is missing.
    """
    doc = await service.DocumentService.get_document(db, ctx.clinic_id, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != "generated":
        raise HTTPException(
            status_code=409,
            detail="Document has not been generated yet",
        )

    pdf_bytes = await service.DocumentService.download_pdf(db, ctx.clinic_id, document_id)
    if pdf_bytes is None:
        raise HTTPException(
            status_code=404,
            detail="Rendered file not found — regenerate the document",
        )

    filename = f"{doc.document_type}_{str(doc.id)[:8]}.pdf"
    await record_access(doc.patient_id, "document_pdf", action="download")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "",
    response_model=ApiResponse[DocumentResponse],
    status_code=201,
)
async def create_document(
    data: DocumentCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DocumentResponse]:
    """Create a new document."""
    doc = await service.DocumentService.create_document(
        db,
        ctx.clinic_id,
        patient_id=data.patient_id,
        document_type=data.document_type,
        title=data.title,
        content=data.content,
        created_by=ctx.user_id,
    )
    if doc is None:
        raise HTTPException(
            status_code=400,
            detail="Patient does not belong to this clinic",
        )
    return ApiResponse(data=DocumentResponse.model_validate(doc))


@router.patch(
    "/{document_id}",
    response_model=ApiResponse[DocumentResponse],
)
async def update_document(
    document_id: uuid.UUID,
    data: DocumentUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DocumentResponse]:
    """Partial update of a document."""
    doc = await service.DocumentService.update_document(
        db,
        ctx.clinic_id,
        document_id,
        title=data.title,
        content=data.content,
        status=data.status,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return ApiResponse(data=DocumentResponse.model_validate(doc))


@router.delete(
    "/{document_id}",
    status_code=204,
)
async def delete_document(
    document_id: uuid.UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete (archive) a document."""
    deleted = await service.DocumentService.delete_document(db, ctx.clinic_id, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


@router.post(
    "/generate",
    response_model=ApiResponse[DocumentResponse],
)
async def generate_document(
    data: DocumentGenerateRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    locale: str = Query(default="es", pattern=PDF_LOCALE_PATTERN),
) -> ApiResponse[DocumentResponse]:
    """Generate (render) a document as a branded PDF.

    Renders via WeasyPrint, persists the file under the storage
    backend, marks the document as generated, and publishes
    ``DOCUMENT_GENERATED`` on the event bus.
    """
    doc = await service.DocumentService.generate_pdf(
        db, ctx.clinic_id, data.document_id, locale=locale
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return ApiResponse(data=DocumentResponse.model_validate(doc))
