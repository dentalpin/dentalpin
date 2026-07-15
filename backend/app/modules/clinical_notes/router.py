"""Clinical notes module API endpoints.

All routes are mounted at ``/api/v1/clinical_notes/`` by the plugin loader.

Attachment CRUD lives in the ``media`` module since issue #55 — clients
should call ``/api/v1/media/attachments`` directly. We keep one
read-only convenience endpoint (``GET /attachments``) to honor existing
frontend code paths during the transition; create/delete moved away.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from .models import ClinicalNote
from .schemas import (
    NOTE_OWNER_PATTERN,
    ClinicalNoteCreate,
    ClinicalNoteEntry,
    ClinicalNoteResponse,
    ClinicalNoteUpdate,
    NoteAttachmentResponse,
    NoteTemplateResponse,
    PlanNotesGroup,
    RecentNoteEntry,
)
from .service import (
    AttachmentPatientMismatchError,
    NoteOwnerError,
    NoteService,
    count_notes_for_owners,
    list_attachments_for_note,
    list_attachments_for_owner,
    list_grouped_for_patient,
    list_merged_for_plan,
    list_recent_for_patient,
    resolve_owner_patient,
)

router = APIRouter()

ATTACHMENT_OWNER_PATTERN = "^(patient|treatment|plan|appointment|clinical_note)$"


def _is_admin_role(ctx: ClinicContext) -> bool:
    return ctx.role == "admin"


_THUMBNAILABLE = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "image/gif",
}


def _decorate_attachment(att) -> NoteAttachmentResponse:
    """Project a MediaAttachment + its loaded document into a response.

    URL templates mirror media's own decorator. They live as plain
    strings here so we don't import a private helper from media — the
    only contract we depend on is the public download endpoint shape.
    """
    response = NoteAttachmentResponse.model_validate(att)
    doc = att.document
    if doc is not None:
        response.title = doc.title
        response.mime_type = doc.mime_type
        response.media_kind = doc.media_kind
        base = f"/api/v1/media/documents/{doc.id}/download"
        response.full_url = base
        if doc.mime_type in _THUMBNAILABLE and doc.media_kind in ("photo", "xray"):
            response.thumb_url = f"{base}?variant=thumb"
            response.medium_url = f"{base}?variant=medium"
    return response


def _author_brief_from(note: ClinicalNote) -> dict | None:
    """Project the loaded ``author`` relationship into an AuthorBrief shape."""
    author = getattr(note, "author", None)
    if author is None:
        return None
    full_name = (
        getattr(author, "full_name", None)
        or " ".join(
            filter(
                None,
                [getattr(author, "first_name", None), getattr(author, "last_name", None)],
            )
        ).strip()
        or None
    )
    return {
        "id": author.id,
        "full_name": full_name,
        "email": getattr(author, "email", None),
    }


async def _decorate_note(
    db: AsyncSession, clinic_id: UUID, note: ClinicalNote
) -> ClinicalNoteResponse:
    """Build a ClinicalNoteResponse with attachments fetched from media."""
    response = ClinicalNoteResponse.model_validate(note)
    attachments = await list_attachments_for_note(db, clinic_id, note.id)
    response.attachments = [_decorate_attachment(a) for a in attachments]
    author_brief = _author_brief_from(note)
    if author_brief is not None:
        from .schemas import AuthorBrief

        response.author = AuthorBrief.model_validate(author_brief)
    return response


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


@router.get(
    "/notes",
    response_model=ApiResponse[list[ClinicalNoteResponse]],
)
async def list_notes(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("clinical_notes.notes.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_type: str = Query(..., pattern=NOTE_OWNER_PATTERN),
    owner_id: UUID = Query(...),
) -> ApiResponse[list[ClinicalNoteResponse]]:
    """List clinical notes for a single owner (patient / treatment / plan)."""
    try:
        await resolve_owner_patient(db, ctx.clinic_id, owner_type, owner_id)
        notes = await NoteService.list_for_owner(db, ctx.clinic_id, owner_type, owner_id)
    except NoteOwnerError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    decorated = [await _decorate_note(db, ctx.clinic_id, n) for n in notes]
    return ApiResponse(data=decorated)


@router.post(
    "/notes",
    response_model=ApiResponse[ClinicalNoteResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_note(
    data: ClinicalNoteCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("clinical_notes.notes.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ClinicalNoteResponse]:
    """Create a clinical note. Owner must exist in the same clinic."""
    try:
        note = await NoteService.create(
            db,
            clinic_id=ctx.clinic_id,
            user_id=ctx.user_id,
            note_type=data.note_type,
            owner_type=data.owner_type,
            owner_id=data.owner_id,
            body=data.body,
            tooth_number=data.tooth_number,
            attachment_document_ids=data.attachment_document_ids,
        )
    except NoteOwnerError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AttachmentPatientMismatchError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ApiResponse(data=await _decorate_note(db, ctx.clinic_id, note))


@router.patch(
    "/notes/{note_id}",
    response_model=ApiResponse[ClinicalNoteResponse],
)
async def update_note(
    note_id: UUID,
    data: ClinicalNoteUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("clinical_notes.notes.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ClinicalNoteResponse]:
    """Edit a note body. Author or admin only."""
    try:
        note = await NoteService.update(
            db,
            clinic_id=ctx.clinic_id,
            note_id=note_id,
            body=data.body,
            user_id=ctx.user_id,
            is_admin=_is_admin_role(ctx),
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return ApiResponse(data=await _decorate_note(db, ctx.clinic_id, note))


@router.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_note(
    note_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("clinical_notes.notes.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete a note. Author or admin only."""
    try:
        ok = await NoteService.soft_delete(
            db,
            clinic_id=ctx.clinic_id,
            note_id=note_id,
            user_id=ctx.user_id,
            is_admin=_is_admin_role(ctx),
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")


@router.get(
    "/notes/counts",
    response_model=ApiResponse[dict[str, int]],
)
async def count_notes_by_owner(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("clinical_notes.notes.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_type: str = Query(..., pattern=NOTE_OWNER_PATTERN),
    owner_ids: list[UUID] = Query(..., min_length=1, max_length=500),
) -> ApiResponse[dict[str, int]]:
    """Bulk note counts per owner_id. Used by callers that render a
    "has notes" indicator next to a list of entities (e.g. the agenda
    weekly/daily/kanban views) without fetching each note body.
    """
    counts = await count_notes_for_owners(db, ctx.clinic_id, owner_type, owner_ids)
    return ApiResponse(data={str(k): v for k, v in counts.items()})


# ---------------------------------------------------------------------------
# Attachments — read-only convenience that proxies media. New code should
# call /api/v1/media/attachments directly.
# ---------------------------------------------------------------------------


@router.get(
    "/attachments",
    response_model=ApiResponse[list[NoteAttachmentResponse]],
)
async def list_attachments(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("clinical_notes.notes.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_type: str = Query(..., pattern=ATTACHMENT_OWNER_PATTERN),
    owner_id: UUID = Query(...),
) -> ApiResponse[list[NoteAttachmentResponse]]:
    """Proxy of media's attachment list — kept for transitional callers."""
    try:
        rows = await list_attachments_for_owner(db, ctx.clinic_id, owner_type, owner_id)
    except NoteOwnerError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ApiResponse(data=[NoteAttachmentResponse.model_validate(r) for r in rows])


# ---------------------------------------------------------------------------
# Aggregate feeds
# ---------------------------------------------------------------------------


@router.get(
    "/patients/{patient_id}/recent",
    response_model=ApiResponse[list[RecentNoteEntry]],
)
async def list_patient_recent_notes(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("clinical_notes.notes.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    types: list[str] | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    before: datetime | None = Query(default=None),
) -> ApiResponse[list[RecentNoteEntry]]:
    """Recent notes for a patient — feed for the Summary tab."""
    from .models import NOTE_TYPES

    if types:
        invalid = [t for t in types if t not in NOTE_TYPES]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown note_type values: {invalid}",
            )
    try:
        entries = await list_recent_for_patient(
            db,
            clinic_id=ctx.clinic_id,
            patient_id=patient_id,
            note_types=types,
            limit=limit,
            before=before,
        )
    except NoteOwnerError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    for e in entries:
        e["attachments"] = [_decorate_attachment(a) for a in e["attachments"]]
    return ApiResponse(data=[RecentNoteEntry.model_validate(e) for e in entries])


@router.get(
    "/patients/{patient_id}/by-plan",
    response_model=ApiResponse[list[PlanNotesGroup]],
)
async def list_patient_clinical_notes_by_plan(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("clinical_notes.notes.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[PlanNotesGroup]]:
    """Clinical notes grouped by plan → treatment for one patient."""
    groups = await list_grouped_for_patient(db, ctx.clinic_id, patient_id)
    for g in groups:
        for entry in g.get("plan_notes", []):
            entry["attachments"] = [_decorate_attachment(a) for a in entry["attachments"]]
        for tg in g.get("treatments", []):
            for entry in tg.get("notes", []):
                entry["attachments"] = [_decorate_attachment(a) for a in entry["attachments"]]
    return ApiResponse(data=[PlanNotesGroup.model_validate(g) for g in groups])


@router.get(
    "/treatment-plans/{plan_id}/merged",
    response_model=ApiResponse[list[ClinicalNoteEntry]],
)
async def list_plan_merged_clinical_notes(
    plan_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("clinical_notes.notes.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[ClinicalNoteEntry]]:
    """Merged clinical-notes feed for a plan (plan + treatment + visit)."""
    entries = await list_merged_for_plan(db, ctx.clinic_id, plan_id)
    for e in entries:
        e["attachments"] = [_decorate_attachment(a) for a in e["attachments"]]
    return ApiResponse(data=[ClinicalNoteEntry.model_validate(e) for e in entries])


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


@router.get(
    "/note-templates",
    response_model=ApiResponse[list[NoteTemplateResponse]],
)
async def list_note_templates(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("clinical_notes.notes.read"))],
    category: str | None = Query(default=None),
) -> ApiResponse[list[NoteTemplateResponse]]:
    """Return static template catalog, optionally filtered by category."""
    from .note_templates import NOTE_TEMPLATES, list_templates

    entries: list[NoteTemplateResponse] = []
    if category:
        for tpl in list_templates(category):
            entries.append(
                NoteTemplateResponse(
                    id=tpl["id"],
                    category=category,
                    i18n_key=tpl["i18n_key"],
                    body_i18n_key=tpl["body_i18n_key"],
                    body=tpl["body"],
                )
            )
    else:
        for cat, bucket in NOTE_TEMPLATES.items():
            for tpl in bucket:
                entries.append(
                    NoteTemplateResponse(
                        id=tpl["id"],
                        category=cat,
                        i18n_key=tpl["i18n_key"],
                        body_i18n_key=tpl["body_i18n_key"],
                        body=tpl["body"],
                    )
                )
    return ApiResponse(data=entries)
