"""Orthodontics schemas (issue #270, slices a+b)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    patient_name: str | None = None
    treatment_plan_id: UUID | None = None
    plan_item_id: UUID | None = None
    control_count: int = 0
    last_control_at: datetime | None = None
    next_due: date | None = None
    plan_close_suggested: bool = False


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
    appointment_id: UUID | None = None
    session_id: UUID | None = None


class OrthoControlUpdate(BaseModel):
    upper_wire: str | None = Field(default=None, max_length=40)
    lower_wire: str | None = Field(default=None, max_length=40)
    procedures: list[str] | None = Field(default=None, max_length=50)
    procedures_other: str | None = Field(default=None, max_length=2000)
    aligner_number: int | None = Field(default=None, ge=1)
    hygiene: Hygiene | None = None
    notes: str | None = Field(default=None, max_length=5000)
    next_control_weeks: int | None = Field(default=None, ge=1, le=52)
    appointment_id: UUID | None = None
    session_id: UUID | None = None


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
    appointment_id: UUID | None = None
    session_id: UUID | None = None


class OrthoSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinic_id: UUID
    wires: list[str]
    procedures: list[str]


class OrthoSettingsUpdate(BaseModel):
    wires: list[str] = Field(max_length=100)
    procedures: list[str] = Field(max_length=100)


class OrthoPlanLink(BaseModel):
    treatment_plan_id: UUID
    plan_item_id: UUID


class OrthoScheduleCreate(BaseModel):
    down_payment: Decimal = Field(ge=0)
    months: int = Field(ge=1, le=60)
    monthly_amount: Decimal = Field(ge=0)
    # Session labels in the caller's language (the UI's own strings), so
    # generated rows never store English fallback text. Absent labels keep
    # the legacy English ones for older API clients.
    down_payment_label: str | None = Field(default=None, max_length=120)
    installment_labels: list[str] | None = None


class OrthoSessionBrief(BaseModel):
    id: UUID
    sequence: int
    label: str | None
    amount: Decimal
    status: str


class OrthoInstallmentsResponse(BaseModel):
    treatment_plan_id: UUID
    plan_item_id: UUID
    sessions: list[OrthoSessionBrief]
    completed_count: int
    pending_count: int
