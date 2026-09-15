"""Schemas for treasury."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: Literal["cash", "bank"] = "cash"
    opening_balance: Decimal = Field(default=Decimal("0"), ge=0)


class AccountUpdate(BaseModel):
    """All-optional: PATCH semantics with exclude_unset (M4)."""

    name: str | None = Field(default=None, min_length=1, max_length=60)
    is_active: bool | None = None


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    kind: str
    opening_balance: Decimal
    is_active: bool
    balance: Decimal = Decimal("0")


class TransferRequest(BaseModel):
    from_account_id: UUID
    to_account_id: UUID
    amount: Decimal = Field(gt=0, le=Decimal("9999999999.99"))
    memo: str | None = Field(default=None, max_length=500)
    at: datetime | None = None


class CorrectionRequest(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("9999999999.99"))
    direction: Literal["in", "out"]
    memo: str = Field(min_length=1, max_length=500)
    at: datetime | None = None


class EntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    group_id: UUID
    kind: str
    amount: Decimal
    at: datetime
    memo: str | None
