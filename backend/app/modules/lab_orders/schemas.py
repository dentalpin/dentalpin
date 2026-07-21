"""Pydantic schemas for the lab_orders module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

WorkType = Literal[
    "crown", "bridge", "denture", "implant", "veneer", "orthodontic", "repair", "other"
]
OrderStatus = Literal["sent", "in_progress", "ready", "received", "cancelled"]
ImpressionType = Literal["alginate", "pvs_silicone", "digital_scan", "other"]
# Vita Classical shade guide (16 shades, no D1).
ShadeSelection = Literal[
    "A1", "A2", "A3", "A3.5", "A4",
    "B1", "B2", "B3", "B4",
    "C1", "C2", "C3", "C4",
    "D2", "D3", "D4",
]


class LabOrderCreate(BaseModel):
    patient_id: UUID
    lab_contact_id: UUID
    work_type: WorkType
    tooth_reference: str | None = Field(default=None, max_length=50)
    impression_type: ImpressionType | None = None
    antagonist_info: str | None = Field(default=None, max_length=500)
    shade: ShadeSelection | None = None
    sent_date: date
    expected_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class LabOrderUpdate(BaseModel):
    lab_contact_id: UUID | None = None
    work_type: WorkType | None = None
    tooth_reference: str | None = Field(default=None, max_length=50)
    impression_type: ImpressionType | None = None
    antagonist_info: str | None = Field(default=None, max_length=500)
    shade: ShadeSelection | None = None
    status: OrderStatus | None = None
    expected_date: date | None = None
    received_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class LabOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    patient_name: str
    lab_contact_id: UUID
    lab_contact_name: str
    work_type: WorkType
    tooth_reference: str | None
    impression_type: ImpressionType | None
    antagonist_info: str | None
    shade: ShadeSelection | None
    status: OrderStatus
    sent_date: date
    expected_date: date | None
    received_date: date | None
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
