"""Pydantic schemas for the imaging_viewer module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StudyIndexRequest(BaseModel):
    """Index an existing media document as a viewable DICOM study."""

    document_id: UUID
    study_uid: str | None = Field(default=None, max_length=128)
    modality: str | None = Field(default=None, max_length=16)


class ImagingStudyResponse(BaseModel):
    """Viewable DICOM study with extracted tags."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    document_id: UUID
    study_uid: str
    modality: str | None
    study_date: datetime | None
    dicom_metadata: dict
    status: str
    created_at: datetime
    updated_at: datetime


class RvgImportResponse(BaseModel):
    """One RVG watch-folder file and its queue state."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID | None
    document_id: UUID | None
    study_id: UUID | None
    filename: str
    identity_tags: dict
    suggested_patient_id: UUID | None
    match_score: int | None
    match_reason: str | None
    status: str
    error: str | None
    created_at: datetime
    updated_at: datetime


class RvgApproveRequest(BaseModel):
    """Approve a pending import for an explicit patient (link stored)."""

    patient_id: UUID


class RvgRejectRequest(BaseModel):
    """Reject a pending import, keeping the row for audit."""

    reason: str | None = Field(default=None, max_length=500)


class RvgScanRequest(BaseModel):
    """Trigger a watch-dir scan now (scheduler-independent)."""

    retry_failed: bool = False


class RvgLinkResponse(BaseModel):
    """Approved DICOM-identity → patient binding."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    dicom_patient_id: str
    created_at: datetime
    updated_at: datetime


class AnnotationCreateRequest(BaseModel):
    """Save a human overlay: ruler (2 pts), freehand (2-500 pts), note (text)."""

    kind: str = Field(max_length=20)
    payload: dict


class AnnotationResponse(BaseModel):
    """Stored overlay with server-computed mm (ruler + spacing only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    study_id: UUID
    kind: str
    payload: dict
    spacing_mm: float | None
    status: str
    created_at: datetime
    updated_at: datetime
