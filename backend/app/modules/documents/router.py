"""Documents HTTP surface. Mounted under ``/api/v1/documents/*`` by the
module system (prefix comes from `manifest["name"]`, not from `APIRouter(...)`
itself — matches the confirmed real pattern used by inventory/router.py).

Every response wraps its payload in ApiResponse/PaginatedApiResponse,
matching the confirmed real convention from medications/router.py
(`ApiResponse(data=...)` for single objects, `PaginatedApiResponse(...)`
for lists). The module previously returned bare objects, which silently
broke the frontend (it always expects `.data`) — that mismatch was the
actual root cause of "PDF won't generate": the frontend read
`doc.data` off a response that had no `.data` key at all.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    CertificateCreate,
    GeneratedDocumentRead,
    LetterheadCreate,
    LetterheadRead,
    LetterheadUpdate,
    PrescriptionCreate,
    RadiologyRequestCreate,
    ReferralCreate,
)
from .service import DocumentPDFService, DocumentService, LetterheadService

router = APIRouter()


# ---------------------------------------------------------------------------
# Letterhead — read is documents.read, write is admin.clinic.write (clinic-
# wide settings, not module content — same tier as budget/communications
# settings; see PHASE14_INSTALL_GUIDE.md for why).
# ---------------------------------------------------------------------------

@router.get("/letterhead", response_model=ApiResponse[LetterheadRead | None])
async def get_letterhead(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    letterhead = await LetterheadService.get(db, ctx.clinic_id)
    return ApiResponse(data=LetterheadRead.model_validate(letterhead) if letterhead else None)


@router.put("/letterhead", response_model=ApiResponse[LetterheadRead])
async def upsert_letterhead(
    data: LetterheadCreate | LetterheadUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.clinic.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    letterhead = await LetterheadService.upsert(db, ctx.clinic_id, data)
    return ApiResponse(data=LetterheadRead.model_validate(letterhead))


# ---------------------------------------------------------------------------
# Document creation — bug #1: list/create routes MUST be "/" not ""
# ---------------------------------------------------------------------------

@router.post("/prescription", response_model=ApiResponse[GeneratedDocumentRead])
async def create_prescription(
    data: PrescriptionCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    doc = await DocumentService.create_prescription(db, ctx.clinic_id, ctx.user_id, data)
    return ApiResponse(data=GeneratedDocumentRead.model_validate(doc))


@router.post("/certificate", response_model=ApiResponse[GeneratedDocumentRead])
async def create_certificate(
    data: CertificateCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    doc = await DocumentService.create_certificate(db, ctx.clinic_id, ctx.user_id, data)
    return ApiResponse(data=GeneratedDocumentRead.model_validate(doc))


@router.post("/referral", response_model=ApiResponse[GeneratedDocumentRead])
async def create_referral(
    data: ReferralCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    doc = await DocumentService.create_referral(db, ctx.clinic_id, ctx.user_id, data)
    return ApiResponse(data=GeneratedDocumentRead.model_validate(doc))


@router.post("/radiology-request", response_model=ApiResponse[GeneratedDocumentRead])
async def create_radiology_request(
    data: RadiologyRequestCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    doc = await DocumentService.create_radiology_request(db, ctx.clinic_id, ctx.user_id, data)
    return ApiResponse(data=GeneratedDocumentRead.model_validate(doc))


# ---------------------------------------------------------------------------
# List / retrieve / download — all read-only, documents.read
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedApiResponse[GeneratedDocumentRead])
async def list_documents(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    document_type: str | None = None,
    patient_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
):
    items, total = await DocumentService.list(
        db, ctx.clinic_id, document_type=document_type, patient_id=patient_id,
        limit=limit, offset=offset,
    )
    # PaginatedApiResponse uses page/page_size — offset/limit map onto them
    # (page_size == limit; page derived from offset) so the shape matches
    # the confirmed convention without changing this module's own filters.
    page_size = limit or 1
    page = (offset // page_size) + 1
    return PaginatedApiResponse(
        data=[GeneratedDocumentRead.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{doc_id}", response_model=ApiResponse[GeneratedDocumentRead])
async def get_document(
    doc_id: uuid.UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    doc = await DocumentService.get(db, ctx.clinic_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return ApiResponse(data=GeneratedDocumentRead.model_validate(doc))


@router.get("/{doc_id}/pdf")
async def download_pdf(
    doc_id: uuid.UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    doc = await DocumentService.get(db, ctx.clinic_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Binary response — NOT wrapped in ApiResponse, matches confirmed
    # pattern (media/PDF downloads elsewhere return raw Response too).
    pdf_bytes = await DocumentPDFService.generate_pdf(doc.content_html)
    filename = f"{doc.document_type}_{doc.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
