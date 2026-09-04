"""supplier_ratings schemas - manual 1-5 review plus on-demand metrics."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SupplierReviewCreate(BaseModel):
    supplier_id: UUID
    score: int = Field(ge=1, le=5, description="1-5 communication rating")
    comment: str | None = Field(default=None, max_length=2000)


class SupplierReviewUpdate(BaseModel):
    score: int = Field(ge=1, le=5, description="1-5 communication rating")
    comment: str | None = Field(default=None, max_length=2000)


class SupplierReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    supplier_id: UUID
    score: int
    comment: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class SupplierRatingMetrics(BaseModel):
    """Delivery/quality figures derived from purchase order history."""

    po_count: int = 0
    received_count: int = 0
    received_with_due_date: int = 0
    on_time_deliveries: int = 0
    on_time_rate: Decimal | None = None
    received_quantity: Decimal = Decimal("0")
    rejected_quantity: Decimal = Decimal("0")
    reject_rate: Decimal | None = None


class SupplierRatingResponse(BaseModel):
    supplier_id: UUID
    supplier_name: str
    metrics: SupplierRatingMetrics
    review: SupplierReviewResponse | None = None
