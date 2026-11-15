"""Occupancy + utilization analytics.

Reads from the agenda module (``appointments``, ``cabinets``) — this is
why ``schedules.depends = ["agenda"]``. The analytics endpoints are the
only place the schedules module touches agenda code, and the direction
is deliberately one-way: agenda never imports from schedules.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import ClinicMembership, User
from app.modules.agenda.models import Appointment, Cabinet

from .availability import AvailabilityService
from .professional_hours import ProfessionalHoursService


class AnalyticsService:
    @staticmethod
    async def assistant_workload(
        db: AsyncSession,
        clinic_id: UUID,
        start: date,
        end: date,
        assistant_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Return assistant capacity, booked time and shift conflicts.

        Overlapping active appointments are reported separately from
        appointments that fall outside the assistant's configured shifts.
        Cancelled and no-show appointments do not consume capacity.
        """
        if end < start:
            raise ValueError("end must be on or after start")
        members = await ProfessionalHoursService.list_assistants(db, clinic_id)
        if assistant_id is not None:
            members = [m for m in members if m["user_id"] == assistant_id]

        tz_name, _ = await AvailabilityService.resolve(db, clinic_id, start, end)
        tz = ZoneInfo(tz_name)
        lo, hi = _bound(start, "lo", tz), _bound(end, "hi", tz)
        rows: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for member in members:
            user_id = member["user_id"]
            _, ranges = await AvailabilityService.resolve(db, clinic_id, start, end, user_id)
            open_ranges = [r for r in ranges if r.state == "open"]
            available_minutes = sum(
                int((r.end - r.start).total_seconds() / 60) for r in open_ranges
            )
            appointments = (
                (
                    await db.execute(
                        select(Appointment)
                        .where(
                            Appointment.clinic_id == clinic_id,
                            Appointment.assistant_id == user_id,
                            Appointment.status.notin_(["cancelled", "no_show"]),
                            Appointment.start_time < hi,
                            Appointment.end_time > lo,
                        )
                        .order_by(Appointment.start_time, Appointment.end_time)
                    )
                )
                .scalars()
                .all()
            )
            booked_minutes = sum(
                max(0, int((a.end_time - a.start_time).total_seconds() / 60)) for a in appointments
            )
            active = [
                a
                for a in appointments
                if a.status in ("scheduled", "confirmed", "checked_in", "in_treatment")
            ]
            for index, appointment in enumerate(active):
                if not any(
                    interval.start <= appointment.start_time
                    and interval.end >= appointment.end_time
                    for interval in open_ranges
                ):
                    conflicts.append(
                        {
                            "assistant_id": user_id,
                            "assistant_name": f"{member['first_name']} {member['last_name']}".strip(),
                            "kind": "outside_shift",
                            "appointment_id": appointment.id,
                            "other_appointment_id": None,
                            "start_at": appointment.start_time,
                            "end_at": appointment.end_time,
                        }
                    )
                for other in active[index + 1 :]:
                    if other.start_time >= appointment.end_time:
                        break
                    if (
                        other.start_time < appointment.end_time
                        and other.end_time > appointment.start_time
                    ):
                        conflicts.append(
                            {
                                "assistant_id": user_id,
                                "assistant_name": f"{member['first_name']} {member['last_name']}".strip(),
                                "kind": "overlap",
                                "appointment_id": appointment.id,
                                "other_appointment_id": other.id,
                                "start_at": max(appointment.start_time, other.start_time),
                                "end_at": min(appointment.end_time, other.end_time),
                            }
                        )

            rows.append(
                {
                    "assistant_id": user_id,
                    "assistant_name": f"{member['first_name']} {member['last_name']}".strip(),
                    "appointment_count": len(appointments),
                    "booked_minutes": booked_minutes,
                    "available_minutes": available_minutes,
                    "utilization_rate": booked_minutes / available_minutes
                    if available_minutes
                    else 0.0,
                    "conflict_count": sum(c["assistant_id"] == user_id for c in conflicts),
                }
            )
        return {"start": start, "end": end, "rows": rows, "conflicts": conflicts}

    @staticmethod
    async def occupancy(
        db: AsyncSession,
        clinic_id: UUID,
        start: date,
        end: date,
        cabinet_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        tz_name, ranges = await AvailabilityService.resolve(db, clinic_id, start, end)
        tz = ZoneInfo(tz_name)
        available_minutes = sum(
            int((r.end - r.start).total_seconds() / 60) for r in ranges if r.state == "open"
        )

        query = (
            select(
                Cabinet.id,
                Cabinet.name,
                func.coalesce(
                    func.sum(
                        func.extract("epoch", Appointment.end_time - Appointment.start_time) / 60
                    ),
                    0,
                ).label("booked_minutes"),
            )
            .select_from(Cabinet)
            .join(
                Appointment,
                (Appointment.cabinet_id == Cabinet.id)
                & (Appointment.status != "cancelled")
                & (Appointment.start_time >= _bound(start, "lo", tz))
                & (Appointment.start_time <= _bound(end, "hi", tz)),
                isouter=True,
            )
            .where(Cabinet.clinic_id == clinic_id)
            .group_by(Cabinet.id, Cabinet.name)
            .order_by(Cabinet.name)
        )
        if cabinet_id is not None:
            query = query.where(Cabinet.id == cabinet_id)

        result = await db.execute(query)
        rows: list[dict[str, Any]] = []
        for row in result.all():
            booked = int(row.booked_minutes or 0)
            rate = (booked / available_minutes) if available_minutes else 0.0
            rows.append(
                {
                    "cabinet_id": row.id,
                    "cabinet_name": row.name,
                    "booked_minutes": booked,
                    "available_minutes": available_minutes,
                    "occupancy_rate": min(rate, 1.0),
                }
            )
        return rows

    @staticmethod
    async def utilization(
        db: AsyncSession,
        clinic_id: UUID,
        start: date,
        end: date,
        professional_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        membership_filter = (
            select(ClinicMembership.user_id)
            .where(
                ClinicMembership.clinic_id == clinic_id,
                ClinicMembership.is_professional.is_(True),
            )
            .subquery()
        )
        users_query = (
            select(User.id, User.first_name, User.last_name)
            .where(User.id.in_(select(membership_filter.c.user_id)))
            .order_by(User.last_name, User.first_name)
        )
        if professional_id is not None:
            users_query = users_query.where(User.id == professional_id)
        users = (await db.execute(users_query)).all()
        if not users:
            return []

        tz_name, _ = await AvailabilityService.resolve(db, clinic_id, start, end)
        tz = ZoneInfo(tz_name)
        result_rows: list[dict[str, Any]] = []
        for user in users:
            _, ranges = await AvailabilityService.resolve(db, clinic_id, start, end, user.id)
            working_minutes = sum(
                int((r.end - r.start).total_seconds() / 60) for r in ranges if r.state == "open"
            )

            booked = (
                await db.execute(
                    select(
                        func.coalesce(
                            func.sum(
                                func.extract(
                                    "epoch",
                                    Appointment.end_time - Appointment.start_time,
                                )
                                / 60
                            ),
                            0,
                        )
                    ).where(
                        Appointment.clinic_id == clinic_id,
                        Appointment.professional_id == user.id,
                        Appointment.status != "cancelled",
                        Appointment.start_time >= _bound(start, "lo", tz),
                        Appointment.start_time <= _bound(end, "hi", tz),
                    )
                )
            ).scalar() or 0
            booked = int(booked)
            rate = (booked / working_minutes) if working_minutes else 0.0
            result_rows.append(
                {
                    "professional_id": user.id,
                    "professional_name": f"{user.first_name} {user.last_name}".strip(),
                    "booked_minutes": booked,
                    "working_minutes": working_minutes,
                    "utilization_rate": min(rate, 1.0),
                }
            )
        return result_rows

    @staticmethod
    async def peak_hours(
        db: AsyncSession, clinic_id: UUID, start: date, end: date
    ) -> list[dict[str, int]]:
        tz_name = await _tz_name(db, clinic_id)
        tz = ZoneInfo(tz_name)

        query = (
            select(
                func.extract("hour", Appointment.start_time.op("AT TIME ZONE")(tz_name)).label(
                    "hour"
                ),
                func.count().label("count"),
            )
            .where(
                Appointment.clinic_id == clinic_id,
                Appointment.status != "cancelled",
                Appointment.start_time >= _bound(start, "lo", tz),
                Appointment.start_time <= _bound(end, "hi", tz),
            )
            .group_by("hour")
            .order_by("hour")
        )
        result = await db.execute(query)
        return [
            {"hour": int(row.hour), "appointment_count": int(row.count)} for row in result.all()
        ]


async def _tz_name(db: AsyncSession, clinic_id: UUID) -> str:
    from .clinic_hours import ClinicHoursService

    return await ClinicHoursService.get_clinic_timezone(db, clinic_id)


def _bound(day: date, side: str, tz: ZoneInfo) -> datetime:
    if side == "lo":
        return datetime.combine(day, time(0, 0), tzinfo=tz)
    return datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=tz)
