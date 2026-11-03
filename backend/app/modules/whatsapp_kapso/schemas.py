"""whatsapp_kapso Pydantic schemas. Secrets are never returned."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.notifications.models import NotificationType


class KapsoSettingsUpdate(BaseModel):
    api_key: str | None = Field(default=None, description="Kapso project API key (write-only).")
    phone_number_id: str | None = Field(default=None, max_length=64)
    business_account_id: str | None = Field(default=None, max_length=64)
    webhook_secret: str | None = Field(
        default=None, description="Webhook signing secret (write-only)."
    )
    display_phone_number: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


class KapsoSettingsResponse(BaseModel):
    phone_number_id: str | None
    business_account_id: str | None
    display_phone_number: str | None
    has_api_key: bool
    has_webhook_secret: bool
    is_active: bool
    is_verified: bool
    last_verified_at: datetime | None
    last_template_sync_at: datetime | None


class KapsoTemplateResponse(BaseModel):
    name: str
    language: str
    status: str
    category: str | None
    synced_at: datetime | None

    model_config = {"from_attributes": True}


class KapsoTemplateMapRequest(BaseModel):
    notification_type: NotificationType
    locale: str = Field(..., max_length=10)
    template_name: str = Field(..., max_length=200)


class KapsoTestRequest(BaseModel):
    to_number: str = Field(..., max_length=32)
    template_name: str = Field(..., max_length=200)
    language: str = Field(default="es", max_length=10)
