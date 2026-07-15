"""Clinical notes module Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import (
    NOTE_OWNER_APPOINTMENT,
    NOTE_OWNER_PATIENT,
    NOTE_OWNER_PLAN,
    NOTE_OWNER_TREATMENT,
    NOTE_OWNER_TYPES,
    NOTE_TYPE_ADMINISTRATIVE,
    NOTE_TYPE_APPOINTMENT_ADMINISTRATIVE,
    NOTE_TYPE_APPOINTMENT_CLINICAL,
    NOTE_TYPE_DIAGNOSIS,
    NOTE_TYPE_TREATMENT,
    NOTE_TYPE_TREATMENT_PLAN,
    NOTE_TYPES,
)

NOTE_TYPE_PATTERN = (
    "^(administrative|diagnosis|treatment|treatment_plan"
    "|appointment_clinical|appointment_administrative)$"
)
NOTE_OWNER_PATTERN = "^(patient|treatment|plan|appointment)$"


# ---------------------------------------------------------------------------
# Attachments — projected from media.MediaAttachment for backwards-compatible
# response shape (`note_id` is no longer a column; it's reconstructed on the
# rare path where a caller still cares).
# ---------------------------------------------------------------------------


class NoteAttachmentResponse(BaseModel):
    """Response for a single attachment (projected from MediaAttachment).

    The document brief + signed URLs are populated by the router so the
    UI can render inline image previews and open the lightbox without a
    second round-trip.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    owner_type: str
    owner_id: UUID
    display_order: int
    created_at: datetime

    # Document brief (optional for transitional callers that don't decorate).
    title: str | None = None
    mime_type: str | None = None
    media_kind: str | None = None
    thumb_url: str | None = None
    medium_url: str | None = None
    full_url: str | None = None


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


_TYPE_OWNER_MATRIX: dict[str, str] = {
    NOTE_TYPE_ADMINISTRATIVE: NOTE_OWNER_PATIENT,
    NOTE_TYPE_DIAGNOSIS: NOTE_OWNER_PATIENT,
    NOTE_TYPE_TREATMENT: NOTE_OWNER_TREATMENT,
    NOTE_TYPE_TREATMENT_PLAN: NOTE_OWNER_PLAN,
    NOTE_TYPE_APPOINTMENT_CLINICAL: NOTE_OWNER_APPOINTMENT,
    NOTE_TYPE_APPOINTMENT_ADMINISTRATIVE: NOTE_OWNER_APPOINTMENT,
}


class ClinicalNoteCreate(BaseModel):
    """Create a clinical note.

    The combination of ``note_type`` and ``owner_type`` is constrained by the
    DB CHECK and validated up front here so the API rejects bad pairings with
    a clear 422 instead of a generic integrity error.
    """

    note_type: str = Field(..., pattern=NOTE_TYPE_PATTERN)
    owner_type: str = Field(..., pattern=NOTE_OWNER_PATTERN)
    owner_id: UUID
    tooth_number: int | None = Field(default=None, ge=11, le=85)
    body: str = Field(..., min_length=1)
    attachment_document_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_matrix(self) -> "ClinicalNoteCreate":
        expected_owner = _TYPE_OWNER_MATRIX.get(self.note_type)
        if expected_owner and self.owner_type != expected_owner:
            raise ValueError(f"note_type={self.note_type!r} requires owner_type={expected_owner!r}")
        if self.tooth_number is not None and self.note_type != NOTE_TYPE_DIAGNOSIS:
            raise ValueError("tooth_number is only allowed for note_type='diagnosis'")
        return self


class ClinicalNoteUpdate(BaseModel):
    """Edit a note body. Author or admin only."""

    body: str = Field(..., min_length=1)


class ClinicalNoteResponse(BaseModel):
    """Response for a single clinical note."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    note_type: str
    owner_type: str
    owner_id: UUID
    tooth_number: int | None
    body: str
    author_id: UUID
    author: "AuthorBrief | None" = None
    created_at: datetime
    updated_at: datetime
    attachments: list[NoteAttachmentResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Aggregate / feed schemas
# ---------------------------------------------------------------------------


class AuthorBrief(BaseModel):
    """Brief author info (denormalized into recent feed entries)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str | None = None
    email: str | None = None


# Resolve forward reference declared on ClinicalNoteResponse.author.
ClinicalNoteResponse.model_rebuild()


class LinkedEntityBrief(BaseModel):
    """Lightweight descriptor of the owner — surfaced as a chip in the feed."""

    kind: str  # 'patient' | 'treatment' | 'plan'
    id: UUID | None = None
    label: str | None = None
    tooth_number: int | None = None


class RecentNoteEntry(BaseModel):
    """One row in the patient summary recent-notes feed."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    note_type: str
    owner_type: str
    owner_id: UUID
    tooth_number: int | None
    body: str
    created_at: datetime
    updated_at: datetime
    author: AuthorBrief
    linked: LinkedEntityBrief
    attachments: list[NoteAttachmentResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Plan-grouped feed
# ---------------------------------------------------------------------------


class ClinicalNoteEntry(BaseModel):
    """Merged-feed entry covering plan / treatment / visit notes for a plan."""

    source: str  # 'plan' | 'treatment' | 'visit'
    note_id: UUID | None
    owner_id: UUID
    plan_item_id: UUID | None = None
    body: str
    author_id: UUID | None
    author: AuthorBrief | None = None
    created_at: datetime
    updated_at: datetime | None = None
    attachments: list[NoteAttachmentResponse] = Field(default_factory=list)


class PlanSummary(BaseModel):
    """Minimal plan info inlined in the grouped feed."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_number: str
    title: str | None = None
    status: str
    created_at: datetime


class PlanItemSummary(BaseModel):
    """Minimal plan-item descriptor surfaced in the grouped feed."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    treatment_id: UUID
    sequence_order: int
    status: str
    label: str | None = None
    teeth: list[int] = Field(default_factory=list)


class PlanItemNotesGroup(BaseModel):
    plan_item: PlanItemSummary
    notes: list[ClinicalNoteEntry] = Field(default_factory=list)


class PlanNotesGroup(BaseModel):
    plan: PlanSummary
    plan_notes: list[ClinicalNoteEntry] = Field(default_factory=list)
    treatments: list[PlanItemNotesGroup] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class NoteTemplateResponse(BaseModel):
    id: str
    category: str
    i18n_key: str
    body_i18n_key: str
    body: str


__all__ = [
    "AuthorBrief",
    "ClinicalNoteCreate",
    "ClinicalNoteEntry",
    "ClinicalNoteResponse",
    "ClinicalNoteUpdate",
    "LinkedEntityBrief",
    "NOTE_OWNER_PATTERN",
    "NOTE_OWNER_TYPES",
    "NOTE_TYPES",
    "NOTE_TYPE_PATTERN",
    "NoteAttachmentResponse",
    "NoteTemplateResponse",
    "PlanItemNotesGroup",
    "PlanItemSummary",
    "PlanNotesGroup",
    "PlanSummary",
    "RecentNoteEntry",
]
