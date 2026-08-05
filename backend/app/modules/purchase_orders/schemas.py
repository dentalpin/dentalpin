"""Pydantic schemas for the purchase_orders module."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PurchaseOrderStatus = Literal[
    "draft", "sent", "confirmed", "partially_received", "fully_received", "cancelled"
]


class PurchaseOrderItemCreate(BaseModel):
    inventory_item_id: UUID
    # Optional — if omitted, the service snapshots the current
    # InventoryItem.name. Pass explicitly to override (rare).
    description: str | None = Field(default=None, max_length=200)
    unit_price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    quantity_ordered: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class PurchaseOrderItemUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=200)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    quantity_ordered: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)


class PurchaseOrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    inventory_item_id: UUID
    description: str
    unit_price: Decimal
    quantity_ordered: Decimal
    quantity_received: Decimal
    line_total: Decimal
    display_order: int


class PurchaseOrderCreate(BaseModel):
    supplier_contact_id: UUID
    expected_delivery_date: date | None = None
    shipping_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)
    items: list[PurchaseOrderItemCreate] = Field(default_factory=list)


class PurchaseOrderUpdate(BaseModel):
    """Draft-only — header fields. Line items are managed via their
    own endpoints (add/update/remove), not through this."""

    expected_delivery_date: date | None = None
    shipping_cost: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    tax_amount: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)


class PurchaseOrderCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    po_number: str
    supplier_contact_id: UUID
    status: PurchaseOrderStatus
    order_date: date
    expected_delivery_date: date | None
    shipping_cost: Decimal
    tax_amount: Decimal
    subtotal: Decimal
    total: Decimal
    notes: str | None
    sent_at: datetime | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    items: list[PurchaseOrderItemResponse] = Field(default_factory=list)


class PurchaseOrderListItem(BaseModel):
    """Lighter shape for the list view — no line items, plus the
    supplier name joined in (avoids a second round-trip per row)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    po_number: str
    supplier_contact_id: UUID
    supplier_name: str
    status: PurchaseOrderStatus
    order_date: date
    expected_delivery_date: date | None
    total: Decimal


ReceiptLineQuality = Literal["good", "damaged", "expired", "wrong_item"]


class PurchaseOrderReceiptLineCreate(BaseModel):
    purchase_order_item_id: UUID
    quantity_received: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    quality_status: ReceiptLineQuality = "good"
    notes: str | None = Field(default=None, max_length=500)


class PurchaseOrderReceiptCreate(BaseModel):
    received_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[PurchaseOrderReceiptLineCreate] = Field(min_length=1)


class PurchaseOrderReceiptLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_item_id: UUID
    quantity_received: Decimal
    quality_status: ReceiptLineQuality
    notes: str | None


class PurchaseOrderReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_id: UUID
    received_date: date
    received_by: UUID | None
    notes: str | None
    created_at: datetime
    lines: list[PurchaseOrderReceiptLineResponse] = Field(default_factory=list)
