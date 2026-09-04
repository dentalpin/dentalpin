"""Pydantic schemas for inventory_reorder suggestions and order generation."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReorderSuggestionResponse(BaseModel):
    """One item's computed reorder suggestion (native values for jsonify)."""

    model_config = ConfigDict(from_attributes=True)

    inventory_item_id: UUID
    item_name: str
    category: str
    unit: str
    usage_90d: Decimal
    daily_usage: Decimal
    supplier_id: UUID | None = None
    supplier_name: str | None = None
    lead_time_days: int | None = None
    unit_price: Decimal | None = None
    stock_quantity: Decimal
    on_order: Decimal
    reorder_point: Decimal
    suggested_quantity: Decimal


class ReorderOrdersCreate(BaseModel):
    """Body for POST /orders: the item ids whose suggestions become POs.

    Suggestions are grouped by the item's chosen supplier, so one draft
    purchase order is created per supplier involved.
    """

    item_ids: list[UUID] = Field(min_length=1)
