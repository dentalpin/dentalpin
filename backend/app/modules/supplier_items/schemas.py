"""Pydantic schemas for the supplier_items module."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class SupplierItemCreate(BaseModel):
    supplier_contact_id: UUID
    inventory_item_id: UUID
    supplier_sku: str | None = Field(default=None, max_length=100)
    unit_price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    is_preferred_supplier: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class SupplierItemUpdate(BaseModel):
    supplier_sku: str | None = Field(default=None, max_length=100)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    is_preferred_supplier: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class SupplierItemResponse(BaseModel):
    """Built manually in the service (not via from_attributes) — spans
    three tables (supplier_items, contacts, inventory_items, and
    optionally supplier_profiles for lead_time_days)."""

    id: UUID
    clinic_id: UUID
    supplier_contact_id: UUID
    supplier_name: str
    inventory_item_id: UUID
    item_name: str
    supplier_sku: str | None
    unit_price: Decimal
    is_preferred_supplier: bool
    lead_time_days: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
