"""Pydantic schemas for the medications module.

Shape matches backend/app/modules/patients/schemas.py: plain
BaseModel Create/Update/Response classes, response validated
straight from the ORM object (ConfigDict(from_attributes=True)),
no manual dict-building.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import MedicationForm, UnitType


class MedicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    dose: float = Field(gt=0)
    unit: UnitType
    form: MedicationForm
    times_per_day: int | None = Field(default=None, ge=1, le=24)
    instructions: str | None = None
    is_prescribed: bool = True


class MedicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    dose: float | None = Field(default=None, gt=0)
    unit: UnitType | None = None
    form: MedicationForm | None = None
    times_per_day: int | None = Field(default=None, ge=1, le=24)
    instructions: str | None = None
    is_prescribed: bool | None = None


class MedicationResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    name: str
    dose: float
    unit: UnitType
    form: MedicationForm
    times_per_day: int | None
    instructions: str | None
    is_prescribed: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
