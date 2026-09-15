"""AttendanceService — clock events, current state, daily pairing report.

Events are append-only (no update/delete routes). A consecutive same-kind
punch answers 409 — the roster, not the log, is where corrections happen
(a later opposite punch supersedes; nothing is rewritten).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from uuid import UUID

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import ClinicMembership, User

from .models import AttendanceEvent


class AttendanceService:
    @staticmethod
    async def list_members(db: AsyncSession, clinic_id: UUID) -> list[dict]:
        """Clinic members the picker can clock — clinic-scoped, active only."""
        stmt = (
            select(ClinicMembership, User.id, User.first_name, User.last_name)
            .join(User, User.id == ClinicMembership.user_id)
            .where(
                ClinicMembership.clinic_id == clinic_id,
                User.is_active.is_(True),
            )
            .order_by(User.first_name, User.last_name)
        )
        rows = (await db.execute(stmt)).all()
        return [
            {
                "id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "role": membership.role,
            }
            for membership, user_id, first_name, last_name in rows
        ]

    @staticmethod
    async def _assert_member(db: AsyncSession, clinic_id: UUID, user_id: UUID) -> None:
        """Users are global rows: only clinic members can be clocked here,
        otherwise an admin could punch another clinic's staff (and probe
        user ids) — same rule as payroll profiles."""
        member = (
            await db.execute(
                select(ClinicMembership.id).where(
                    ClinicMembership.clinic_id == clinic_id,
                    ClinicMembership.user_id == user_id,
                )
            )
        ).first()
        if member is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "user not found")

    @staticmethod
    async def _last_event(
        db: AsyncSession, clinic_id: UUID, user_id: UUID
    ) -> AttendanceEvent | None:
        stmt = (
            select(AttendanceEvent)
            .where(
                AttendanceEvent.clinic_id == clinic_id,
                AttendanceEvent.user_id == user_id,
            )
            .order_by(desc(AttendanceEvent.at), desc(AttendanceEvent.created_at))
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def clock(
        db: AsyncSession,
        clinic_id: UUID,
        user_id: UUID,
        kind: str,
        at: datetime | None = None,
        note: str | None = None,
    ) -> AttendanceEvent:
        await AttendanceService._assert_member(db, clinic_id, user_id)
        last = await AttendanceService._last_event(db, clinic_id, user_id)
        if last is not None and last.kind == kind:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Already clocked {kind}",
            )
        row = AttendanceEvent(
            clinic_id=clinic_id,
            user_id=user_id,
            kind=kind,
            at=at or datetime.now(UTC),
            note=note,
        )
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def list_events(
        db: AsyncSession,
        clinic_id: UUID,
        user_id: UUID | None = None,
        day: date | None = None,
        limit: int = 100,
    ) -> list[AttendanceEvent]:
        stmt = select(AttendanceEvent).where(AttendanceEvent.clinic_id == clinic_id)
        if user_id is not None:
            stmt = stmt.where(AttendanceEvent.user_id == user_id)
        if day is not None:
            start = datetime.combine(day, time.min, tzinfo=UTC)
            end = datetime.combine(day, time.max, tzinfo=UTC)
            stmt = stmt.where(AttendanceEvent.at >= start, AttendanceEvent.at <= end)
        stmt = stmt.order_by(desc(AttendanceEvent.at)).limit(min(limit, 500))
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def get_status(
        db: AsyncSession, clinic_id: UUID, user_id: UUID
    ) -> tuple[str, datetime | None]:
        await AttendanceService._assert_member(db, clinic_id, user_id)
        last = await AttendanceService._last_event(db, clinic_id, user_id)
        if last is None or last.kind == "out":
            return "out", last.at if last else None
        return "in", last.at

    @staticmethod
    async def daily_report(
        db: AsyncSession, clinic_id: UUID, day: date, now: datetime | None = None
    ) -> list[dict]:
        """Pair in→out punches per member for one UTC day. An unpaired
        trailing ``in`` counts up to query time and is flagged open."""
        now = now or datetime.now(UTC)
        start = datetime.combine(day, time.min, tzinfo=UTC)
        end = datetime.combine(day, time.max, tzinfo=UTC)
        stmt = (
            select(AttendanceEvent, User.first_name, User.last_name)
            .join(User, User.id == AttendanceEvent.user_id)
            .where(
                AttendanceEvent.clinic_id == clinic_id,
                AttendanceEvent.at >= start,
                AttendanceEvent.at <= end,
            )
            .order_by(AttendanceEvent.user_id, AttendanceEvent.at)
        )
        rows = (await db.execute(stmt)).all()
        by_user: dict[UUID, dict] = {}
        for event, first, last in rows:
            slot = by_user.setdefault(
                event.user_id, {"name": f"{first} {last}", "seconds": 0, "open_since": None}
            )
            if event.kind == "in":
                slot["open_since"] = event.at
            elif slot["open_since"] is not None:
                slot["seconds"] += int((event.at - slot["open_since"]).total_seconds())
                slot["open_since"] = None
        return [
            {
                "user_id": uid,
                "full_name": slot["name"],
                "seconds": slot["seconds"]
                + (int((now - slot["open_since"]).total_seconds()) if slot["open_since"] else 0),
                "open": slot["open_since"] is not None,
            }
            for uid, slot in sorted(by_user.items(), key=lambda kv: kv[1]["name"])
        ]
