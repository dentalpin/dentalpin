"""Pydantic schemas for the patients_clinical module."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# --- Medical context -----------------------------------------------------


class MedicalContextBase(BaseModel):
    is_pregnant: bool = False
    pregnancy_week: int | None = Field(default=None, ge=1, le=42)
    is_lactating: bool = False

    is_on_anticoagulants: bool = False
    anticoagulant_medication: str | None = Field(default=None, max_length=100)
    inr_value: float | None = Field(default=None, ge=0, le=20)
    last_inr_date: date | None = None

    is_smoker: bool = False
    smoking_frequency: str | None = Field(default=None, max_length=100)
    alcohol_consumption: str | None = Field(default=None, max_length=100)

    bruxism: bool = False

    adverse_reactions_to_anesthesia: bool = False
    anesthesia_reaction_details: str | None = Field(default=None, max_length=500)


class MedicalContextUpdate(MedicalContextBase):
    pass


class MedicalContextResponse(MedicalContextBase):
    last_updated_at: datetime | None = None
    last_updated_by: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Allergy ------------------------------------------------------------


class AllergyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str | None = Field(default=None, max_length=50)
    severity: str = Field(default="medium", max_length=20)
    reaction: str | None = Field(default=None, max_length=500)
    notes: str | None = None
    reference_id: UUID | None = None


class AllergyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: str | None = Field(default=None, max_length=50)
    severity: str | None = Field(default=None, max_length=20)
    reaction: str | None = Field(default=None, max_length=500)
    notes: str | None = None
    reference_id: UUID | None = None


class AllergyResponse(AllergyCreate):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


# --- Medication ---------------------------------------------------------


class MedicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dosage: str | None = Field(default=None, max_length=100)
    frequency: str | None = Field(default=None, max_length=100)
    start_date: date | None = None
    notes: str | None = None
    reference_id: UUID | None = None


class MedicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    dosage: str | None = Field(default=None, max_length=100)
    frequency: str | None = Field(default=None, max_length=100)
    start_date: date | None = None
    notes: str | None = None
    reference_id: UUID | None = None


class MedicationResponse(MedicationCreate):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


# --- Systemic disease ---------------------------------------------------


class SystemicDiseaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str | None = Field(default=None, max_length=50)
    diagnosis_date: date | None = None
    is_controlled: bool = True
    is_critical: bool = False
    medications: str | None = None
    notes: str | None = None
    reference_id: UUID | None = None


class SystemicDiseaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: str | None = Field(default=None, max_length=50)
    diagnosis_date: date | None = None
    is_controlled: bool | None = None
    is_critical: bool | None = None
    medications: str | None = None
    notes: str | None = None
    reference_id: UUID | None = None


class SystemicDiseaseResponse(SystemicDiseaseCreate):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


# --- Surgical history ---------------------------------------------------


class SurgicalHistoryCreate(BaseModel):
    procedure: str = Field(min_length=1, max_length=200)
    surgery_date: date | None = None
    complications: str | None = None
    notes: str | None = None
    reference_id: UUID | None = None


class SurgicalHistoryUpdate(BaseModel):
    procedure: str | None = Field(default=None, min_length=1, max_length=200)
    surgery_date: date | None = None
    complications: str | None = None
    notes: str | None = None
    reference_id: UUID | None = None


class SurgicalHistoryResponse(SurgicalHistoryCreate):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


# --- Emergency contact --------------------------------------------------


class EmergencyContactBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    relationship: str | None = Field(default=None, max_length=50)
    phone: str = Field(min_length=1, max_length=20)
    email: EmailStr | None = None
    is_legal_guardian: bool = False


class EmergencyContactUpsert(EmergencyContactBase):
    pass


class EmergencyContactResponse(EmergencyContactBase):
    model_config = ConfigDict(from_attributes=True)


# --- Legal guardian -----------------------------------------------------


class LegalGuardianBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    relationship: str = Field(max_length=50)
    dni: str | None = Field(default=None, max_length=20)
    phone: str = Field(min_length=1, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class LegalGuardianUpsert(LegalGuardianBase):
    pass


class LegalGuardianResponse(LegalGuardianBase):
    model_config = ConfigDict(from_attributes=True)


# --- Aggregate medical history (legacy-shaped payload for the form) -----


class MedicalHistoryUpdate(BaseModel):
    """Bulk update payload mirroring the legacy JSONB shape.

    The frontend form submits the entire medical history in one go.
    Backend converts it into the normalized tables atomically.
    """

    allergies: list[AllergyCreate] = []
    medications: list[MedicationCreate] = []
    systemic_diseases: list[SystemicDiseaseCreate] = []
    surgical_history: list[SurgicalHistoryCreate] = []

    is_pregnant: bool = False
    pregnancy_week: int | None = Field(default=None, ge=1, le=42)
    is_lactating: bool = False

    is_on_anticoagulants: bool = False
    anticoagulant_medication: str | None = Field(default=None, max_length=100)
    inr_value: float | None = Field(default=None, ge=0, le=20)
    last_inr_date: date | None = None

    is_smoker: bool = False
    smoking_frequency: str | None = Field(default=None, max_length=100)
    alcohol_consumption: str | None = Field(default=None, max_length=100)

    bruxism: bool = False

    adverse_reactions_to_anesthesia: bool = False
    anesthesia_reaction_details: str | None = Field(default=None, max_length=500)


class MedicalHistoryResponse(BaseModel):
    allergies: list[AllergyResponse] = []
    medications: list[MedicationResponse] = []
    systemic_diseases: list[SystemicDiseaseResponse] = []
    surgical_history: list[SurgicalHistoryResponse] = []

    is_pregnant: bool = False
    pregnancy_week: int | None = None
    is_lactating: bool = False

    is_on_anticoagulants: bool = False
    anticoagulant_medication: str | None = None
    inr_value: float | None = None
    last_inr_date: date | None = None

    is_smoker: bool = False
    smoking_frequency: str | None = None
    alcohol_consumption: str | None = None

    bruxism: bool = False

    adverse_reactions_to_anesthesia: bool = False
    anesthesia_reaction_details: str | None = None

    last_updated_at: datetime | None = None
    last_updated_by: UUID | None = None


# --- Alerts (computed) --------------------------------------------------


class PatientAlert(BaseModel):
    type: str
    severity: str
    title: str
    details: str | None = None


class PatientAlertsResponse(BaseModel):
    alerts: list[PatientAlert]
