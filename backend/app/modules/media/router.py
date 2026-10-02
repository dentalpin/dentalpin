"""FastAPI router for media module."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db
from app.modules.patients.service import PatientService

from .schemas import (
    AttachmentCreate,
    AttachmentResponse,
    DocumentBrief,
    DocumentResponse,
    DocumentUpdate,
    PhotoMetadataUpdate,
)
from .service import AttachmentService, DocumentService, PhotoService
from .thumbnails import MEDIUM_SUFFIX, THUMB_SUFFIX, is_thumbnailable
from .validation import (
    DOCUMENT_TYPES,
    validate_document_type,
    validate_file_size,
    validate_mime_type,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# URL helpers — keep all link construction in one place so we can swap to
# signed S3 URLs in a future module without touching call sites.
# ---------------------------------------------------------------------------


def _download_url(document_id: UUID, suffix: str = "") -> str:
    if suffix:
        return f"/api/v1/media/documents/{document_id}/download?variant={suffix}"
    return f"/api/v1/media/documents/{document_id}/download"


def _decorate(doc) -> DocumentResponse:
    """Build a DocumentResponse with thumb / medium / full URLs."""
    response = DocumentResponse.model_validate(doc)
    response.full_url = _download_url(doc.id)
    if is_thumbnailable(doc.mime_type) and doc.media_kind in {"photo", "xray"}:
        response.thumb_url = _download_url(doc.id, "thumb")
        response.medium_url = _download_url(doc.id, "medium")
    return response


def _safe_filename(name: str | None) -> str:
    """Strip header-breaking characters from a stored filename.

    The name comes from the uploader, so quotes, backslashes and control
    characters must never reach Content-Disposition verbatim (#560).
    """
    cleaned = "".join(c for c in (name or "") if c.isprintable() and c not in '"\\')
    return cleaned.strip() or "document"


# ---------------------------------------------------------------------------
# Document upload — generic / administrative path (PDFs, consent, ...).
# ---------------------------------------------------------------------------


@router.post(
    "/patients/{patient_id}/documents",
    response_model=ApiResponse[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    patient_id: UUID,
    file: Annotated[UploadFile, File()],
    document_type: Annotated[str, Form()],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    description: Annotated[str | None, Form(max_length=2000)] = None,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)] = None,
    _: Annotated[None, Depends(require_permission("media.documents.write"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> ApiResponse[DocumentResponse]:
    patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    validate_document_type(document_type)
    validate_file_size(file)
    mime_type = validate_mime_type(file)

    file_data = await file.read()

    document = await DocumentService.create_document(
        db=db,
        clinic_id=ctx.clinic_id,
        patient_id=patient_id,
        user_id=ctx.user_id,
        file_data=file_data,
        original_filename=file.filename or "document",
        mime_type=mime_type,
        document_type=document_type,
        title=title,
        description=description,
    )
    return ApiResponse(data=_decorate(document))


@router.get(
    "/patients/{patient_id}/documents",
    response_model=PaginatedApiResponse[DocumentResponse],
)
async def list_patient_documents(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("media.documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    document_type: str | None = Query(default=None),
    media_kind: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[DocumentResponse]:
    patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if document_type and document_type not in DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document type. Allowed: {', '.join(DOCUMENT_TYPES)}",
        )

    documents, total = await DocumentService.list_documents(
        db=db,
        clinic_id=ctx.clinic_id,
        patient_id=patient_id,
        document_type=document_type,
        media_kind=media_kind,
        page=page,
        page_size=page_size,
    )
    return PaginatedApiResponse(
        data=[_decorate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Photo-aware upload + gallery list.
# ---------------------------------------------------------------------------


@router.post(
    "/patients/{patient_id}/photos",
    response_model=ApiResponse[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_photo(
    patient_id: UUID,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    media_kind: Annotated[str, Form()] = "photo",
    media_category: Annotated[str | None, Form()] = None,
    media_subtype: Annotated[str | None, Form()] = None,
    captured_at: Annotated[datetime | None, Form()] = None,
    paired_document_id: Annotated[UUID | None, Form()] = None,
    description: Annotated[str | None, Form(max_length=2000)] = None,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)] = None,
    _: Annotated[None, Depends(require_permission("media.documents.write"))] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> ApiResponse[DocumentResponse]:
    """Upload a clinical photo / X-ray with taxonomy metadata.

    The standard ``/documents`` endpoint also writes Documents but this
    one wraps the photo-aware path: thumbnail generation, EXIF capture
    extraction, taxonomy validation, optional pair link.
    """
    patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    validate_file_size(file)
    mime_type = validate_mime_type(file)
    file_data = await file.read()

    document = await DocumentService.create_document(
        db=db,
        clinic_id=ctx.clinic_id,
        patient_id=patient_id,
        user_id=ctx.user_id,
        file_data=file_data,
        original_filename=file.filename or "photo",
        mime_type=mime_type,
        document_type="other",  # photos use the media_kind taxonomy instead
        title=title,
        description=description,
        media_kind=media_kind,
        media_category=media_category,
        media_subtype=media_subtype,
        captured_at=captured_at,
        paired_document_id=paired_document_id,
    )
    return ApiResponse(data=_decorate(document))


@router.get(
    "/patients/{patient_id}/photos",
    response_model=PaginatedApiResponse[DocumentResponse],
)
async def list_patient_photos(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("media.documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    media_kind: str | None = Query(default=None),
    media_category: str | None = Query(default=None),
    media_subtype: str | None = Query(default=None),
    captured_from: datetime | None = Query(default=None),
    captured_to: datetime | None = Query(default=None),
    pair_status: Literal["all", "paired", "unpaired"] = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=40, ge=1, le=200),
) -> PaginatedApiResponse[DocumentResponse]:
    patient = await PatientService.get_patient(db, ctx.clinic_id, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    documents, total = await PhotoService.list_photos(
        db=db,
        clinic_id=ctx.clinic_id,
        patient_id=patient_id,
        media_kind=media_kind,
        media_category=media_category,
        media_subtype=media_subtype,
        captured_from=captured_from,
        captured_to=captured_to,
        pair_status=pair_status,
        page=page,
        page_size=page_size,
    )
    return PaginatedApiResponse(
        data=[_decorate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Document detail / download / update / delete.
# ---------------------------------------------------------------------------


@router.get(
    "/documents/{document_id}",
    response_model=ApiResponse[DocumentResponse],
)
async def get_document(
    document_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("media.documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DocumentResponse]:
    document = await DocumentService.get_document(db, ctx.clinic_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return ApiResponse(data=_decorate(document))


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("media.documents.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    variant: Literal["thumb", "medium", "full"] = Query(default="full"),
) -> Response:
    document = await DocumentService.get_document(db, ctx.clinic_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    from .storage import get_storage_backend

    storage = get_storage_backend()
    base_path = document.storage_path

    path: str
    media_type: str
    if variant == "thumb" and is_thumbnailable(document.mime_type):
        path = f"{base_path}{THUMB_SUFFIX}"
        media_type = "image/jpeg"
    elif variant == "medium" and is_thumbnailable(document.mime_type):
        path = f"{base_path}{MEDIUM_SUFFIX}"
        media_type = "image/jpeg"
    else:
        path = base_path
        media_type = document.mime_type

    try:
        content = await storage.retrieve(path)
    except FileNotFoundError:
        # Variant not generated (e.g. pre-existing document); fall back to original.
        content = await storage.retrieve(base_path)
        media_type = document.mime_type

    headers = {"Content-Length": str(len(content))}
    if variant == "full":
        headers["Content-Disposition"] = (
            f'attachment; filename="{_safe_filename(document.original_filename)}"'
        )
    return Response(content=content, media_type=media_type, headers=headers)


@router.put(
    "/documents/{document_id}",
    response_model=ApiResponse[DocumentResponse],
)
async def update_document(
    document_id: UUID,
    data: DocumentUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("media.documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DocumentResponse]:
    document = await DocumentService.get_document(db, ctx.clinic_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    updated = await DocumentService.update_document(
        db, document, data.model_dump(exclude_unset=True)
    )
    return ApiResponse(data=_decorate(updated))


@router.patch(
    "/documents/{document_id}/photo-metadata",
    response_model=ApiResponse[DocumentResponse],
)
async def patch_photo_metadata(
    document_id: UUID,
    data: PhotoMetadataUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("media.documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DocumentResponse]:
    document = await DocumentService.get_document(db, ctx.clinic_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    updated = await PhotoService.update_metadata(
        db,
        document,
        media_category=data.media_category,
        media_subtype=data.media_subtype,
        captured_at=data.captured_at,
        tags=data.tags,
        paired_document_id=data.paired_document_id,
    )
    return ApiResponse(data=_decorate(updated))


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("media.documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    document = await DocumentService.get_document(db, ctx.clinic_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    await DocumentService.delete_document(db, document)


# ---------------------------------------------------------------------------
# Before / after pairing.
# ---------------------------------------------------------------------------


@router.post(
    "/documents/{document_id}/pair/{other_id}",
    response_model=ApiResponse[DocumentResponse],
)
async def pair_documents(
    document_id: UUID,
    other_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("media.documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DocumentResponse]:
    a, _b = await PhotoService.pair(db, ctx.clinic_id, document_id, other_id)
    await db.refresh(a, ["uploader"])
    return ApiResponse(data=_decorate(a))


@router.delete(
    "/documents/{document_id}/pair",
    response_model=ApiResponse[DocumentResponse],
)
async def unpair_document(
    document_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("media.documents.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DocumentResponse]:
    doc = await PhotoService.unpair(db, ctx.clinic_id, document_id)
    await db.refresh(doc, ["uploader"])
    return ApiResponse(data=_decorate(doc))


# ---------------------------------------------------------------------------
# Polymorphic attachments — generic owner registry.
# ---------------------------------------------------------------------------


@router.post(
    "/attachments",
    response_model=ApiResponse[AttachmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def link_attachment(
    data: AttachmentCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("media.attachments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AttachmentResponse]:
    attachment = await AttachmentService.link(
        db,
        clinic_id=ctx.clinic_id,
        document_id=data.document_id,
        owner_type=data.owner_type,
        owner_id=data.owner_id,
        display_order=data.display_order,
    )
    response = AttachmentResponse.model_validate(attachment)
    response.document = (
        DocumentBrief.model_validate(attachment.document)
        if attachment.document is not None
        else None
    )
    if attachment.document is not None and is_thumbnailable(attachment.document.mime_type):
        response.thumb_url = _download_url(attachment.document.id, "thumb")
    return ApiResponse(data=response)


@router.delete(
    "/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_attachment(
    attachment_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("media.attachments.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await AttachmentService.unlink(db, ctx.clinic_id, attachment_id)


@router.get(
    "/attachments",
    response_model=ApiResponse[list[AttachmentResponse]],
)
async def list_attachments(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("media.attachments.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_type: str = Query(...),
    owner_id: UUID = Query(...),
) -> ApiResponse[list[AttachmentResponse]]:
    attachments = await AttachmentService.list_by_owner(db, ctx.clinic_id, owner_type, owner_id)
    items: list[AttachmentResponse] = []
    for att in attachments:
        response = AttachmentResponse.model_validate(att)
        response.document = (
            DocumentBrief.model_validate(att.document) if att.document is not None else None
        )
        if att.document is not None and is_thumbnailable(att.document.mime_type):
            response.thumb_url = _download_url(att.document.id, "thumb")
        items.append(response)
    return ApiResponse(data=items)
