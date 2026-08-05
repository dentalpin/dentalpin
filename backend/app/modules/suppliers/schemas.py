"""Pydantic schemas for the suppliers module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SupplierProfileUpsert(BaseModel):
    website: str | None = Field(default=None, max_length=255)
    payment_terms: str | None = Field(default=None, max_length=100)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    is_preferred: bool = False


class SupplierProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contact_id: UUID
    clinic_id: UUID
    website: str | None
    payment_terms: str | None
    lead_time_days: int | None
    is_preferred: bool
    created_at: datetime
    updated_at: datetime


class SupplierResponse(BaseModel):
    """Flattened Contact + SupplierProfile view. Built manually in the
    router (not via from_attributes) since it spans two tables — see
    `_to_response` in router.py."""

    contact_id: UUID
    name: str
    phone: str | None
    email: str | None
    address: str | None
    notes: str | None
    is_active: bool
    website: str | None
    payment_terms: str | None
    lead_time_days: int | None
    is_preferred: bool
