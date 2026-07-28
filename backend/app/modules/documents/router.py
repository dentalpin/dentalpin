"""Documents HTTP surface. Mounted under ``/api/v1/documents/*`` by the
module system (prefix comes from `manifest["name"]`, not from `APIRouter(...)`
itself — matches the confirmed real pattern used by inventory/router.py)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.database import get_db

from .schemas import (
    CertificateCreate,
    GeneratedDocumentList,
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
# Letterhead is clinic-wide settings (the template itself), not module
# content, so its write uses the clinic-settings permission — same tier
# as budget/communications settings endpoints — not a module-specific one.
# ---------------------------------------------------------------------------

@router.get("/letterhead", response_model=LetterheadRead | None)
async def get_letterhead(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await LetterheadService.get(db, ctx.clinic_id)


@router.put("/letterhead", response_model=LetterheadRead)
async def upsert_letterhead(
    data: LetterheadCreate | LetterheadUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.clinic.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await LetterheadService.upsert(db, ctx.clinic_id, data)


# ---------------------------------------------------------------------------
# Document creation — bug #1: list/create routes MUST be "/" not ""
# ---------------------------------------------------------------------------

@router.post("/prescription", response_model=GeneratedDocumentRead)
async def create_prescription(
    data: PrescriptionCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await DocumentService.create_prescription(db, ctx.clinic_id, ctx.user_id, data)


@router.post("/certificate", response_model=GeneratedDocumentRead)
async def create_certificate(
    data: CertificateCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await DocumentService.create_certificate(db, ctx.clinic_id, ctx.user_id, data)


@router.post("/referral", response_model=GeneratedDocumentRead)
async def create_referral(
    data: ReferralCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await DocumentService.create_referral(db, ctx.clinic_id, ctx.user_id, data)


@router.post("/radiology-request", response_model=GeneratedDocumentRead)
async def create_radiology_request(
    data: RadiologyRequestCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await DocumentService.create_radiology_request(db, ctx.clinic_id, ctx.user_id, data)


# ---------------------------------------------------------------------------
# List / retrieve / download — all read-only, documents.read
# ---------------------------------------------------------------------------

@router.get("/", response_model=GeneratedDocumentList)
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
    return GeneratedDocumentList(items=items, total=total)


@router.get("/{doc_id}", response_model=GeneratedDocumentRead)
async def get_document(
    doc_id: uuid.UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    doc = await DocumentService.get(db, ctx.clinic_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


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

    pdf_bytes = await DocumentPDFService.generate_pdf(doc.content_html)
    filename = f"{doc.document_type}_{doc.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
