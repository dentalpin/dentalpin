"""Pydantic schemas for payroll.

CRITICAL: bank_account_encrypted / tax_id_encrypted are NEVER in any
response schema below — only plaintext bank_account/tax_id go in
Create/Update (write-only, encrypted before storage), and Response
schemas expose neither the ciphertext nor the plaintext. If you ever
need to display a masked hint (last 4 digits), add that as a separate
explicit field computed in the service layer — do not add the raw
encrypted or decrypted value to a response schema.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --- Staff payroll profile ------------------------------------------------


class StaffPayrollProfileCreate(BaseModel):
    user_id: UUID
    hourly_rate: float | None = Field(default=None, ge=0)
    base_salary: float | None = Field(default=None, ge=0)
    tax_regime: str | None = Field(default=None, max_length=50)
    bank_account: str | None = None  # plaintext in, encrypted by the service
    tax_id: str | None = None  # plaintext in, encrypted by the service
    is_active: bool = True


class StaffPayrollProfileUpdate(BaseModel):
    hourly_rate: float | None = Field(default=None, ge=0)
    base_salary: float | None = Field(default=None, ge=0)
    tax_regime: str | None = Field(default=None, max_length=50)
    bank_account: str | None = None
    tax_id: str | None = None
    is_active: bool | None = None


class StaffPayrollProfileResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    user_id: UUID
    hourly_rate: float | None
    base_salary: float | None
    tax_regime: str | None
    has_bank_account: bool  # computed — never the value itself
    has_tax_id: bool  # computed — never the value itself
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Payroll period --------------------------------------------------------


class PayrollPeriodCreate(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)


class PayrollPeriodResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    month: int
    year: int
    status: str
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Payroll entry -----------------------------------------------------------


class PayrollEntryCreate(BaseModel):
    staff_payroll_profile_id: UUID
    gross_pay: float = Field(ge=0)
    deductions: float = Field(default=0, ge=0)
    details: dict | None = None


class PayrollEntryResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    period_id: UUID
    staff_payroll_profile_id: UUID
    gross_pay: float
    deductions: float
    net_pay: float
    details: dict | None
    is_paid: bool
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Reports -----------------------------------------------------------------


class MonthlySummaryResponse(BaseModel):
    month: int
    year: int
    status: str
    total_gross: float
    total_deductions: float
    total_net: float
    employee_count: int


class AnnualSummaryResponse(BaseModel):
    year: int
    total_gross: float
    total_deductions: float
    total_net: float
    months_processed: int
