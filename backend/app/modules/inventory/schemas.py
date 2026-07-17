"""Pydantic schemas for the inventory module."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

InventoryCategory = Literal["consumables", "ppe", "materials", "medication", "other"]


class InventoryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: InventoryCategory = "other"
    unit: str | None = Field(default=None, max_length=30)
    quantity_on_hand: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    low_stock_threshold: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)


class InventoryItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: InventoryCategory | None = None
    unit: str | None = Field(default=None, max_length=30)
    low_stock_threshold: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)


class InventoryAdjust(BaseModel):
    """Adjust quantity on hand by a signed delta (e.g. -2 for 2 used, +10 for restock)."""

    delta: Decimal = Field(max_digits=10, decimal_places=2)
    note: str | None = Field(default=None, max_length=500)


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    name: str
    category: InventoryCategory
    unit: str | None
    quantity_on_hand: Decimal
    low_stock_threshold: Decimal
    is_low_stock: bool
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
