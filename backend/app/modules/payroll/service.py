"""PayrollService — staff profiles, periods, entries, reports.

Encryption follows the confirmed real pattern (app.core.email.encryption,
same as whatsapp_kapso/sms_gateway): encrypt on write in the service
layer, decrypt only when a specific internal operation needs the
plaintext (never returned to a response schema). db.flush() only — the
request-scoped session commits once at the end (get_db pattern).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import encrypt_password

from .models import PayrollEntry, PayrollPeriod, StaffPayrollProfile


class StaffPayrollProfileService:
    @staticmethod
    async def list(db: AsyncSession, clinic_id: UUID) -> list[StaffPayrollProfile]:
        result = await db.execute(
            select(StaffPayrollProfile)
            .where(StaffPayrollProfile.clinic_id == clinic_id)
            .order_by(StaffPayrollProfile.created_at)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get(
        db: AsyncSession, clinic_id: UUID, profile_id: UUID
    ) -> StaffPayrollProfile | None:
        result = await db.execute(
            select(StaffPayrollProfile).where(
                StaffPayrollProfile.id == profile_id,
                StaffPayrollProfile.clinic_id == clinic_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, clinic_id: UUID, data: dict) -> StaffPayrollProfile:
        bank_account = data.pop("bank_account", None)
        tax_id = data.pop("tax_id", None)
        profile = StaffPayrollProfile(
            clinic_id=clinic_id,
            bank_account_encrypted=encrypt_password(bank_account) if bank_account else None,
            tax_id_encrypted=encrypt_password(tax_id) if tax_id else None,
            **data,
        )
        db.add(profile)
        await db.flush()
        return profile

    @staticmethod
    async def update(
        db: AsyncSession, profile: StaffPayrollProfile, data: dict
    ) -> StaffPayrollProfile:
        if "bank_account" in data:
            bank_account = data.pop("bank_account")
            profile.bank_account_encrypted = (
                encrypt_password(bank_account) if bank_account else None
            )
        if "tax_id" in data:
            tax_id = data.pop("tax_id")
            profile.tax_id_encrypted = encrypt_password(tax_id) if tax_id else None
        for key, value in data.items():
            setattr(profile, key, value)
        await db.flush()
        return profile


class PayrollPeriodService:
    @staticmethod
    async def list(db: AsyncSession, clinic_id: UUID) -> list[PayrollPeriod]:
        result = await db.execute(
            select(PayrollPeriod)
            .where(PayrollPeriod.clinic_id == clinic_id)
            .order_by(PayrollPeriod.year.desc(), PayrollPeriod.month.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get(db: AsyncSession, clinic_id: UUID, period_id: UUID) -> PayrollPeriod | None:
        result = await db.execute(
            select(PayrollPeriod).where(
                PayrollPeriod.id == period_id,
                PayrollPeriod.clinic_id == clinic_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, clinic_id: UUID, month: int, year: int) -> PayrollPeriod:
        period = PayrollPeriod(clinic_id=clinic_id, month=month, year=year, status="draft")
        db.add(period)
        await db.flush()
        return period

    @staticmethod
    async def generate_entries(
        db: AsyncSession, clinic_id: UUID, period: PayrollPeriod
    ) -> list[PayrollEntry]:
        """Create one draft entry per active staff profile for this period.

        Gross pay defaults to base_salary when set (salaried staff);
        hourly staff get a 0 default since hours-worked isn't tracked
        anywhere yet — the admin fills in the real gross_pay per entry
        before marking the period processed. This is a deliberate MVP
        simplification, not a hidden assumption: flagged here and in
        the install guide.
        """
        profiles = await StaffPayrollProfileService.list(db, clinic_id)
        entries: list[PayrollEntry] = []
        for profile in profiles:
            if not profile.is_active:
                continue
            existing = await db.execute(
                select(PayrollEntry).where(
                    PayrollEntry.period_id == period.id,
                    PayrollEntry.staff_payroll_profile_id == profile.id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            gross = float(profile.base_salary) if profile.base_salary is not None else 0.0
            entry = PayrollEntry(
                clinic_id=clinic_id,
                period_id=period.id,
                staff_payroll_profile_id=profile.id,
                gross_pay=gross,
                deductions=0,
                net_pay=gross,
            )
            db.add(entry)
            entries.append(entry)
        await db.flush()
        return entries

    @staticmethod
    async def mark_processed(db: AsyncSession, period: PayrollPeriod) -> PayrollPeriod:
        period.status = "processed"
        period.processed_at = datetime.now(UTC)
        await db.flush()
        return period

    @staticmethod
    async def mark_paid(db: AsyncSession, period: PayrollPeriod) -> PayrollPeriod:
        period.status = "paid"
        await db.flush()
        return period


class PayrollEntryService:
    @staticmethod
    async def list_for_period(
        db: AsyncSession, clinic_id: UUID, period_id: UUID
    ) -> list[PayrollEntry]:
        result = await db.execute(
            select(PayrollEntry).where(
                PayrollEntry.clinic_id == clinic_id,
                PayrollEntry.period_id == period_id,
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get(db: AsyncSession, clinic_id: UUID, entry_id: UUID) -> PayrollEntry | None:
        result = await db.execute(
            select(PayrollEntry).where(
                PayrollEntry.id == entry_id,
                PayrollEntry.clinic_id == clinic_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update(db: AsyncSession, entry: PayrollEntry, data: dict) -> PayrollEntry:
        for key, value in data.items():
            setattr(entry, key, value)
        entry.net_pay = float(entry.gross_pay) - float(entry.deductions)
        await db.flush()
        return entry

    @staticmethod
    async def mark_paid(db: AsyncSession, entry: PayrollEntry) -> PayrollEntry:
        entry.is_paid = True
        entry.paid_at = datetime.now(UTC)
        await db.flush()
        return entry


class PayrollReportService:
    @staticmethod
    async def monthly_summary(db: AsyncSession, clinic_id: UUID, month: int, year: int) -> dict:
        period_result = await db.execute(
            select(PayrollPeriod).where(
                PayrollPeriod.clinic_id == clinic_id,
                PayrollPeriod.month == month,
                PayrollPeriod.year == year,
            )
        )
        period = period_result.scalar_one_or_none()
        if period is None:
            return {
                "month": month,
                "year": year,
                "status": "none",
                "total_gross": 0.0,
                "total_deductions": 0.0,
                "total_net": 0.0,
                "employee_count": 0,
            }

        totals = await db.execute(
            select(
                func.coalesce(func.sum(PayrollEntry.gross_pay), 0),
                func.coalesce(func.sum(PayrollEntry.deductions), 0),
                func.coalesce(func.sum(PayrollEntry.net_pay), 0),
                func.count(PayrollEntry.id),
            ).where(PayrollEntry.period_id == period.id)
        )
        gross, deductions, net, count = totals.one()
        return {
            "month": month,
            "year": year,
            "status": period.status,
            "total_gross": float(gross),
            "total_deductions": float(deductions),
            "total_net": float(net),
            "employee_count": count,
        }

    @staticmethod
    async def annual_summary(db: AsyncSession, clinic_id: UUID, year: int) -> dict:
        totals = await db.execute(
            select(
                func.coalesce(func.sum(PayrollEntry.gross_pay), 0),
                func.coalesce(func.sum(PayrollEntry.deductions), 0),
                func.coalesce(func.sum(PayrollEntry.net_pay), 0),
                func.count(func.distinct(PayrollEntry.period_id)),
            )
            .select_from(PayrollEntry)
            .join(PayrollPeriod, PayrollPeriod.id == PayrollEntry.period_id)
            .where(PayrollPeriod.clinic_id == clinic_id, PayrollPeriod.year == year)
        )
        gross, deductions, net, months_processed = totals.one()
        return {
            "year": year,
            "total_gross": float(gross),
            "total_deductions": float(deductions),
            "total_net": float(net),
            "months_processed": months_processed,
        }
