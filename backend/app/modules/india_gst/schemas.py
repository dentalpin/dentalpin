"""Pydantic schemas for the India GST API."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .constants import INDIA_STATES, REGISTRATION_TYPES

_REGISTRATION_PATTERN = "^(" + "|".join(REGISTRATION_TYPES) + ")$"
_STATE_PATTERN = "^(" + "|".join(INDIA_STATES.keys()) + ")$"


class IndiaGstSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    trade_name: str | None
    gstin: str | None
    registration_type: str
    clinic_state: str | None
    clinic_state_name: str | None = None
    turnover_threshold: Decimal | None
    show_gstin_on_invoice: bool
    show_sac_on_invoice: bool
    # Computed: supplier GSTIN's leading 2-digit state code disagrees
    # with clinic_state — the UI shows a warning, saving is not blocked
    # (#262).
    gstin_state_mismatch: bool = False


class IndiaGstSettingsUpdate(BaseModel):
    trade_name: str | None = Field(default=None, max_length=200)
    gstin: str | None = Field(default=None, max_length=15)
    registration_type: str | None = Field(default=None, pattern=_REGISTRATION_PATTERN)
    clinic_state: str | None = Field(default=None, pattern=_STATE_PATTERN)
    turnover_threshold: Decimal | None = None
    show_gstin_on_invoice: bool | None = None
    show_sac_on_invoice: bool | None = None


class IndiaGstCatalogItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    catalog_item_id: UUID
    sac_code: str
    notes: str | None


class IndiaGstCatalogItemUpdate(BaseModel):
    sac_code: str = Field(min_length=4, max_length=10)
    notes: str | None = Field(default=None, max_length=500)


class IndiaGstMissingSacItem(BaseModel):
    catalog_item_id: UUID
    # Full ``{locale: name}`` dict so the client renders the treatment in
    # the viewer's own UI language; ``name`` is the English fallback.
    names: dict[str, str] = Field(default_factory=dict)
    name: str | None
    internal_code: str | None


class IndiaGstCatalogDefaultsResponse(BaseModel):
    configured: list[IndiaGstCatalogItemResponse]
    missing: list[IndiaGstMissingSacItem]


class IndiaGstCatalogAutoconfigureResponse(BaseModel):
    configured_count: int
    sac_code: str


class GstLineBreakdownResponse(BaseModel):
    invoice_item_id: UUID | None
    sac_code: str | None
    tax_type: str
    cgst_rate: Decimal
    cgst_amount: Decimal
    sgst_rate: Decimal
    sgst_amount: Decimal
    igst_rate: Decimal
    igst_amount: Decimal


class GstBreakdownResponse(BaseModel):
    is_intra: bool
    lines: list[GstLineBreakdownResponse]
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal


class TaxPreviewLineInput(BaseModel):
    invoice_item_id: UUID | None = None
    vat_rate: Decimal
    line_tax: Decimal
    sac_code: str | None = None


class TaxPreviewRequest(BaseModel):
    items: list[TaxPreviewLineInput]
    place_of_supply: str | None = Field(default=None, pattern=_STATE_PATTERN)


class IndiaGstInvoiceDraftItemUpdate(BaseModel):
    invoice_item_id: UUID
    sac_code: str | None = Field(default=None, max_length=10)


class IndiaGstInvoiceDraftUpdate(BaseModel):
    place_of_supply: str | None = Field(default=None, pattern=_STATE_PATTERN)
    items: list[IndiaGstInvoiceDraftItemUpdate] = Field(default_factory=list)


class IndiaGstEinvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: UUID
    state: str
    provider_error_message: str | None


class IndiaGstEinvoiceRetryError(BaseModel):
    reason: str = "provider_not_configured"
    message: str = "Configure an e-invoice provider before submitting this invoice."


class GstReportSummaryResponse(BaseModel):
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    invoice_count: int
    credit_note_count: int
    by_place_of_supply: list[dict]


class GstReportTransactionRow(BaseModel):
    invoice_id: UUID
    gst_document_number: str | None
    issue_date: str | None
    recipient_gstin: str | None
    place_of_supply: str | None
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    status: str
    is_credit_note: bool
