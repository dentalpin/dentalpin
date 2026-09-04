"""Pydantic schemas for payroll.

Plaintext bank account / tax ID are WRITE-ONLY: they arrive on create /
replace and are never serialized back. Responses expose ``last_4`` +
``has_*`` booleans only.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PayrollProfileCreate(BaseModel):
    user_id: UUID
    payment_type: str = Field(default="monthly", pattern="^(monthly|hourly)$")
    base_amount: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    bank_account: str | None = Field(default=None, max_length=100)
    tax_id: str | None = Field(default=None, max_length=50)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)


class PayrollProfileUpdate(BaseModel):
    payment_type: str | None = Field(default=None, pattern="^(monthly|hourly)$")
    base_amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    # Replace-to-edit: send the full new value to change it; omitted means
    # keep the stored ciphertext. Plaintext is never returned.
    bank_account: str | None = Field(default=None, max_length=100)
    tax_id: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)


class PayrollProfileResponse(BaseModel):
    """Masked profile view. No ciphertext, no plaintext, ever."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    user_id: UUID
    payment_type: str
    base_amount: Decimal | None
    currency: str
    has_bank_account: bool = False
    bank_last_4: str | None = None
    has_tax_id: bool = False
    tax_last_4: str | None = None
    is_active: bool
    country_code: str | None
    created_at: datetime
    updated_at: datetime


class PayrollPeriodCreate(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM")


class PayrollPeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    month: str
    status: str
    created_at: datetime
    updated_at: datetime


class PeriodTransition(BaseModel):
    status: str = Field(pattern="^(draft|closed|paid)$")


class PayrollEntryCreate(BaseModel):
    period_id: UUID
    user_id: UUID
    gross: Decimal = Field(ge=0)
    deductions: Decimal = Field(ge=0)
    net: Decimal = Field(ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class PayrollEntryUpdate(BaseModel):
    gross: Decimal | None = Field(default=None, ge=0)
    deductions: Decimal | None = Field(default=None, ge=0)
    net: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class PayrollEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    period_id: UUID
    user_id: UUID
    gross: Decimal
    deductions: Decimal
    net: Decimal
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PeriodReport(BaseModel):
    period_id: UUID
    month: str
    status: str
    currency: str
    entry_count: int
    total_gross: Decimal
    total_deductions: Decimal
    total_net: Decimal


class AnnualReport(BaseModel):
    year: str
    currency: str
    period_count: int
    entry_count: int
    total_gross: Decimal
    total_deductions: Decimal
    total_net: Decimal
