"""Payroll models: staff payroll profiles, periods, and entries.

Bank/tax fields are Fernet-encrypted at rest via the confirmed real
project-wide pattern (app.core.email.encryption.encrypt_password /
decrypt_password — same as whatsapp_kapso / sms_gateway). NEVER expose
*_encrypted fields, or their decrypted values, in API responses or logs.

Status fields use plain String (with allowed-values documented in a
comment), not a Postgres ENUM type — matches the confirmed real pattern
(WhatsappKapsoTemplate.status, SmsOutboxLog.status), and avoids the
SQLAlchemy Enum values_callable pitfall entirely (the bug that broke the
medications module's unit field).
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class StaffPayrollProfile(Base, TimestampMixin):
    """Payroll profile for one staff member, linked to core users.id.

    Does NOT modify users/clinic_memberships — this is a separate table
    with a FK, per the phase spec's explicit constraint.
    """

    __tablename__ = "staff_payroll_profiles"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    hourly_rate: Mapped[float | None] = mapped_column(Numeric(10, 2))
    base_salary: Mapped[float | None] = mapped_column(Numeric(10, 2))
    tax_regime: Mapped[str | None] = mapped_column(String(50))  # e.g. "employee", "self-employed"

    bank_account_encrypted: Mapped[str | None] = mapped_column(Text)
    tax_id_encrypted: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def has_bank_account(self) -> bool:
        return bool(self.bank_account_encrypted)

    @property
    def has_tax_id(self) -> bool:
        return bool(self.tax_id_encrypted)


class PayrollPeriod(Base, TimestampMixin):
    """One monthly payroll run for a clinic."""

    __tablename__ = "payroll_periods"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    month: Mapped[int] = mapped_column(Integer)  # 1-12
    year: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | processed | paid
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("clinic_id", "month", "year", name="uq_payroll_period_clinic_month_year"),
    )


class PayrollEntry(Base, TimestampMixin):
    """One staff member's calculated pay within a PayrollPeriod."""

    __tablename__ = "payroll_entries"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    period_id: Mapped[UUID] = mapped_column(ForeignKey("payroll_periods.id"), index=True)
    staff_payroll_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_payroll_profiles.id"), index=True
    )

    gross_pay: Mapped[float] = mapped_column(Numeric(10, 2))
    deductions: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    net_pay: Mapped[float] = mapped_column(Numeric(10, 2))
    # Free-form breakdown: bonuses, commissions, tax lines, social security, etc.
    details: Mapped[dict | None] = mapped_column(JSONB)

    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "period_id", "staff_payroll_profile_id", name="uq_payroll_entry_period_staff"
        ),
    )
