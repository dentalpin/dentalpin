"""KanbanDayService — per-day operational snapshot for the kanban board.

Produces the payload consumed by the professionals strip:

    {
      date, clinic_id,
      professionals: [{
        id, first_name, last_name,
        state: "free" | "in_treatment" | "on_break" | "off",
        current_appointment_id?: UUID,
        current_cabinet_id?: UUID
      }]
    }

Module-isolation rules: ``schedules`` is optional at runtime. If it's
installed we consult its availability service to distinguish ``on_break``
and ``off`` from plain ``free`` / ``in_treatment``. If it isn't, every
professional outside of an active treatment is simply ``free`` — the
module keeps working without the extra nuance.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import ClinicMembership, User

from .models import Appointment


async def _fetch_professionals(db: AsyncSession, clinic_id: UUID) -> list[tuple[UUID, str, str]]:
    """Return (id, first_name, last_name) for every active dentist /
    hygienist in the clinic."""
    result = await db.execute(
        select(User.id, User.first_name, User.last_name)
        .join(ClinicMembership, ClinicMembership.user_id == User.id)
        .where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.is_professional.is_(True),
            User.is_active.is_(True),
        )
    )
    return [(r.id, r.first_name, r.last_name) for r in result.all()]


async def _fetch_active_treatments(
    db: AsyncSession, clinic_id: UUID, day_start: datetime, day_end: datetime
) -> dict[UUID, tuple[UUID, UUID | None]]:
    """Map ``professional_id -> (appointment_id, cabinet_id)`` for the
    single appointment each professional is currently treating today."""
    result = await db.execute(
        select(
            Appointment.professional_id,
            Appointment.id,
            Appointment.cabinet_id,
        ).where(
            Appointment.clinic_id == clinic_id,
            Appointment.status == "in_treatment",
            Appointment.start_time >= day_start,
            Appointment.start_time <= day_end,
        )
    )
    out: dict[UUID, tuple[UUID, UUID | None]] = {}
    for prof_id, apt_id, cab_id in result.all():
        # A professional should only have one in-flight appointment at a
        # time — if multiple somehow exist, the first one wins; downstream
        # analytics have the full picture.
        out.setdefault(prof_id, (apt_id, cab_id))
    return out


async def _fetch_schedule_states(
    db: AsyncSession,
    clinic_id: UUID,
    professional_ids: list[UUID],
    target: datetime,
) -> dict[UUID, str]:
    """Return ``professional_id -> state`` where ``state`` is ``"on_break"``
    (the professional has working hours today but this minute is a closed
    block inside them) or ``"off"`` (outside working hours entirely).

    Uses the ``schedules`` module when installed; otherwise returns an
    empty dict so every professional defaults to ``free`` / ``in_treatment``.
    """
    try:
        from app.modules.schedules.services.availability import AvailabilityService
    except Exception:
        return {}

    target_day = target.date()
    out: dict[UUID, str] = {}
    for pid in professional_ids:
        try:
            _, ranges = await AvailabilityService.resolve(
                db, clinic_id, target_day, target_day, professional_id=pid
            )
        except Exception:
            continue

        # Find the range containing ``target``. If inside an "open" range
        # → keep default (free/in_treatment); if "closed" (break inside
        # working hours) → on_break; otherwise off.
        state = "off"
        any_open_today = any(r.state == "open" for r in ranges)
        for r in ranges:
            if r.start <= target <= r.end:
                if r.state == "open":
                    state = "free"
                elif r.state == "closed" and any_open_today:
                    state = "on_break"
                else:
                    state = "off"
                break
        if state != "free":
            out[pid] = state
    return out


class KanbanDayService:
    @staticmethod
    async def snapshot(
        db: AsyncSession,
        clinic_id: UUID,
        target_date: date,
    ) -> dict:
        now = datetime.now(UTC)
        # Day window in UTC (start/end).
        day_start = datetime(
            target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=UTC
        )
        day_end = datetime(
            target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=UTC
        )

        pros = await _fetch_professionals(db, clinic_id)
        active = await _fetch_active_treatments(db, clinic_id, day_start, day_end)
        schedule_states = await _fetch_schedule_states(db, clinic_id, [p[0] for p in pros], now)

        professionals_payload = []
        for pid, first_name, last_name in pros:
            if pid in active:
                apt_id, cab_id = active[pid]
                professionals_payload.append(
                    {
                        "id": str(pid),
                        "first_name": first_name,
                        "last_name": last_name,
                        "state": "in_treatment",
                        "current_appointment_id": str(apt_id),
                        "current_cabinet_id": str(cab_id) if cab_id else None,
                    }
                )
                continue
            state = schedule_states.get(pid, "free")
            professionals_payload.append(
                {
                    "id": str(pid),
                    "first_name": first_name,
                    "last_name": last_name,
                    "state": state,
                    "current_appointment_id": None,
                    "current_cabinet_id": None,
                }
            )

        return {
            "date": target_date,
            "clinic_id": str(clinic_id),
            "professionals": professionals_payload,
        }
