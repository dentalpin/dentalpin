"""Pydantic schemas for the expenses module."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ExpenseCategory = Literal[
    "rent",
    "utilities",
    "salaries",
    "supplies",
    "equipment",
    "insurance",
    "maintenance",
    "other",
]


class ExpenseCreate(BaseModel):
    category: ExpenseCategory
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    expense_date: date
    description: str | None = Field(default=None, max_length=2000)


class ExpenseUpdate(BaseModel):
    category: ExpenseCategory | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    expense_date: date | None = None
    description: str | None = Field(default=None, max_length=2000)


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    category: ExpenseCategory
    amount: Decimal
    expense_date: date
    description: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class ExpenseMonthlyTotal(BaseModel):
    """One row of the monthly-total-by-category summary."""

    category: ExpenseCategory
    total: Decimal
