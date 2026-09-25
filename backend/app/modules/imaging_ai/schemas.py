"""Pydantic schemas for the imaging_ai module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AiJobQueueRequest(BaseModel):
    """Queue (or, unattributed, propose) an AI run over patient documents."""

    document_id: UUID
    series_document_ids: list[UUID] = Field(default_factory=list, max_length=500)
    backend: str = Field(default="pano", max_length=40)


class DicomDocumentResponse(BaseModel):
    """One DICOM candidate for the series picker."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    mime_type: str
    file_size: int
    created_at: datetime


class AiJobResponse(BaseModel):
    """AI job with lifecycle status, draft review, and artifact links."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    document_id: UUID
    series_document_ids: list
    backend: str
    model_id: str
    model_version: str
    status: str
    review_status: str
    confirmed_by: UUID | None
    confirmed_at: datetime | None
    queued_by: UUID | None = None
    log_excerpt: str | None
    error: str | None
    artifact_document_ids: list
    created_at: datetime
    updated_at: datetime
