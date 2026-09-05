"""Business logic for payroll (admin-only, no agent tools).

Plaintext bank/tax values exist only as function arguments on the write
path: they are encrypted before insert/update and never logged,
published, or serialized. Reads decrypt transiently to derive ``last_4``.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import User
from app.core.email.encryption import decrypt_password, encrypt_password
from app.core.events import EventType, event_bus

from .models import PayrollEntry, PayrollPeriod, PayrollProfile
from .schemas import (
    PayrollEntryCreate,
    PayrollEntryUpdate,
    PayrollPeriodCreate,
    PayrollProfileCreate,
    PayrollProfileResponse,
    PayrollProfileUpdate,
    PeriodTransition,
)

PERIOD_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"closed"}),
    "closed": frozenset({"paid"}),
    "paid": frozenset(),
}


def _last_4(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    try:
        plaintext = decrypt_password(ciphertext)
    except Exception:
        return None
    if not plaintext:
        return None
    return plaintext[-4:]


def mask_profile(row: PayrollProfile) -> PayrollProfileResponse:
    """Masked view: ciphertext stays in the row, never in the response."""
    return PayrollProfileResponse(
        id=row.id,
        clinic_id=row.clinic_id,
        user_id=row.user_id,
        payment_type=row.payment_type,
        base_amount=row.base_amount,
        currency=row.currency,
        has_bank_account=row.bank_account_encrypted is not None,
        bank_last_4=_last_4(row.bank_account_encrypted),
        has_tax_id=row.tax_id_encrypted is not None,
        tax_last_4=_last_4(row.tax_id_encrypted),
        is_active=row.is_active,
        country_code=row.country_code,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ProfileService:
    @staticmethod
    async def _assert_user(db: AsyncSession, user_id: UUID) -> User:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "user not found")
        return user

    @staticmethod
    async def create_profile(
        db: AsyncSession, clinic_id: UUID, payload: PayrollProfileCreate
    ) -> PayrollProfile:
        await ProfileService._assert_user(db, payload.user_id)
        row = PayrollProfile(
            clinic_id=clinic_id,
            user_id=payload.user_id,
            payment_type=payload.payment_type,
            base_amount=payload.base_amount,
            currency=payload.currency,
            bank_account_encrypted=encrypt_password(payload.bank_account)
            if payload.bank_account
            else None,
            tax_id_encrypted=encrypt_password(payload.tax_id) if payload.tax_id else None,
            country_code=payload.country_code,
        )
        db.add(row)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                "this user already has a payroll profile in this clinic",
            )
        await db.refresh(row)
        await event_bus.publish(
            EventType.PAYROLL_PROFILE_UPDATED,
            {
                "clinic_id": str(clinic_id),
                "profile_id": str(row.id),
                "user_id": str(row.user_id),
            },
            db=db,
        )
        return row

    @staticmethod
    async def get_profile(
        db: AsyncSession, clinic_id: UUID, profile_id: UUID
    ) -> PayrollProfile | None:
        return (
            await db.execute(
                select(PayrollProfile).where(
                    PayrollProfile.id == profile_id, PayrollProfile.clinic_id == clinic_id
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_profiles(
        db: AsyncSession, clinic_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[PayrollProfile], int]:
        stmt = select(PayrollProfile).where(PayrollProfile.clinic_id == clinic_id)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = (
            stmt.order_by(PayrollProfile.created_at.desc())
            .offset((max(page, 1) - 1) * min(max(page_size, 1), 100))
            .limit(min(max(page_size, 1), 100))
        )
        return list((await db.execute(stmt)).scalars()), total

    @staticmethod
    async def update_profile(
        db: AsyncSession, row: PayrollProfile, payload: PayrollProfileUpdate
    ) -> PayrollProfile:
        changes = payload.model_dump(exclude_unset=True)
        for field in ("payment_type", "base_amount", "currency", "is_active", "country_code"):
            if field in changes:
                setattr(row, field, changes[field])
        # Replace-to-edit: only a provided full value rotates the ciphertext.
        if "bank_account" in changes:
            row.bank_account_encrypted = (
                encrypt_password(changes["bank_account"]) if changes["bank_account"] else None
            )
        if "tax_id" in changes:
            row.tax_id_encrypted = (
                encrypt_password(changes["tax_id"]) if changes["tax_id"] else None
            )
        await db.commit()
        await db.refresh(row)
        await event_bus.publish(
            EventType.PAYROLL_PROFILE_UPDATED,
            {
                "clinic_id": str(row.clinic_id),
                "profile_id": str(row.id),
                "user_id": str(row.user_id),
            },
            db=db,
        )
        return row


class PeriodService:
    @staticmethod
    async def create_period(
        db: AsyncSession, clinic_id: UUID, payload: PayrollPeriodCreate
    ) -> PayrollPeriod:
        row = PayrollPeriod(clinic_id=clinic_id, month=payload.month, status="draft")
        db.add(row)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                "this clinic already has a period for this month",
            )
        await db.refresh(row)
        return row

    @staticmethod
    async def get_period(
        db: AsyncSession, clinic_id: UUID, period_id: UUID
    ) -> PayrollPeriod | None:
        return (
            await db.execute(
                select(PayrollPeriod).where(
                    PayrollPeriod.id == period_id, PayrollPeriod.clinic_id == clinic_id
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_periods(
        db: AsyncSession, clinic_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[PayrollPeriod], int]:
        stmt = select(PayrollPeriod).where(PayrollPeriod.clinic_id == clinic_id)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = (
            stmt.order_by(PayrollPeriod.month.desc())
            .offset((max(page, 1) - 1) * min(max(page_size, 1), 100))
            .limit(min(max(page_size, 1), 100))
        )
        return list((await db.execute(stmt)).scalars()), total

    @staticmethod
    async def transition(
        db: AsyncSession, row: PayrollPeriod, payload: PeriodTransition
    ) -> PayrollPeriod:
        if payload.status not in PERIOD_TRANSITIONS.get(row.status, frozenset()):
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                f"cannot move period from {row.status} to {payload.status}",
            )
        old_status = row.status
        row.status = payload.status
        await db.commit()
        await db.refresh(row)
        await event_bus.publish(
            EventType.PAYROLL_PERIOD_STATUS_CHANGED,
            {
                "clinic_id": str(row.clinic_id),
                "period_id": str(row.id),
                "month": row.month,
                "from_status": old_status,
                "to_status": row.status,
            },
            db=db,
        )
        return row


def _assert_balanced(gross: Decimal, deductions: Decimal, net: Decimal) -> None:
    if net != gross - deductions:
        raise HTTPException(
            http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            "net must equal gross minus deductions",
        )


class EntryService:
    @staticmethod
    async def _assert_draft_period(
        db: AsyncSession, clinic_id: UUID, period_id: UUID
    ) -> PayrollPeriod:
        period = await PeriodService.get_period(db, clinic_id, period_id)
        if period is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "period not found")
        if period.status != "draft":
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                "entries can only change while the period is draft",
            )
        return period

    @staticmethod
    async def create_entry(
        db: AsyncSession, clinic_id: UUID, payload: PayrollEntryCreate
    ) -> PayrollEntry:
        await EntryService._assert_draft_period(db, clinic_id, payload.period_id)
        await ProfileService._assert_user(db, payload.user_id)
        _assert_balanced(payload.gross, payload.deductions, payload.net)
        row = PayrollEntry(
            clinic_id=clinic_id,
            period_id=payload.period_id,
            user_id=payload.user_id,
            gross=payload.gross,
            deductions=payload.deductions,
            net=payload.net,
            notes=payload.notes,
        )
        db.add(row)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                "this user already has an entry in this period",
            )
        await db.refresh(row)
        return row

    @staticmethod
    async def get_entry(db: AsyncSession, clinic_id: UUID, entry_id: UUID) -> PayrollEntry | None:
        return (
            await db.execute(
                select(PayrollEntry).where(
                    PayrollEntry.id == entry_id, PayrollEntry.clinic_id == clinic_id
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def update_entry(
        db: AsyncSession, row: PayrollEntry, payload: PayrollEntryUpdate
    ) -> PayrollEntry:
        await EntryService._assert_draft_period(db, row.clinic_id, row.period_id)
        changes = payload.model_dump(exclude_unset=True)
        gross = changes.get("gross", row.gross)
        deductions = changes.get("deductions", row.deductions)
        net = changes.get("net", row.net)
        _assert_balanced(gross, deductions, net)
        for field in ("gross", "deductions", "net", "notes"):
            if field in changes:
                setattr(row, field, changes[field])
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def list_entries(
        db: AsyncSession, clinic_id: UUID, period_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[PayrollEntry], int]:
        period = await PeriodService.get_period(db, clinic_id, period_id)
        if period is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "period not found")
        stmt = select(PayrollEntry).where(
            PayrollEntry.clinic_id == clinic_id, PayrollEntry.period_id == period_id
        )
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = (
            stmt.order_by(PayrollEntry.created_at.desc())
            .offset((max(page, 1) - 1) * min(max(page_size, 1), 100))
            .limit(min(max(page_size, 1), 100))
        )
        return list((await db.execute(stmt)).scalars()), total


class ReportService:
    @staticmethod
    async def _sums(
        db: AsyncSession, clinic_id: UUID, period_ids: list[UUID]
    ) -> tuple[int, Decimal, Decimal, Decimal]:
        if not period_ids:
            return 0, Decimal("0"), Decimal("0"), Decimal("0")
        row = (
            await db.execute(
                select(
                    func.count(PayrollEntry.id),
                    func.coalesce(func.sum(PayrollEntry.gross), 0),
                    func.coalesce(func.sum(PayrollEntry.deductions), 0),
                    func.coalesce(func.sum(PayrollEntry.net), 0),
                ).where(
                    PayrollEntry.clinic_id == clinic_id,
                    PayrollEntry.period_id.in_(period_ids),
                )
            )
        ).one()
        return row[0], Decimal(row[1]), Decimal(row[2]), Decimal(row[3])

    @staticmethod
    async def monthly_report(db: AsyncSession, clinic_id: UUID, month: str) -> dict | None:
        period = (
            await db.execute(
                select(PayrollPeriod).where(
                    PayrollPeriod.clinic_id == clinic_id, PayrollPeriod.month == month
                )
            )
        ).scalar_one_or_none()
        if period is None:
            return None
        count, gross, deductions, net = await ReportService._sums(db, clinic_id, [period.id])
        return {
            "period_id": period.id,
            "month": period.month,
            "status": period.status,
            "entry_count": count,
            "total_gross": gross,
            "total_deductions": deductions,
            "total_net": net,
        }

    @staticmethod
    async def annual_report(db: AsyncSession, clinic_id: UUID, year: str) -> dict:
        periods = list(
            (
                await db.execute(
                    select(PayrollPeriod).where(
                        PayrollPeriod.clinic_id == clinic_id,
                        PayrollPeriod.month.like(f"{year}-%"),
                    )
                )
            ).scalars()
        )
        count, gross, deductions, net = await ReportService._sums(
            db, clinic_id, [p.id for p in periods]
        )
        return {
            "year": year,
            "period_count": len(periods),
            "entry_count": count,
            "total_gross": gross,
            "total_deductions": deductions,
            "total_net": net,
        }
