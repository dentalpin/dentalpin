"""Pydantic schemas for the imaging_ai module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AiJobQueueRequest(BaseModel):
    """Queue an AI run over a study's document bytes."""

    study_id: UUID
    document_id: UUID
    backend: str = Field(default="nnunet", max_length=40)


class AiJobResponse(BaseModel):
    """AI job with lifecycle status and artifact links."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    study_id: UUID
    document_id: UUID
    backend: str
    model_id: str
    model_version: str
    status: str
    log_excerpt: str | None
    error: str | None
    artifact_document_ids: list
    created_at: datetime
    updated_at: datetime
