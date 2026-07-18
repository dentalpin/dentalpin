"""sms_gateway Pydantic schemas. Secrets are never returned, only a has_api_key flag."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SmsSettingsUpdate(BaseModel):
    provider_name: str | None = Field(default=None, max_length=50)
    api_key: str | None = Field(default=None, description="Provider API key (write-only).")
    sender_id: str | None = Field(default=None, max_length=50)
    base_url: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class SmsSettingsResponse(BaseModel):
    provider_name: str
    sender_id: str | None
    base_url: str | None
    has_api_key: bool
    is_active: bool


class SmsOutboxLogResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    to_address: str
    body: str
    provider_name: str
    status: str
    error_message: str | None
    created_at: datetime
