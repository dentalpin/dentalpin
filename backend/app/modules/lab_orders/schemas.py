"""Pydantic schemas for the lab_orders module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

WorkType = Literal[
    "crown", "bridge", "denture", "implant", "veneer", "orthodontic", "other"
]
OrderStatus = Literal["sent", "in_progress", "ready", "received", "cancelled"]


class LabOrderCreate(BaseModel):
    patient_id: UUID
    lab_contact_id: UUID
    work_type: WorkType
    tooth_reference: str | None = Field(default=None, max_length=50)
    sent_date: date
    expected_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class LabOrderUpdate(BaseModel):
    lab_contact_id: UUID | None = None
    work_type: WorkType | None = None
    tooth_reference: str | None = Field(default=None, max_length=50)
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
    status: OrderStatus
    sent_date: date
    expected_date: date | None
    received_date: date | None
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
