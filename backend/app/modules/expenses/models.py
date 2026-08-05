"""Expense entity — fixed/recurring office costs (rent, utilities, salaries, etc.)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin

EXPENSE_CATEGORIES = (
    "rent",
    "utilities",
    "salaries",
    "supplies",
    "equipment",
    "insurance",
    "maintenance",
    "other",
)


class Expense(Base, TimestampMixin):
    """A single office expense entry, tied to a clinic and a category."""

    __tablename__ = "expenses"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    category: Mapped[str] = mapped_column(String(20), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    expense_date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
