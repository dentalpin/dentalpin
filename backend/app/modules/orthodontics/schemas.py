"""Orthodontics schemas (issue #270, slice-a)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import APPLIANCE_TYPES, CASE_STATUSES, HYGIENE_LEVELS

ApplianceType = Literal[
    "brackets_metal",
    "brackets_esthetic",
    "self_ligating",
    "aligners",
    "functional",
    "retention",
]

CaseStatus = Literal["active", "paused", "finished", "transferred_out"]

Hygiene = Literal["good", "fair", "poor"]


class OrthoCaseCreate(BaseModel):
    patient_id: UUID
    appliance_type: ApplianceType
    start_date: date = Field(default_factory=date.today)
    estimated_months: int | None = Field(default=None, ge=1, le=120)
    professional_id: UUID | None = None
    diagnosis_notes: str | None = Field(default=None, max_length=5000)


class OrthoCaseUpdate(BaseModel):
    appliance_type: ApplianceType | None = None
    estimated_months: int | None = Field(default=None, ge=1, le=120)
    professional_id: UUID | None = None
    diagnosis_notes: str | None = Field(default=None, max_length=5000)


class OrthoCaseStatusChange(BaseModel):
    status: CaseStatus
    status_note: str | None = Field(default=None, max_length=2000)


class OrthoCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    professional_id: UUID | None
    appliance_type: str
    status: str
    start_date: date
    estimated_months: int | None
    diagnosis_notes: str | None
    current_upper_wire: str | None
    current_lower_wire: str | None
    finished_at: datetime | None
    reopened_at: datetime | None = None
    status_note: str | None
    control_count: int = 0
    last_control_at: datetime | None = None
    next_due: date | None = None


class OrthoControlCreate(BaseModel):
    performed_at: datetime | None = None
    upper_wire: str | None = Field(default=None, max_length=40)
    lower_wire: str | None = Field(default=None, max_length=40)
    procedures: list[str] = Field(default_factory=list, max_length=50)
    procedures_other: str | None = Field(default=None, max_length=2000)
    aligner_number: int | None = Field(default=None, ge=1)
    hygiene: Hygiene | None = None
    notes: str | None = Field(default=None, max_length=5000)
    next_control_weeks: int | None = Field(default=None, ge=1, le=52)


class OrthoControlUpdate(BaseModel):
    upper_wire: str | None = Field(default=None, max_length=40)
    lower_wire: str | None = Field(default=None, max_length=40)
    procedures: list[str] | None = Field(default=None, max_length=50)
    procedures_other: str | None = Field(default=None, max_length=2000)
    aligner_number: int | None = Field(default=None, ge=1)
    hygiene: Hygiene | None = None
    notes: str | None = Field(default=None, max_length=5000)
    next_control_weeks: int | None = Field(default=None, ge=1, le=52)


class OrthoControlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    case_id: UUID
    performed_at: datetime
    performed_by: UUID | None
    upper_wire: str | None
    lower_wire: str | None
    procedures: list[str]
    procedures_other: str | None
    aligner_number: int | None
    hygiene: str | None
    notes: str | None
    next_control_weeks: int | None
    next_due: date | None = None


class OrthoSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinic_id: UUID
    wires: list[str]
    procedures: list[str]


assert set(APPLIANCE_TYPES) == {
    "brackets_metal",
    "brackets_esthetic",
    "self_ligating",
    "aligners",
    "functional",
    "retention",
}
assert set(CASE_STATUSES) == {"active", "paused", "finished", "transferred_out"}
assert set(HYGIENE_LEVELS) == {"good", "fair", "poor"}
