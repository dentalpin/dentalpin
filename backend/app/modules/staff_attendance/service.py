"""AttendanceService — clock events, current state, daily pairing report.

Events are append-only (no update/delete routes). A consecutive same-kind
punch answers 409 — the roster, not the log, is where corrections happen
(a later opposite punch supersedes; nothing is rewritten).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.events import EventType, event_bus

from .models import AttendanceEvent

DEFAULT_TIMEZONE = "Europe/Madrid"

# Tolerance for device clock skew on manual punches. Anything further
# ahead of now is a typo (e.g. an `out` dated 2030 that would answer 409
# on every later punch, with no void route to undo it).
CLOCK_SKEW = timedelta(minutes=5)


class AttendanceService:
    @staticmethod
    async def _clinic_zone(db: AsyncSession, clinic_id: UUID) -> ZoneInfo:
        """Clinic-local zone (house rule: naive datetimes are clinic wall-clock).

        Same semantics as ``agenda/tz.py`` without taking an agenda
        dependency (schedules precedent: low coupling over reuse).
        """
        result = await db.execute(select(Clinic.timezone).where(Clinic.id == clinic_id))
        try:
            return ZoneInfo(result.scalar_one_or_none() or DEFAULT_TIMEZONE)
        except ZoneInfoNotFoundError:
            return ZoneInfo(DEFAULT_TIMEZONE)

    @staticmethod
    def _as_utc(at: datetime, tz: ZoneInfo) -> datetime:
        """Naive → attach clinic tz; aware → keep instant. Always UTC."""
        if at.tzinfo is None:
            at = at.replace(tzinfo=tz)
        return at.astimezone(UTC)

    @staticmethod
    async def _day_bounds_utc(
        db: AsyncSession, clinic_id: UUID, day: date
    ) -> tuple[datetime, datetime]:
        """Half-open day window in UTC: [local midnight, next local midnight).

        Half-open (not ``time.max``/``<=``) so a punch at exactly midnight
        belongs to the day it starts and no second is lost per segment.
        """
        tz = await AttendanceService._clinic_zone(db, clinic_id)
        start = datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)
        end = (datetime.combine(day, time.min, tzinfo=tz) + timedelta(days=1)).astimezone(UTC)
        return start, end

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
        created_by: UUID | None = None,
    ) -> AttendanceEvent:
        await AttendanceService._assert_member(db, clinic_id, user_id)
        tz = await AttendanceService._clinic_zone(db, clinic_id)
        at = AttendanceService._as_utc(at or datetime.now(UTC), tz)
        if at > datetime.now(UTC) + CLOCK_SKEW:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Punch time is in the future",
            )
        # Alternation is positional, not tail-based: the new punch must
        # differ from both neighbours, so backdated inserts cannot slip
        # past the duplicate guard.
        prev_stmt = (
            select(AttendanceEvent)
            .where(
                AttendanceEvent.clinic_id == clinic_id,
                AttendanceEvent.user_id == user_id,
                AttendanceEvent.at <= at,
            )
            .order_by(desc(AttendanceEvent.at), desc(AttendanceEvent.created_at))
            .limit(1)
        )
        prev = (await db.execute(prev_stmt)).scalar_one_or_none()
        if prev is not None and prev.kind == kind:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Already clocked {kind}",
            )
        next_stmt = (
            select(AttendanceEvent)
            .where(
                AttendanceEvent.clinic_id == clinic_id,
                AttendanceEvent.user_id == user_id,
                AttendanceEvent.at > at,
            )
            .order_by(AttendanceEvent.at, AttendanceEvent.created_at)
            .limit(1)
        )
        nxt = (await db.execute(next_stmt)).scalar_one_or_none()
        if nxt is not None and nxt.kind == kind:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Already clocked {kind}",
            )
        row = AttendanceEvent(
            clinic_id=clinic_id,
            user_id=user_id,
            kind=kind,
            at=at,
            note=note,
            created_by=created_by,
        )
        db.add(row)
        await db.flush()
        await event_bus.publish(
            EventType.STAFF_ATTENDANCE_CLOCKED,
            {
                "event_id": str(row.id),
                "clinic_id": str(clinic_id),
                "user_id": str(user_id),
                "kind": kind,
                "created_by": str(created_by) if created_by else None,
            },
            db=db,
        )
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
            start, end = await AttendanceService._day_bounds_utc(db, clinic_id, day)
            stmt = stmt.where(AttendanceEvent.at >= start, AttendanceEvent.at < end)
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
        """Pair in→out punches per member for one clinic-local day.

        Every in→out pair is clipped to the window on both ends —
        ``max(in, start)`` → ``min(out, end)`` — so multi-day ranges sum
        exactly and no shift is ever counted twice. ``open`` means no
        closing punch exists at all (forward query), never an inference
        from the window: a closed historical shift is never "still in".
        An unpaired trailing ``in`` accrues up to query time but never
        past the end of the reported day. A shift opened on an earlier day
        and still open is seeded from its last pre-window punch, so it
        appears on every later day until it closes.
        """
        now = now or datetime.now(UTC)
        start, end = await AttendanceService._day_bounds_utc(db, clinic_id, day)
        cap = min(now, end)
        stmt = (
            select(AttendanceEvent, User.first_name, User.last_name)
            .join(User, User.id == AttendanceEvent.user_id)
            .where(
                AttendanceEvent.clinic_id == clinic_id,
                AttendanceEvent.at >= start,
                AttendanceEvent.at < end,
            )
            .order_by(AttendanceEvent.user_id, AttendanceEvent.at)
        )
        rows = (await db.execute(stmt)).all()
        # Seed each member seen in the window; then carry a pre-window
        # trailing `in` (lookback bounded — a shift open longer than that
        # without any punch is outside this module's model). Members with
        # no in-window events whose last pre-window punch is an unclosed
        # `in` are seeded too, so a shift opened yesterday and still open
        # appears on today's report instead of vanishing.
        by_user: dict[UUID, dict] = {}
        for event, first, last in rows:
            by_user.setdefault(
                event.user_id, {"name": f"{first} {last}", "seconds": 0, "open_since": None}
            )
        pre_stmt = (
            select(AttendanceEvent, User.first_name, User.last_name)
            .join(User, User.id == AttendanceEvent.user_id)
            .where(
                AttendanceEvent.clinic_id == clinic_id,
                AttendanceEvent.at >= start - timedelta(days=7),
                AttendanceEvent.at < start,
            )
            .order_by(AttendanceEvent.user_id, desc(AttendanceEvent.at))
        )
        seen: set[UUID] = set()
        for pre, first, last in (await db.execute(pre_stmt)).all():
            if pre.user_id in seen:
                continue
            seen.add(pre.user_id)
            if pre.kind == "in":
                slot = by_user.setdefault(
                    pre.user_id,
                    {"name": f"{first} {last}", "seconds": 0, "open_since": None},
                )
                slot["open_since"] = pre.at
        for event, first, last in rows:
            slot = by_user[event.user_id]
            if event.kind == "in":
                slot["open_since"] = event.at
            elif slot["open_since"] is not None:
                slot["seconds"] += max(
                    0,
                    int((min(event.at, end) - max(slot["open_since"], start)).total_seconds()),
                )
                slot["open_since"] = None
        out: list[dict] = []
        for uid, slot in sorted(by_user.items(), key=lambda kv: kv[1]["name"]):
            is_open = False
            extra = 0
            if slot["open_since"] is not None:
                # Forward query: does any closing punch exist at all?
                later = (
                    await db.execute(
                        select(AttendanceEvent.at)
                        .where(
                            AttendanceEvent.clinic_id == clinic_id,
                            AttendanceEvent.user_id == uid,
                            AttendanceEvent.kind == "out",
                            AttendanceEvent.at > slot["open_since"],
                        )
                        .order_by(AttendanceEvent.at)
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if later is None:
                    is_open = True
                    if cap > max(slot["open_since"], start):
                        extra = int((cap - max(slot["open_since"], start)).total_seconds())
                else:
                    slot["seconds"] += max(
                        0,
                        int((min(later, end) - max(slot["open_since"], start)).total_seconds()),
                    )
            out.append(
                {
                    "user_id": uid,
                    "full_name": slot["name"],
                    "seconds": slot["seconds"] + extra,
                    "open": is_open,
                }
            )
        return out
