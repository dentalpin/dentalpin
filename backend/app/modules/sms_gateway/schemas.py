"""Pydantic schemas for sms_gateway settings."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SmsSettingsUpdate(BaseModel):
    provider: str | None = Field(default=None, pattern="^(log|twilio)$")
    account_sid: str | None = Field(default=None, max_length=100)
    auth_token: str | None = Field(default=None, max_length=100)
    from_number: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


class SmsSettingsResponse(BaseModel):
    """Masked settings view. Ciphertext never leaves the server."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    provider: str
    from_number: str | None
    has_account_sid: bool = False
    has_auth_token: bool = False
    is_active: bool
    created_at: datetime
    updated_at: datetime


def mask_settings(row) -> SmsSettingsResponse:
    return SmsSettingsResponse(
        id=row.id,
        clinic_id=row.clinic_id,
        provider=row.provider,
        from_number=row.from_number,
        has_account_sid=row.account_sid_encrypted is not None,
        has_auth_token=row.auth_token_encrypted is not None,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
