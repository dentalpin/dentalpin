"""Pydantic schemas for medical_reference."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# --- Allergy --------------------------------------------------------------


class ReferenceAllergyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class ReferenceAllergyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None


class ReferenceAllergyResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# --- Medication -------------------------------------------------------------


class ReferenceMedicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class ReferenceMedicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None


class ReferenceMedicationResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# --- Surgery ------------------------------------------------------------


class ReferenceSurgeryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class ReferenceSurgeryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None


class ReferenceSurgeryResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# --- Disease ----------------------------------------------------------------


class ReferenceDiseaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    is_apci: bool = False


class ReferenceDiseaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    is_apci: bool | None = None
    is_active: bool | None = None


class ReferenceDiseaseResponse(BaseModel):
    id: UUID
    name: str
    is_apci: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# --- Interactions & contraindications --------------------------------------


class ReferenceInteractionCreate(BaseModel):
    medication_a_id: UUID
    medication_b_id: UUID
    risk_note: str = Field(min_length=1)


class ReferenceInteractionUpdate(BaseModel):
    risk_note: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class ReferenceInteractionResponse(BaseModel):
    id: UUID
    medication_a_id: UUID
    medication_a_name: str
    medication_b_id: UUID
    medication_b_name: str
    risk_note: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ReferenceContraindicationCreate(BaseModel):
    disease_id: UUID
    medication_id: UUID
    risk_note: str = Field(min_length=1)


class ReferenceContraindicationUpdate(BaseModel):
    risk_note: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class ReferenceContraindicationResponse(BaseModel):
    id: UUID
    disease_id: UUID
    disease_name: str
    medication_id: UUID
    medication_name: str
    risk_note: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# --- Active per-patient flags ------------------------------------------------


class PatientFlag(BaseModel):
    """One detected warning for a patient — either an interaction between
    two of their recorded medications, or a disease contraindicating one
    of their medications."""

    type: str  # "interaction" | "contraindication"
    risk_note: str
    # For interaction: [medication_a_name, medication_b_name]
    # For contraindication: [disease_name, medication_name]
    involved: list[str]
