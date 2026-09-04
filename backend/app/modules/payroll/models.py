"""Payroll profile/period/entry models.

Bank account + tax ID are stored Fernet-encrypted (see
``app.core.email.encryption``, same scheme as whatsapp_kapso /
verifactu). Plaintext is never persisted, never serialized, never
logged — responses expose ``last_4`` + ``has_*`` booleans only.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic, User


class PayrollProfile(Base, TimestampMixin):
    """Payroll profile for one staff user in a clinic (admin-only data)."""

    __tablename__ = "payroll_profiles"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    payment_type: Mapped[str] = mapped_column(String(20), default="monthly")
    base_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    bank_account_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_id_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)

    __table_args__ = (
        UniqueConstraint("clinic_id", "user_id", name="uq_payroll_profiles_clinic_user"),
    )

    clinic: Mapped[Clinic] = relationship(foreign_keys=[clinic_id])
    user: Mapped[User] = relationship(foreign_keys=[user_id])


class PayrollPeriod(Base, TimestampMixin):
    """One payroll month (YYYY-MM) with a draft → closed → paid lifecycle."""

    __tablename__ = "payroll_periods"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")

    __table_args__ = (
        UniqueConstraint("clinic_id", "month", name="uq_payroll_periods_clinic_month"),
    )

    clinic: Mapped[Clinic] = relationship(foreign_keys=[clinic_id])


class PayrollEntry(Base, TimestampMixin):
    """Per-employee raw entry for a period. Net is stored as entered and
    validated (``net == gross - deductions``) — the entry is the formal
    record for payroll disputes."""

    __tablename__ = "payroll_entries"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True, nullable=False)
    period_id: Mapped[UUID] = mapped_column(
        ForeignKey("payroll_periods.id"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deductions: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    net: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("period_id", "user_id", name="uq_payroll_entries_period_user"),
    )

    clinic: Mapped[Clinic] = relationship(foreign_keys=[clinic_id])
    period: Mapped[PayrollPeriod] = relationship(foreign_keys=[period_id])
    user: Mapped[User] = relationship(foreign_keys=[user_id])
