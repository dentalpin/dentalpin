"""Validated input for the online booking API."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    professional_id: UUID | None = None
    public_url: str | None = Field(default=None, max_length=500)
    slot_minutes: int = Field(default=30, ge=5, le=480)
    first_visit_minutes: int | None = Field(default=None, ge=5, le=480)
    checkup_minutes: int | None = Field(default=None, ge=5, le=480)
    window_days: int = Field(default=30, ge=1, le=365)
    min_notice_minutes: int = Field(default=60, ge=0, le=525600)

    @field_validator("public_url")
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        from urllib.parse import urlsplit

        if value is not None:
            parsed = urlsplit(value)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Expected HTTPS URL without credentials, query or fragment")
        return value


class RequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    start_time: datetime
    contact_name: str = Field(min_length=1, max_length=120)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=20, pattern=r"^[+0-9 ()-]*$")
    reason: Literal["first_visit", "checkup"]
    website: str = Field(default="", max_length=200)
    altcha: str = Field(min_length=1, max_length=4096)

    @field_validator("start_time")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Timezone required")
        return value


class ConfirmInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=30, max_length=200)


class AcceptInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    patient_id: UUID | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20, pattern=r"^[+0-9 ()-]*$")
    professional_id: UUID
    cabinet_id: UUID | None = None
    duration_minutes: int = Field(ge=5, le=480)


class RejectInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=500)


class PublicConfig(BaseModel):
    slot_minutes: int
    timezone: str
    reasons: list[str]


class Availability(BaseModel):
    starts: list[str]
    slot_minutes: int


class MessageOut(BaseModel):
    message: str


class StatusOut(BaseModel):
    status: str


class AcceptOut(BaseModel):
    status: str
    appointment_id: UUID


class BookingRequestOut(BaseModel):
    id: UUID
    status: str
    start_time: datetime
    end_time: datetime
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    reason: str
    default_duration_minutes: int


class PatientSuggestion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    date_of_birth: date | None
