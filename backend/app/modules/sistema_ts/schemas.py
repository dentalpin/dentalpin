"""Pydantic schemas for the sistema_ts HTTP surface."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TIPI_SPESA = ("TK", "FC", "FV", "AD", "AS", "SR", "CT", "PI", "IC", "AA", "SV", "SP")


class TsSettingsResponse(BaseModel):
    enabled: bool
    environment: str
    username: str | None
    has_password: bool
    has_pincode: bool
    has_custom_certificate: bool
    certificate_expires_at: datetime | None
    cf_proprietario: str | None
    codice_regione: str | None
    codice_asl: str | None
    codice_ssa: str | None
    dispositivo: str
    default_tipo_spesa: str
    sync_from: date | None
    last_response_at: datetime | None
    next_send_after: datetime | None
    last_error: str | None
    # Year overview for the settings page (ADR 0026 §5)
    year: int
    deadline: date
    unsent_count: int
    accepted_count: int
    rejected_count: int


class TsSettingsUpdate(BaseModel):
    enabled: bool | None = None
    environment: str | None = Field(default=None, pattern=r"^(test|prod)$")
    username: str | None = Field(default=None, min_length=1, max_length=16)
    password: str | None = Field(default=None, max_length=200)
    pincode: str | None = Field(default=None, min_length=4, max_length=20)
    certificate_b64: str | None = Field(default=None, max_length=20000)
    clear_certificate: bool | None = None
    cf_proprietario: str | None = Field(default=None, min_length=11, max_length=16)
    codice_regione: str | None = Field(default=None, max_length=3)
    codice_asl: str | None = Field(default=None, max_length=3)
    codice_ssa: str | None = Field(default=None, max_length=10)
    dispositivo: str | None = Field(default=None, pattern=r"^[0-9]{1,10}$")
    default_tipo_spesa: str | None = Field(
        default=None, pattern=r"^(TK|FC|FV|AD|AS|SR|CT|PI|IC|AA|SV|SP)$"
    )
    sync_from: date | None = None


class TsDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    patient_id: UUID
    operation: str
    num_documento: str
    data_emissione: date
    data_pagamento: date | None
    total_amount: Decimal
    pagamento_tracciato: str
    flag_opposizione: bool
    voci: list
    state: str
    attempts: int
    next_attempt_at: datetime | None
    esito: int | None
    protocollo: str | None
    messages: list | None
    error_message: str | None
    environment: str | None
    created_at: datetime
    sent_at: datetime | None
    finished_at: datetime | None


class OppositionResponse(BaseModel):
    patient_id: UUID
    opposed: bool
    opposed_since: date | None
    revoked_at: date | None
    note: str | None


class OppositionUpdate(BaseModel):
    opposed: bool
    note: str | None = Field(default=None, max_length=300)


class ItemTypeResponse(BaseModel):
    catalog_item_id: UUID
    tipo_spesa: str
    flag_tipo_spesa: str | None


class ItemTypeUpdate(BaseModel):
    tipo_spesa: str = Field(pattern=r"^(TK|FC|FV|AD|AS|SR|CT|PI|IC|AA|SV|SP)$")
    flag_tipo_spesa: str | None = Field(default=None, pattern=r"^[12]$")


class QueueProcessResult(BaseModel):
    queued: int
    accepted: int
    rejected: int
    failed: int
