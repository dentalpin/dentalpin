"""Pydantic schemas for the supplier_items module."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from .models import SupplierItem


class SupplierItemCreate(BaseModel):
    """Schema for linking a supplier to an inventory item."""

    supplier_id: UUID
    inventory_item_id: UUID
    supplier_sku: str | None = Field(default=None, max_length=100)
    price: Decimal | None = Field(default=None, ge=0)


class SupplierItemUpdate(BaseModel):
    """Schema for editing price/SKU on an existing link."""

    supplier_sku: str | None = Field(default=None, max_length=100)
    price: Decimal | None = Field(default=None, ge=0)


class SupplierItemResponse(BaseModel):
    """Link row plus denormalized supplier and item names for readable lists."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    supplier_id: UUID
    inventory_item_id: UUID
    supplier_sku: str | None
    price: Decimal | None
    # Soft-delete flag (L7): removed links are kept for historical references.
    is_active: bool = True

    # Denormalized for UI/readability (via the Contact.name join).
    supplier_name: str
    item_name: str

    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_link(
        cls, link: SupplierItem, supplier_name: str, item_name: str
    ) -> SupplierItemResponse:
        return cls(
            id=link.id,
            clinic_id=link.clinic_id,
            supplier_id=link.supplier_id,
            inventory_item_id=link.inventory_item_id,
            supplier_sku=link.supplier_sku,
            price=link.price,
            is_active=link.is_active,
            supplier_name=supplier_name,
            item_name=item_name,
            created_at=link.created_at,
            updated_at=link.updated_at,
        )
