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
    # PEC transport (passwords are write-only; only their presence is reported)
    pec_address: str | None = None
    sdi_pec_address: str = "sdi01@pec.fatturapa.it"
    smtp_host: str | None = None
    smtp_port: int = 465
    smtp_username: str | None = None
    has_smtp_password: bool = False
    imap_host: str | None = None
    imap_port: int = 993
    imap_folder: str = "INBOX"
    last_pec_poll_at: datetime | None = None
    next_send_after: datetime | None = None


class SdiSettingsUpdate(BaseModel):
    enabled: bool | None = None
    transport: str | None = Field(default=None, pattern=r"^(manual|pec)$")
    regime_fiscale: str | None = Field(default=None, pattern=r"^RF(0[1-9]|1[0-9])$")
    bollo_virtuale: bool | None = None
    riferimento_normativo: str | None = Field(default=None, min_length=1, max_length=100)
    pec_address: str | None = Field(
        default=None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    sdi_pec_address: str | None = Field(
        default=None, max_length=255, pattern=r"^[^@\s]+@pec\.fatturapa\.it$"
    )
    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = Field(default=None, max_length=255)
    smtp_password: str | None = Field(default=None, max_length=500)
    imap_host: str | None = Field(default=None, max_length=255)
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    imap_folder: str | None = Field(default=None, min_length=1, max_length=100)


class PecTestResult(BaseModel):
    smtp: str
    imap: str


class QueueProcessResult(BaseModel):
    sent: int
    failed: int
    receipts: int
    unmatched: int


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
    next_attempt_at: datetime | None = None
    transport: str | None = None
    message_id: str | None = None
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
