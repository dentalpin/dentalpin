"""Schemas for the leads module: staff CRUD, public intake, settings.

Hard rule on the intake side: the public response is byte-identical
whether the enquiry matched a patient or not. An unauthenticated caller
must not be able to probe "is this phone a patient of this clinic?" —
so nothing about the routing branch may appear in LeadIntakeAck, or in
the intake handler's status codes, wording or headers.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.patients.schemas import PatientBrief

LeadStatus = Literal["new", "contacted", "converted", "discarded"]
LeadSubmitOutcome = Literal["lead_created", "recall_queued"]

# Availability is structured rather than free text: the front desk reads a
# week strip, and a card can show which days are open at a glance. The codes
# mirror models.AVAILABILITY_DAYS / AVAILABILITY_SLOTS.
DayOfWeek = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
AvailabilitySlot = Literal["morning", "afternoon", "evening"]

# The path the frontend prefixes with its own origin: the backend does not
# guess hostnames.
INTAKE_PATH = "/api/v1/leads/public/intake"


def _strip_required(value: str | None) -> str | None:
    """Trim, and reject a field that is only whitespace."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


class LeadCreate(BaseModel):
    """Manual creation by staff (front desk taking an enquiry by phone).

    Extra fields are rejected (`extra="forbid"`) so a caller still sending the
    retired `availability` free-text field gets a loud 422 instead of a silently
    dropped value.
    """

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=32)
    email: EmailStr | None = None
    motive: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    # Optional: an enquiry with no stated availability is still a lead.
    availability_days: list[DayOfWeek] | None = Field(default=None, max_length=7)
    availability_slot: AvailabilitySlot | None = None
    status: LeadStatus = "new"

    _strip_name = field_validator("full_name", "phone", "motive")(_strip_required)
    _strip_free = field_validator("description")(_strip_optional)


class LeadUpdate(BaseModel):
    """All-optional: PATCH semantics with exclude_unset."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    email: EmailStr | None = None
    motive: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    availability_days: list[DayOfWeek] | None = Field(default=None, max_length=7)
    availability_slot: AvailabilitySlot | None = None
    status: LeadStatus | None = None

    _strip_name = field_validator("full_name", "phone", "motive")(_strip_required)
    _strip_free = field_validator("description")(_strip_optional)


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    full_name: str
    phone: str
    email: str | None
    motive: str
    description: str | None
    availability_days: list[DayOfWeek] | None
    availability_slot: AvailabilitySlot | None
    status: LeadStatus
    patient_id: UUID | None
    converted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LeadIntakeCreate(BaseModel):
    """The external form's payload.

    Every string carries a max_length — that, plus the request body cap,
    is the storage-abuse floor for an unauthenticated endpoint.

    `extra="forbid"`: an unknown field is a 422, not something quietly thrown
    away. That is what makes a contract change loud — a website still posting the
    retired `availability` string is told so instead of losing the value.
    """

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=32)
    email: EmailStr
    motive: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    # Optional: the form may not ask, and a missing answer is not an error.
    # (Superseded the free-text string of the first design; the website must
    # now send day codes.)
    availability_days: list[DayOfWeek] | None = Field(default=None, max_length=7)
    availability_slot: AvailabilitySlot | None = None
    # Honeypot: a real person leaves it empty. Never stored, never echoed.
    website: str = Field(default="", max_length=200)

    _strip_name = field_validator("full_name", "phone", "motive")(_strip_required)
    _strip_free = field_validator("description")(_strip_optional)


class LeadIntakeAck(BaseModel):
    """The only thing the public endpoint ever returns."""

    received: bool


class LeadSubmitResponse(BaseModel):
    """Staff-path outcome union.

    The front desk is never told "saved" when the row went to Recalls
    instead. recalled_patient discloses which patient matched, which is
    why POST /leads/ also requires patients.read.
    """

    outcome: LeadSubmitOutcome
    lead: LeadResponse | None = None
    recalled_patient: PatientBrief | None = None


class LeadConvertRequest(BaseModel):
    """The patient payload the convert drawer submits."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    date_of_birth: date | None = None
    national_id: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=4000)

    _strip_names = field_validator("first_name", "last_name")(_strip_required)
    _strip_rest = field_validator("phone", "national_id")(_strip_optional)


class LeadConvertResponse(BaseModel):
    lead: LeadResponse
    patient: PatientBrief


class LeadIntakeKeyStatus(BaseModel):
    """Never the key, never the hash — only what the UI needs to show."""

    configured: bool
    key_prefix: str | None = None
    is_active: bool = False
    last_used_at: datetime | None = None


class LeadSettingsResponse(BaseModel):
    daily_cap: int
    day_count: int
    day_count_date: date | None
    intake_url: str
    key: LeadIntakeKeyStatus


class LeadSettingsUpdate(BaseModel):
    """0 means unlimited — but 10_000_000 does not, and a cap the clinic
    can defeat in one field is not a cap."""

    daily_cap: int = Field(ge=0, le=5000)


class IntakeKeyRotated(BaseModel):
    """Returned exactly once. Never stored, never logged, never re-read."""

    key: str
    key_prefix: str


class IntakeKeyUpdate(BaseModel):
    is_active: bool
