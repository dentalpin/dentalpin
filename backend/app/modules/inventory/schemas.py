"""Pydantic schemas for the inventory module."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

InventoryCategory = Literal["consumables", "ppe", "materials", "medication", "other"]

InventoryMovementReason = Literal[
    "purchase", "return", "donation", "adjustment", "damaged", "expired", "lost", "used"
]


class InventoryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: InventoryCategory = "other"
    unit: str | None = Field(default=None, max_length=30)
    quantity_on_hand: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    low_stock_threshold: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)


class InventoryItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: InventoryCategory | None = None
    unit: str | None = Field(default=None, max_length=30)
    low_stock_threshold: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)


class InventoryAdjust(BaseModel):
    """Adjust quantity on hand by a signed delta (e.g. -2 for 2 used, +10 for restock).

    Kept for backward compatibility. Internally recorded as an
    ``adjustment`` movement — see InventoryMovementCreate for the
    reason-aware replacement.
    """

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
    unit_cost: Decimal | None
    average_cost: Decimal | None
    is_low_stock: bool
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class InventoryMovementCreate(BaseModel):
    reason: InventoryMovementReason
    quantity_delta: Decimal = Field(max_digits=10, decimal_places=2)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)
    # Allows backdating a movement (e.g. logging a purchase received
    # yesterday). Omit to use the current time.
    movement_date: datetime | None = Field(default=None)


class InventoryMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    item_id: UUID
    reason: InventoryMovementReason
    quantity_delta: Decimal
    quantity_after: Decimal
    unit_cost: Decimal | None
    reference: str | None
    notes: str | None
    movement_date: datetime
    created_by: UUID | None
    created_at: datetime


class InventoryUsageSummary(BaseModel):
    item_id: UUID
    used_this_week: Decimal
    used_this_month: Decimal
    total_used: Decimal
