"""Pydantic schemas for authentication."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _validate_iana_timezone(value: str | None) -> str | None:
    """Reject anything that isn't a valid IANA timezone id."""
    if value is None:
        return value
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Invalid timezone '{value}'. Must be an IANA id "
            "(e.g. 'Europe/Madrid', 'America/New_York')."
        ) from exc
    return value


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str


class UserResponse(BaseModel):
    """Schema for user response."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    professional_id: str | None = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ClinicResponse(BaseModel):
    """Schema for clinic response."""

    id: UUID
    name: str
    role: str  # User's role in this clinic

    model_config = ConfigDict(from_attributes=True)


# --- Clinic metadata admin (moved from clinical module in B.5) ---------


class ClinicAddressUpdate(BaseModel):
    """Schema for address fields on a clinic."""

    street: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)


class ClinicMetadataUpdate(BaseModel):
    """Schema for updating clinic info (admin only)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    tax_id: str | None = Field(default=None, max_length=20)
    legal_name: str | None = Field(default=None, max_length=200)
    address: ClinicAddressUpdate | None = None
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, pattern="^[A-Z]{3}$")

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        return _validate_iana_timezone(value)


class _ClinicCabinetBrief(BaseModel):
    """Minimal cabinet projection for the clinic metadata endpoint.

    Agenda owns the full cabinet schema; this is a core-layer view so
    core doesn't need to import from modules.
    """

    id: UUID
    name: str
    color: str
    display_order: int = 0
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class ClinicMetadataResponse(BaseModel):
    """Schema for clinic metadata detail response."""

    id: UUID
    name: str
    tax_id: str
    legal_name: str | None = None
    address: dict | None
    phone: str | None
    email: str | None
    timezone: str
    currency: str
    settings: dict
    cabinets: list[_ClinicCabinetBrief]

    model_config = ConfigDict(from_attributes=True)


class MeResponse(BaseModel):
    """Schema for /me endpoint response."""

    user: UserResponse
    clinics: list[ClinicResponse]
    permissions: list[str]


class AuthResponse(BaseModel):
    """Schema for auth response with user info (login/refresh)."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
    clinics: list[ClinicResponse]


class UserCreate(BaseModel):
    """Schema for admin creating a new user."""

    email: EmailStr
    # Optional: without a password the account is created locked and the
    # admin hands out an invite link (``POST /users/{id}/invite-link``).
    password: str | None = Field(default=None, min_length=8)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: str = Field(description="Role: admin, dentist, hygienist, assistant, receptionist")
    clinic_id: UUID | None = Field(
        default=None, description="Clinic ID. If not provided, uses admin's current clinic"
    )
    is_professional: bool | None = Field(
        default=None,
        description="Appears in the agenda / can be assigned treatments. "
        "Defaults to true for dentist/hygienist, false otherwise.",
    )


class InviteLinkResponse(BaseModel):
    """One-time set-password token for a user (the client builds the URL)."""

    token: str
    expires_at: datetime


class SetPasswordRequest(BaseModel):
    """Consume an invite token and set the account password."""

    token: str
    password: str = Field(min_length=8)


class UserWithRoleResponse(BaseModel):
    """Schema for user with their clinic role."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    is_active: bool
    role: str
    is_professional: bool = False
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    role: str | None = Field(
        default=None, description="Role: admin, dentist, hygienist, assistant, receptionist"
    )
    is_active: bool | None = None
    is_professional: bool | None = Field(
        default=None,
        description="Appears in the agenda / can be assigned treatments. "
        "When only `role` changes, the flag is re-derived from the new role.",
    )


class ProfessionalResponse(BaseModel):
    """Schema for professional response (dentists and hygienists)."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    role: str

    model_config = ConfigDict(from_attributes=True)


# --- First-time setup (issue #85) --------------------------------------


class SetupStatusResponse(BaseModel):
    """Whether the system has already been initialized (has any user)."""

    initialized: bool


class SystemSetup(BaseModel):
    """First-run payload: create the first admin account + its clinic."""

    admin_first_name: str = Field(min_length=1, max_length=100)
    admin_last_name: str = Field(min_length=1, max_length=100)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8)
    # Whether the admin also attends patients (solo practice) — flips
    # `is_professional` on the admin membership so the team onboarding
    # step resolves without a second user.
    admin_is_professional: bool = False
    clinic_name: str = Field(min_length=1, max_length=200)
    clinic_tax_id: str = Field(min_length=1, max_length=20)
    # Optional address, same keys as ClinicAddressUpdate — filling street
    # here completes the "clinic info" onboarding step from the wizard.
    clinic_street: str | None = Field(default=None, max_length=200)
    clinic_city: str | None = Field(default=None, max_length=100)
    clinic_postal_code: str | None = Field(default=None, max_length=20)
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, pattern="^[A-Z]{3}$")
    # ISO-3166 alpha-2. Drives the country preset (tz/currency defaults,
    # tax-id format, VAT preset seeded by catalog). None keeps the legacy
    # Europe/Madrid + EUR defaults so pre-existing callers don't change.
    country: str | None = Field(default=None, pattern="^[A-Za-z]{2}$")
    # Communication language for the clinic (patient-facing). Defaults from
    # the country preset.
    language: str | None = Field(default=None, pattern="^(es|en|fr|pt|ta)$")

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        return _validate_iana_timezone(value)

    @field_validator("country")
    @classmethod
    def upper_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class CountryPresetResponse(BaseModel):
    code: str
    currency: str
    timezone: str
    language: str
    vat_preset: str
    tax_id_label: str
    tax_id_pattern: str | None
    tax_id_example: str | None
    suggested_modules: list[str]


class SetupPresetsResponse(BaseModel):
    """Country presets the first-run wizard offers (public, pre-auth)."""

    countries: list[CountryPresetResponse]
    fallback: CountryPresetResponse
