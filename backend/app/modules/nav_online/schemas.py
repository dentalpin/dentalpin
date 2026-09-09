"""nav_online Pydantic schemas. Secrets are write-only."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NavSettingsResponse(BaseModel):
    enabled: bool
    environment: str
    tax_number: str | None
    technical_user_login: str | None
    has_password: bool
    has_signature_key: bool
    has_exchange_key: bool
    software_id: str
    software_dev_contact: str | None
    last_nav_response_at: datetime | None
    next_send_after: datetime | None
    last_error: str | None


class NavSettingsUpdate(BaseModel):
    enabled: bool | None = None
    environment: str | None = Field(default=None, pattern=r"^(test|prod)$")
    tax_number: str | None = Field(default=None, pattern=r"^\d{8}(\d{3})?$")
    technical_user_login: str | None = Field(default=None, max_length=15)
    technical_user_password: str | None = Field(default=None, max_length=200)
    signature_key: str | None = Field(default=None, max_length=200)
    exchange_key: str | None = Field(default=None, min_length=16, max_length=16)
    software_id: str | None = Field(default=None, pattern=r"^[0-9A-Z\-]{18}$")
    software_dev_contact: str | None = Field(default=None, max_length=200)


class NavRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    operation: str
    invoice_number: str
    issue_date: date
    gross_amount: Decimal
    state: str
    attempts: int
    transaction_id: str | None
    nav_status: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    sent_at: datetime | None
    finished_at: datetime | None
