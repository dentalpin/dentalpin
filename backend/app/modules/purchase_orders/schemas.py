"""Pydantic schemas for purchase orders."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import PO_STATUSES


class PurchaseOrderLineCreate(BaseModel):
    inventory_item_id: UUID
    quantity_ordered: Decimal = Field(gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: UUID
    expected_date: date | None = None
    notes: str | None = None
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1)


class PurchaseOrderUpdate(BaseModel):
    expected_date: date | None = None
    notes: str | None = None


class StatusTransition(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _known_status(cls, v: str) -> str:
        if v not in PO_STATUSES:
            raise ValueError(f"status must be one of {sorted(PO_STATUSES)}")
        return v


class PurchaseOrderLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    inventory_item_id: UUID
    item_name: str = ""
    quantity_ordered: Decimal
    quantity_received: Decimal = Decimal("0")
    unit_price: Decimal | None = None


class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    supplier_id: UUID
    supplier_name: str = ""
    status: str
    expected_date: date | None = None
    notes: str | None = None
    created_by: UUID | None = None
    received_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[PurchaseOrderLineResponse] = []


class ReceiptLineCreate(BaseModel):
    purchase_order_line_id: UUID
    quantity_received: Decimal = Field(gt=0)
    quality: str = Field(default="good", pattern="^(good|rejected)$")


class PurchaseReceiptCreate(BaseModel):
    lines: list[ReceiptLineCreate] = Field(min_length=1)


class PurchaseReceiptLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_line_id: UUID
    inventory_item_id: UUID
    item_name: str = ""
    quantity_received: Decimal
    quality: str


class PurchaseReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_id: UUID
    received_at: datetime
    received_by: UUID | None = None
    lines: list[PurchaseReceiptLineResponse] = []
