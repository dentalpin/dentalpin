"""Pydantic schemas for the documents module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID


# ---------------------------------------------------------------------------
# Create / Update schemas
# ---------------------------------------------------------------------------

class MedicationItem(BaseModel):
    """A single medication line in a prescription."""

    name: str
    dose: str = ""
    frequency: str = ""
    duration: str = ""
    notes: str = ""


class PrescriptionContent(BaseModel):
    """Content payload for a prescription document."""

    diagnosis: str = ""
    medications: list[MedicationItem] = Field(default_factory=list)
    notes: str = ""


class MedicalCertificateContent(BaseModel):
    """Content payload for a medical certificate."""

    diagnosis: str = ""
    description: str = ""
    recommendations: str = ""
    valid_from: date | None = None
    valid_until: date | None = None


class ReferralContent(BaseModel):
    """Content payload for a referral letter."""

    referred_to: str = ""
    specialty: str = ""
    reason: str = ""
    clinical_summary: str = ""
    notes: str = ""


class RadiologyRequestContent(BaseModel):
    """Content payload for a radiology request."""

    exam_type: str = ""
    region: str = ""
    clinical_question: str = ""
    notes: str = ""


class DocumentCreate(BaseModel):
    """Schema for creating a new document."""

    patient_id: UUID
    document_type: Literal[
        "prescription",
        "medical_certificate",
        "referral",
        "radiology_request",
    ]
    title: str = Field(..., max_length=200)
    content: dict = Field(default_factory=dict)


class DocumentUpdate(BaseModel):
    """Schema for updating an existing document (partial)."""

    title: str | None = Field(default=None, max_length=200)
    content: dict | None = None
    status: Literal["draft", "generated", "archived"] | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class DocumentResponse(BaseModel):
    """Schema returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    document_type: str
    title: str
    status: str
    content: dict
    file_path: str | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class DocumentGenerateRequest(BaseModel):
    """Request to generate (render) a document as PDF."""

    document_id: UUID
