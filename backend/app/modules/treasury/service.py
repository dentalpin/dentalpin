"""TreasuryService — accounts, transfers, corrections, balances.

The ledger is append-only: money moves via paired transfer legs sharing
a ``group_id``, or single manual corrections (memo required — silent
money edits are an audit hole). Balances are always derived
(opening + signed entries), never stored. Payment/expense auto-posting
is explicitly Later.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import case, func, select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.events import EventType, event_bus

from .models import TreasuryAccount, TreasuryEntry

DEFAULT_TIMEZONE = "Europe/Madrid"

# Tolerance for device clock skew on manual timestamps. Anything further
# ahead of now is a typo — same house rule as staff_attendance.
CLOCK_SKEW = timedelta(minutes=5)

_SIGN = {
    "transfer_out": Decimal("-1"),
    "transfer_in": Decimal("1"),
    "correction_in": Decimal("1"),
    "correction_out": Decimal("-1"),
    "opening": Decimal("1"),
}


class TreasuryService:
    @staticmethod
    async def _clinic_zone(db: AsyncSession, clinic_id: UUID):
        """Clinic-local zone (house rule: naive datetimes are clinic wall-clock).

        Same semantics as ``agenda/tz.py`` without taking an agenda
        dependency — mirrors the staff_attendance precedent.
        """
        result = await db.execute(select(Clinic.timezone).where(Clinic.id == clinic_id))
        try:
            return ZoneInfo(result.scalar_one_or_none() or DEFAULT_TIMEZONE)
        except ZoneInfoNotFoundError:
            return ZoneInfo(DEFAULT_TIMEZONE)

    @staticmethod
    def _as_utc(at: datetime, tz) -> datetime:
        """Naive → attach clinic tz; aware → keep instant. Always UTC."""
        if at.tzinfo is None:
            at = at.replace(tzinfo=tz)
        return at.astimezone(UTC)

    @staticmethod
    async def list_accounts(db: AsyncSession, clinic_id: UUID) -> list[TreasuryAccount]:
        stmt = (
            select(TreasuryAccount)
            .where(TreasuryAccount.clinic_id == clinic_id)
            .order_by(TreasuryAccount.name)
        )
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def get_account(
        db: AsyncSession, clinic_id: UUID, account_id: UUID
    ) -> TreasuryAccount | None:
        stmt = select(TreasuryAccount).where(
            TreasuryAccount.id == account_id, TreasuryAccount.clinic_id == clinic_id
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def balance(db: AsyncSession, account: TreasuryAccount) -> Decimal:
        return (await TreasuryService.balances(db, account.clinic_id)).get(
            account.id, account.opening_balance or Decimal("0")
        )

    @staticmethod
    async def balances(db: AsyncSession, clinic_id: UUID) -> dict[UUID, Decimal]:
        """All account balances in one aggregate query (no N+1).

        The sign map is derived from ``_SIGN`` so SQL and Python can
        never drift apart.
        """
        negative = [kind for kind, sign in _SIGN.items() if sign < 0]
        sign = case((TreasuryEntry.kind.in_(negative), -1), else_=1)
        rows = (
            await db.execute(
                select(
                    TreasuryEntry.account_id,
                    func.sum(TreasuryEntry.amount * sign),
                )
                .where(TreasuryEntry.clinic_id == clinic_id)
                .group_by(TreasuryEntry.account_id)
            )
        ).all()
        out = {account_id: total or Decimal("0") for account_id, total in rows}
        accounts = await TreasuryService.list_accounts(db, clinic_id)
        return {
            account.id: (account.opening_balance or Decimal("0"))
            + out.get(account.id, Decimal("0"))
            for account in accounts
        }

    @staticmethod
    async def create_account(db: AsyncSession, clinic_id: UUID, data: dict) -> TreasuryAccount:
        row = TreasuryAccount(clinic_id=clinic_id, **data)
        if row.opening_balance is not None:
            row.opening_balance = row.opening_balance.quantize(Decimal("0.01"))
        db.add(row)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="An account with this name already exists",
            ) from exc
        except DataError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Opening balance is out of range",
            ) from exc
        return row

    @staticmethod
    async def update_account(db: AsyncSession, row: TreasuryAccount, data: dict) -> TreasuryAccount:
        for key, value in data.items():
            setattr(row, key, value)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="An account with this name already exists",
            ) from exc
        return row

    @staticmethod
    async def delete_account(db: AsyncSession, row: TreasuryAccount) -> None:
        # Refuse when ledger history exists — deleting an account with
        # entries would drop its audit trail (entries cascade). Deactivate
        # via PATCH instead (AccountUpdate.is_active).
        entries = (
            await db.execute(
                select(func.count())
                .select_from(TreasuryEntry)
                .where(TreasuryEntry.account_id == row.id)
            )
        ).scalar_one()
        if entries:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Account has ledger entries — deactivate it instead of deleting",
            )
        await db.delete(row)
        await db.flush()

    @staticmethod
    async def transfer(
        db: AsyncSession,
        clinic_id: UUID,
        from_account: TreasuryAccount,
        to_account: TreasuryAccount,
        amount: Decimal,
        memo: str | None,
        at: datetime | None,
        created_by: UUID | None = None,
    ) -> list[TreasuryEntry]:
        if from_account.id == to_account.id:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Source and destination must differ",
            )
        for account in (from_account, to_account):
            if not account.is_active:
                raise HTTPException(
                    status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Account '{account.name}' is deactivated",
                )
        tz = await TreasuryService._clinic_zone(db, clinic_id)
        stamp = TreasuryService._as_utc(at or datetime.now(UTC), tz)
        if stamp > datetime.now(UTC) + CLOCK_SKEW:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Movement timestamp is in the future",
            )
        amount = amount.quantize(Decimal("0.01"))
        group_id = uuid4()
        legs = [
            TreasuryEntry(
                clinic_id=clinic_id,
                account_id=from_account.id,
                group_id=group_id,
                kind="transfer_out",
                amount=amount,
                at=stamp,
                memo=memo,
                created_by=created_by,
            ),
            TreasuryEntry(
                clinic_id=clinic_id,
                account_id=to_account.id,
                group_id=group_id,
                kind="transfer_in",
                amount=amount,
                at=stamp,
                memo=memo,
                created_by=created_by,
            ),
        ]
        db.add_all(legs)
        await db.flush()
        await event_bus.publish(
            EventType.TREASURY_TRANSFERRED,
            {
                "clinic_id": str(clinic_id),
                "group_id": str(group_id),
                "from_account_id": str(from_account.id),
                "to_account_id": str(to_account.id),
                "amount": str(amount),
                "created_by": str(created_by) if created_by else None,
            },
            db=db,
        )
        return legs

    @staticmethod
    async def correct(
        db: AsyncSession,
        clinic_id: UUID,
        account: TreasuryAccount,
        amount: Decimal,
        direction: str,
        memo: str,
        at: datetime | None,
        created_by: UUID | None = None,
    ) -> TreasuryEntry:
        if not account.is_active:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Account '{account.name}' is deactivated",
            )
        tz = await TreasuryService._clinic_zone(db, clinic_id)
        stamp = TreasuryService._as_utc(at or datetime.now(UTC), tz)
        if stamp > datetime.now(UTC) + CLOCK_SKEW:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Movement timestamp is in the future",
            )
        row = TreasuryEntry(
            clinic_id=clinic_id,
            account_id=account.id,
            group_id=uuid4(),
            kind=f"correction_{direction}",
            amount=amount.quantize(Decimal("0.01")),
            at=stamp,
            memo=memo,
            created_by=created_by,
        )
        db.add(row)
        await db.flush()
        await event_bus.publish(
            EventType.TREASURY_CORRECTED,
            {
                "clinic_id": str(clinic_id),
                "account_id": str(account.id),
                "entry_id": str(row.id),
                "amount": str(row.amount),
                "direction": direction,
                "memo": memo,
                "created_by": str(created_by) if created_by else None,
            },
            db=db,
        )
        return row

    @staticmethod
    async def statement(
        db: AsyncSession, clinic_id: UUID, account_id: UUID, limit: int = 100
    ) -> list[TreasuryEntry]:
        stmt = (
            select(TreasuryEntry)
            .where(
                TreasuryEntry.account_id == account_id,
                TreasuryEntry.clinic_id == clinic_id,
            )
            .order_by(TreasuryEntry.at.desc(), TreasuryEntry.created_at.desc())
            .limit(min(limit, 500))
        )
        return (await db.execute(stmt)).scalars().all()
