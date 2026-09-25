"""Schemas for prescriptions."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PrescriptionItemCreate(BaseModel):
    medication_name: str = Field(min_length=1, max_length=150)
    catalog_ref: UUID | None = None
    dosage: str | None = Field(default=None, max_length=50)
    unit: str | None = Field(default=None, max_length=20)
    route: str | None = Field(default=None, max_length=50)
    frequency: str | None = Field(default=None, max_length=100)
    duration: str | None = Field(default=None, max_length=100)
    instructions: str | None = None
    sort_order: int = 0


class PrescriptionCreate(BaseModel):
    patient_id: UUID
    notes: str | None = None
    locale: str = Field(default="es", max_length=8)
    items: list[PrescriptionItemCreate] = Field(default_factory=list)


class PrescriptionUpdate(BaseModel):
    """Draft edits only; all-optional with exclude_unset (M4)."""

    notes: str | None = None
    locale: str | None = Field(default=None, max_length=8)
    items: list[PrescriptionItemCreate] | None = None


class PrescriptionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    medication_name: str
    catalog_ref: UUID | None
    dosage: str | None
    unit: str | None
    route: str | None
    frequency: str | None
    duration: str | None
    instructions: str | None
    sort_order: int


class PrescriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    prescriber_id: UUID
    status: str
    issued_at: datetime | None
    notes: str | None
    locale: str
    prescriber_name: str | None
    license_number: str | None
    compliance_data: dict
    items: list[PrescriptionItemResponse] = []


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    items: list[PrescriptionItemCreate] = Field(default_factory=list)


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    items: list[PrescriptionItemCreate] | None = None


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    items: list


class PrescriberProfileUpsert(BaseModel):
    license_number: str | None = Field(default=None, max_length=100)
    signature_document_id: UUID | None = None


class PrescriberProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    license_number: str | None
    signature_document_id: UUID | None


class PrescribeWarnings(BaseModel):
    allergies: list[str] = []
    interaction_flags: list[str] = []
