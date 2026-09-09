"""Pydantic schemas for the sdi_it HTTP surface."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SdiSettingsResponse(BaseModel):
    enabled: bool
    transport: str
    regime_fiscale: str
    bollo_virtuale: bool
    riferimento_normativo: str
    progressivo_invio: int
    last_receipt_at: datetime | None
    last_error: str | None


class SdiSettingsUpdate(BaseModel):
    enabled: bool | None = None
    transport: str | None = Field(default=None, pattern=r"^manual$")
    regime_fiscale: str | None = Field(default=None, pattern=r"^RF(0[1-9]|1[0-9])$")
    bollo_virtuale: bool | None = None
    riferimento_normativo: str | None = Field(default=None, min_length=1, max_length=100)


class SdiRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    tipo_documento: str
    invoice_number: str
    issue_date: date
    gross_amount: Decimal
    recipient_name: str | None
    recipient_tax_id: str | None
    codice_destinatario: str
    progressivo: str
    file_name: str
    state: str
    attempts: int
    sdi_identifier: str | None
    receipt_type: str | None
    receipt_at: datetime | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    sent_at: datetime | None
    finished_at: datetime | None


class ReceiptImport(BaseModel):
    """A receipt XML as text (the UI reads the file the SDI sent back)."""

    xml: str = Field(min_length=20, max_length=2_000_000)
    file_name: str | None = Field(default=None, max_length=80)


class ReceiptImportResult(BaseModel):
    record_id: UUID
    receipt_type: str
    state: str
    errors: list[dict[str, str]]
