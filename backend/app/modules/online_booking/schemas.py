"""Validated input for the online booking API."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .logo import MAX_LOGO_BASE64
from .models import default_reasons


class ReasonInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=30, pattern=r"^[a-z0-9_]+$")
    name_es: str = Field(min_length=1, max_length=80)
    name_en: str = Field(min_length=1, max_length=80)
    duration_minutes: int = Field(ge=5, le=480)
    active: bool = True


class SettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reasons: list[ReasonInput] = Field(
        default_factory=default_reasons, min_length=1, max_length=30, validate_default=True
    )
    enabled: bool = False
    professional_id: UUID | None = None
    public_url: str | None = Field(default=None, max_length=500)
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    title_es: str | None = Field(default=None, max_length=120)
    intro_es: str | None = Field(default=None, max_length=300)
    title_en: str | None = Field(default=None, max_length=120)
    intro_en: str | None = Field(default=None, max_length=300)
    slot_minutes: int = Field(default=30, ge=5, le=480)
    first_visit_minutes: int | None = Field(default=None, ge=5, le=480)
    checkup_minutes: int | None = Field(default=None, ge=5, le=480)
    window_days: int = Field(default=30, ge=1, le=365)
    min_notice_minutes: int = Field(default=60, ge=0, le=525600)

    @field_validator("reasons")
    @classmethod
    def unique_reasons(cls, value: list[ReasonInput]) -> list[ReasonInput]:
        if len({reason.id for reason in value}) != len(value):
            raise ValueError("Reason IDs must be unique")
        if not any(reason.active for reason in value):
            raise ValueError("At least one reason must be active")
        return value

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


class LogoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=255)
    data: str = Field(min_length=1, max_length=MAX_LOGO_BASE64)


class LogoState(BaseModel):
    uploaded: bool


class RequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    start_time: datetime
    contact_name: str = Field(min_length=1, max_length=120)
    contact_email: EmailStr
    contact_phone: str = Field(min_length=1, max_length=30, pattern=r"^\+?[0-9 ()-]+$")
    language: Literal["es", "en"] = "es"
    reason: str = Field(min_length=1, max_length=30, pattern=r"^[a-z0-9_]+$")
    website: str = Field(default="", max_length=200)
    altcha: str = Field(min_length=1, max_length=4096)

    @field_validator("contact_phone")
    @classmethod
    def valid_phone(cls, value: str) -> str:
        import phonenumbers

        try:
            number = phonenumbers.parse(value, "ES")
        except phonenumbers.NumberParseException as exc:
            raise ValueError("Invalid phone number") from exc
        if not phonenumbers.is_valid_number(number) or number.extension:
            raise ValueError("Invalid phone number")
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)

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
    window_days: int
    branding: dict[str, str | None]
    timezone: str
    reasons: list[ReasonInput]


class DayAvailability(BaseModel):
    date: str
    starts: list[str]


class Availability(BaseModel):
    """One day (``starts``) or a range (``days``); the unused one is omitted."""

    starts: list[str] | None = None
    days: list[DayAvailability] | None = None
    slot_minutes: int


class ConfirmOut(BaseModel):
    status: str
    start_time: str
    timezone: str


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
    reason_name_es: str
    reason_name_en: str
    default_duration_minutes: int


class PatientSuggestion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    date_of_birth: date | None
