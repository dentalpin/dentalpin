"""FastAPI routes for the documents module.

Routes mounted at ``/api/v1/documents/`` by the plugin loader.
Every route takes ``ctx`` and ``require_permission`` for multi-tenancy
and RBAC.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import (
    ClinicContext,
    get_clinic_context,
    require_permission,
)
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db
from . import service
from .schemas import (
    DocumentCreate,
    DocumentGenerateRequest,
    DocumentResponse,
    DocumentUpdate,
)

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedApiResponse[DocumentResponse],
)
async def list_documents(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    patient_id: str | None = Query(default=None),
    document_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[DocumentResponse]:
    """List documents with optional filters."""
    pid = _uuid.UUID(patient_id) if patient_id else None
    items, total = await service.DocumentService.list_documents(
        db,
        ctx.clinic_id,
        patient_id=pid,
        document_type=document_type,
        status=status,
        page=page,
        page_size=page_size,
    )
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
    document_id: str,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DocumentResponse]:
    """Get a single document."""
    doc = await service.DocumentService.get_document(
        db, ctx.clinic_id, _uuid.UUID(document_id)
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return ApiResponse(data=DocumentResponse.model_validate(doc))


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
    # current_user is injected via auth middleware; created_by comes from ctx
) -> ApiResponse[DocumentResponse]:
    """Create a new document."""
    doc = await service.DocumentService.create_document(
        db,
        ctx.clinic_id,
        patient_id=data.patient_id,
        document_type=data.document_type,
        title=data.title,
        content=data.content,
    )
    return ApiResponse(data=DocumentResponse.model_validate(doc))


@router.patch(
    "/{document_id}",
    response_model=ApiResponse[DocumentResponse],
)
async def update_document(
    document_id: str,
    data: DocumentUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DocumentResponse]:
    """Partial update of a document."""
    doc = await service.DocumentService.update_document(
        db,
        ctx.clinic_id,
        _uuid.UUID(document_id),
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
    document_id: str,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete (archive) a document."""
    deleted = await service.DocumentService.delete_document(
        db, ctx.clinic_id, _uuid.UUID(document_id)
    )
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
) -> ApiResponse[DocumentResponse]:
    """Generate (render) a document as a branded PDF.

    Marks the document as generated, stores the file path, and
    publishes ``DOCUMENT_GENERATED`` on the event bus.
    """
    doc = await service.DocumentService.generate_pdf(
        db, ctx.clinic_id, data.document_id
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return ApiResponse(data=DocumentResponse.model_validate(doc))
