"""Pydantic schemas for the gdpr module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

RequestType = Literal["access", "rectification", "erasure", "portability", "restrict"]
RequestStatus = Literal["received", "in_progress", "completed", "rejected"]


class GdprRequestCreate(BaseModel):
    patient_id: UUID | None = None
    requester_name: str = Field(min_length=1, max_length=200)
    requester_email: EmailStr
    request_type: RequestType
    notes: str | None = Field(default=None, max_length=2000)


class GdprRequestUpdate(BaseModel):
    status: RequestStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)


class GdprRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID | None
    requester_name: str
    requester_email: str
    request_type: str
    status: str
    received_at: datetime
    deadline_at: datetime
    resolved_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ConsentCreate(BaseModel):
    patient_id: UUID
    purpose: str = Field(min_length=1, max_length=100)
    granted: bool = True
    provided_text: str | None = Field(default=None, max_length=4000)


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    purpose: str
    granted: bool
    provided_text: str | None
    granted_at: datetime | None
    withdrawn_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RetentionPolicyCreate(BaseModel):
    data_category: str = Field(min_length=1, max_length=100)
    retention_years: int = Field(ge=0)
    legal_hold_until: date | None = None


class RetentionPolicyUpdate(BaseModel):
    retention_years: int | None = Field(default=None, ge=0)
    legal_hold_until: date | None = None
    is_active: bool | None = None


class RetentionPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    data_category: str
    retention_years: int
    legal_hold_until: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ErasureRequest(BaseModel):
    """Define which data categories to erase for a patient."""

    patient_id: UUID
    # Categories to erase; each must map to an active retention policy.
    categories: list[str] = Field(min_length=1)
    rationale: str | None = Field(default=None, max_length=2000)


class ErasureResult(BaseModel):
    """Result of a partial erasure run."""

    patient_id: UUID
    erased_categories: list[str]
    audit_log_id: UUID
    # Patient identity fields kept under the legal-hold gate, if any.
    retained_categories: list[str] = Field(default_factory=list)


class ErasureAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID | None
    request_id: UUID | None
    erased_categories: list
    fields_blanked: dict | None
    rationale: str | None
    executed_at: datetime
    executed_by: UUID | None
    created_at: datetime
    updated_at: datetime


class DataBreachCreate(BaseModel):
    occurred_at: datetime | None = None
    description: str = Field(min_length=1, max_length=4000)
    data_involved: list[str] = Field(min_length=0)
    affected_people: int | None = Field(default=None, ge=0)


class DataBreachUpdate(BaseModel):
    status: Literal["under_review", "reported", "not_reportable", "resolved"] | None = None
    notified_authority_at: datetime | None = None


class DataBreachResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    occurred_at: datetime
    description: str
    data_involved: list
    affected_people: int | None
    status: str
    notified_authority_at: datetime | None
    reported: bool
    created_at: datetime
    updated_at: datetime


class ExportResponse(BaseModel):
    """Portable data export payload."""

    patient_id: UUID
    definition_year: int
    clinic_id: UUID
    data: dict
