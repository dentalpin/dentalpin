import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentType = Literal["prescription", "certificate", "referral", "radiology_request"]


# ---------------------------------------------------------------------------
# Letterhead
# ---------------------------------------------------------------------------

class LetterheadBase(BaseModel):
    practice_name: str
    legal_name: str | None = None
    address: dict | None = None
    phone: str | None = None
    email: str | None = None
    logo_url: str | None = None
    registration_number: str | None = None
    footer_text: str | None = None


class LetterheadCreate(LetterheadBase):
    pass


class LetterheadUpdate(BaseModel):
    practice_name: str | None = None
    legal_name: str | None = None
    address: dict | None = None
    phone: str | None = None
    email: str | None = None
    logo_url: str | None = None
    registration_number: str | None = None
    footer_text: str | None = None


class LetterheadRead(LetterheadBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clinic_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Prescription — free-text drug name for now (Phase 9 will swap to FK later)
# ---------------------------------------------------------------------------

class PrescriptionItem(BaseModel):
    drug_name: str  # snapshot at prescribing time — kept even if the
    # catalog entry is later edited/deleted, so a past prescription
    # stays reproducible. Auto-filled from the catalog pick on the
    # frontend but still editable before submit.
    dosage: str
    instructions: str
    quantity: str | None = None
    medication_id: uuid.UUID | None = None  # Phase 9 catalog reference, optional


class PrescriptionCreate(BaseModel):
    patient_id: uuid.UUID
    items: list[PrescriptionItem] = Field(min_length=1)
    notes: str | None = None


# ---------------------------------------------------------------------------
# Certificate
# ---------------------------------------------------------------------------

CertificateType = Literal["work_absence", "school_absence", "fitness_for_work"]


class CertificateCreate(BaseModel):
    patient_id: uuid.UUID
    certificate_type: CertificateType
    start_date: date
    end_date: date | None = None
    reason: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Referral letter
# ---------------------------------------------------------------------------

class ReferralCreate(BaseModel):
    patient_id: uuid.UUID
    specialist_name: str
    specialty: str
    reason: str
    clinical_history: str | None = None
    urgency: Literal["routine", "urgent"] = "routine"


# ---------------------------------------------------------------------------
# Radiology request
# ---------------------------------------------------------------------------

class RadiologyRequestCreate(BaseModel):
    patient_id: uuid.UUID
    exam_type: str
    tooth_reference: str | None = None
    clinical_indication: str
    notes: str | None = None


# ---------------------------------------------------------------------------
# Generated document (read model)
# ---------------------------------------------------------------------------

class GeneratedDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clinic_id: uuid.UUID
    patient_id: uuid.UUID
    created_by: uuid.UUID
    document_type: DocumentType
    title: str
    payload: dict
    file_path: str | None = None
    created_at: datetime


class GeneratedDocumentList(BaseModel):
    items: list[GeneratedDocumentRead]
    total: int
