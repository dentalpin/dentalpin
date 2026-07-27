"""Schemas for the inventory_reorder module."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ReorderSuggestion(BaseModel):
    inventory_item_id: UUID
    item_name: str
    quantity_on_hand: Decimal
    low_stock_threshold: Decimal
    reorder_max_quantity: Decimal | None
    avg_daily_usage: Decimal
    lead_time_days: int
    suggested_quantity: Decimal
    supplier_contact_id: UUID | None
    supplier_name: str | None
    unit_price: Decimal | None
    estimated_cost: Decimal | None
    # True when the suggestion had no usage history and no explicit
    # reorder_max_quantity to size against — a crude fallback was used.
    # Surfaced so staff know to double-check the number, not hide it.
    low_confidence: bool


class ReorderSelection(BaseModel):
    inventory_item_id: UUID
    supplier_contact_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    unit_price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class GeneratePOsRequest(BaseModel):
    selections: list[ReorderSelection] = Field(min_length=1)


class GeneratePOsResponse(BaseModel):
    purchase_order_ids: list[UUID]
