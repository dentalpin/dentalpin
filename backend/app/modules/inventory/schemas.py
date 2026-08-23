"""Pydantic schemas for the inventory module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# --- Enum literals --------------------------------------------------------

Status = Literal["active", "inactive"]

# --- Category CRUD --------------------------------------------------------


class CategoryCreate(BaseModel):
    name: str = Field(max_length=100)
    description: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Item CRUD -----------------------------------------------------------


class ItemCreate(BaseModel):
    category_id: UUID | None = None
    code: str = Field(max_length=50)
    name: str = Field(max_length=200)
    description: str | None = None
    quantity: int = 0
    min_quantity: int = 0
    unit: str = Field(default="units", max_length=20)
    location: str | None = Field(default=None, max_length=200)
    supplier: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class ItemUpdate(BaseModel):
    category_id: UUID | None = None
    code: str | None = Field(default=None, max_length=50)
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    min_quantity: int | None = None
    unit: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=200)
    supplier: str | None = Field(default=None, max_length=200)
    notes: str | None = None
    status: Status | None = None


class StockAdjustRequest(BaseModel):
    """Atomic stock adjustment — positive to add, negative to subtract.

    The service layer performs an atomic
    ``UPDATE … SET quantity = quantity + :delta WHERE quantity + :delta >= 0``
    so concurrent requests serialize at the DB level.
    """

    delta: int = Field(description="Positive to add, negative to subtract")
    reason: str | None = Field(default=None, max_length=500)


# --- Response shapes -----------------------------------------------------


class CategoryBriefForItem(BaseModel):
    """Nested category for item responses."""

    id: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class ItemResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    category_id: UUID | None = None
    code: str
    name: str
    description: str | None = None
    quantity: int
    min_quantity: int
    unit: str
    location: str | None = None
    supplier: str | None = None
    notes: str | None = None
    status: Status
    is_low_stock: bool
    metadata_: dict | None = Field(default=None, alias="metadata_")
    created_at: datetime
    updated_at: datetime
    category: CategoryBriefForItem | None = None

    model_config = ConfigDict(from_attributes=True)


class ItemDetailResponse(ItemResponse):
    """Detailed item response — same as ItemResponse for V1."""

    pass


class LowStockResponse(BaseModel):
    """Summary of low-stock items for dashboard widgets."""

    item_id: UUID
    code: str
    name: str
    quantity: int
    min_quantity: int
    unit: str
    category_name: str | None = None


# --- Filters (service-layer, not API-facing) ----------------------------


class ItemFilters(BaseModel):
    """Service-layer filter bag — not serialised to the client."""

    status: Status | None = None
    category_id: UUID | None = None
    low_stock: bool = False
    search: str | None = None  # matches code, name, or supplier
