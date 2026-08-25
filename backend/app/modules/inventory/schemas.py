"""Pydantic schemas for the inventory module (#226 core upgrade)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ItemCategory = Literal["consumables", "equipment", "office", "other"]

MovementReason = Literal["initial", "restock", "consumption", "adjustment", "correction"]


class InventoryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: ItemCategory = "other"
    unit: str = Field(default="units", max_length=20)
    stock_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    min_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class InventoryItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: ItemCategory | None = None
    unit: str | None = Field(default=None, max_length=20)
    # Absolute set — the CHECK constraint still blocks negatives at the DB
    # level. Incremental changes must go through the atomic adjust endpoint.
    stock_quantity: Decimal | None = Field(default=None, ge=0)
    min_quantity: Decimal | None = Field(default=None, ge=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class StockAdjustPayload(BaseModel):
    """Relative stock change. ``delta`` may be negative (consumption).

    Every adjustment is recorded in the ``stock_movements`` ledger with
    its reason and an optional note — that ledger is the audit trail
    (#226).
    """

    delta: Decimal
    reason: MovementReason = "adjustment"
    note: str | None = Field(default=None, max_length=200)


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    name: str
    category: ItemCategory
    unit: str
    stock_quantity: Decimal
    min_quantity: Decimal
    unit_cost: Decimal | None
    is_low_stock: bool
    is_active: bool
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    inventory_item_id: UUID
    delta: Decimal
    reason: str
    note: str | None
    reference_type: str | None
    reference_id: UUID | None
    created_by: UUID | None
    created_at: datetime


class StockValuationResponse(BaseModel):
    """Total value of on-hand stock, over items with a known unit cost."""

    total_value: Decimal
    valued_items: int
    unvalued_items: int
