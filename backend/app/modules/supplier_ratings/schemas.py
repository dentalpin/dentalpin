"""Schemas for the supplier_ratings module."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SupplierRatingCreate(BaseModel):
    communication_score: int = Field(ge=1, le=5)
    notes: str | None = Field(default=None, max_length=2000)


class SupplierRatingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    supplier_contact_id: UUID
    communication_score: int
    notes: str | None
    rated_by: UUID | None
    rated_at: datetime


class SupplierPerformanceDashboard(BaseModel):
    """All computed + manual metrics for one supplier.

    Computed fields are None when there's no data yet to compute them
    from (e.g. no fully/partially received POs) — shown as such in the
    UI rather than defaulting to a misleading 0%.
    """

    supplier_contact_id: UUID
    supplier_name: str

    # Computed from purchase_orders + purchase_order_receipts
    on_time_delivery_pct: float | None
    completed_order_count: int
    avg_unit_price: Decimal | None
    quality_good_pct: float | None
    total_receipt_lines: int

    # Manual
    avg_communication_score: float | None
    ratings: list[SupplierRatingResponse] = Field(default_factory=list)
