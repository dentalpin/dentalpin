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
