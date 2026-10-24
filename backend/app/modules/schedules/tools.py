"""Agent tools for the schedules module.

Thin wrappers over ``AvailabilityService`` — no business logic here.
Clinic-scoped; RBAC via the existing ``schedules.availability.read``.

``get_availability`` returns the clinic's open working windows for a day.
``find_free_slots`` goes further: it subtracts the professional's booked
appointments from those windows and returns discrete bookable slots
(this is allowed to read agenda because ``agenda`` is in
``manifest.depends``). See
``docs/technical/copilot-agentic-architecture.md`` §3.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from datetime import date as date_cls
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory
from app.core.utils.dates import clinic_today_for
from app.modules.agenda.service import AppointmentService

from .services.availability import AvailabilityService

_BLOCKING_STATUSES = {"scheduled", "confirmed", "checked_in", "in_treatment", "completed"}


class AvailabilityArgs(BaseModel):
    date: date_cls = Field(description="Día a consultar (YYYY-MM-DD).")
    professional_id: UUID | None = Field(
        default=None, description="Opcional: restringe a un profesional."
    )


class FreeSlotsArgs(BaseModel):
    professional_id: UUID
    slot_minutes: int = Field(
        default=30,
        ge=5,
        le=480,
        description="Duración mínima (min) que debe caber en la ventana libre para incluirla.",
    )
    days_ahead: int = Field(default=14, ge=1, le=60)
    part_of_day: Literal["morning", "afternoon", "any"] = "any"
    date_from: date_cls | None = Field(
        default=None, description="Primer día a considerar; por defecto hoy."
    )
    limit: int = Field(default=5, ge=1, le=20)


async def _get_availability(ctx: AgentContext, params: AvailabilityArgs) -> dict:
    tz_name, ranges = await AvailabilityService.resolve(
        ctx.db, ctx.clinic_id, params.date, params.date, params.professional_id
    )
    open_windows = [{"start": r.start, "end": r.end} for r in ranges if r.state == "open"]
    return {"date": params.date, "timezone": tz_name, "open_windows": open_windows}


def _subtract(start: datetime, end: datetime, busy: list[tuple[datetime, datetime]]) -> list[tuple]:
    """Return the sub-intervals of [start, end] not covered by ``busy``."""
    free = [(start, end)]
    for b0, b1 in busy:
        nxt: list[tuple[datetime, datetime]] = []
        for f0, f1 in free:
            if b1 <= f0 or b0 >= f1:  # disjoint
                nxt.append((f0, f1))
                continue
            if b0 > f0:
                nxt.append((f0, b0))
            if b1 < f1:
                nxt.append((b1, f1))
        free = nxt
    return free


def _overlaps_part(local_start: datetime, local_end: datetime, part: str) -> bool:
    """Whether a free window overlaps the requested part of the day (split at 14:00)."""
    if part == "morning":
        return local_start.hour < 14
    if part == "afternoon":
        noon = local_start.replace(hour=14, minute=0, second=0, microsecond=0)
        return local_end > noon
    return True


async def _find_free_slots(ctx: AgentContext, params: FreeSlotsArgs) -> dict:
    start_day = params.date_from or await clinic_today_for(ctx.db, ctx.clinic_id)
    end_day = start_day + timedelta(days=params.days_ahead)
    tz_name, ranges = await AvailabilityService.resolve(
        ctx.db, ctx.clinic_id, start_day, end_day, params.professional_id
    )
    open_ranges = sorted((r.start, r.end) for r in ranges if r.state == "open")
    if not open_ranges:
        return {"professional_id": params.professional_id, "free_windows": []}

    appts, _ = await AppointmentService.list_appointments(
        ctx.db,
        ctx.clinic_id,
        start_date=datetime.combine(start_day, time.min, tzinfo=UTC),
        end_date=datetime.combine(end_day, time.max, tzinfo=UTC),
        professional_id=params.professional_id,
        page_size=500,
    )
    busy = sorted(
        (a.start_time, a.end_time)
        for a in appts
        if a.status in _BLOCKING_STATUSES and a.start_time and a.end_time
    )

    tz = ZoneInfo(tz_name)
    min_dur = timedelta(minutes=params.slot_minutes)
    windows: list[tuple[datetime, datetime]] = []
    for win_start, win_end in open_ranges:
        for free_start, free_end in _subtract(win_start, win_end, busy):
            if free_end - free_start < min_dur:
                continue
            local_start = free_start.astimezone(tz)
            local_end = free_end.astimezone(tz)
            if not _overlaps_part(local_start, local_end, params.part_of_day):
                continue
            windows.append((local_start, local_end))

    windows.sort(key=lambda w: w[0])
    return {
        "professional_id": params.professional_id,
        "min_minutes": params.slot_minutes,
        # Contiguous free windows (real start/end), not fixed-size slots, so the
        # agent knows the true extent of each gap.
        "free_windows": [
            {"start": s, "end": e, "minutes": int((e - s).total_seconds() // 60)}
            for s, e in windows[: params.limit]
        ],
    }


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="get_availability",
            description=(
                "Ventanas de horario abierto de la clínica (o de un profesional) para un día. "
                "No descuenta citas reservadas; usa find_free_slots para huecos reales."
            ),
            parameters=AvailabilityArgs,
            handler=_get_availability,
            permissions=["schedules.availability.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="find_free_slots",
            description=(
                "Ventanas libres reales de un profesional (horario abierto menos citas ya "
                "reservadas), ordenadas de la más cercana a la más lejana. Devuelve "
                "`free_windows` con `start`, `end` y `minutes` (la duración real de cada hueco "
                "contiguo), no slots de tamaño fijo: úsalo para saber cuánto dura cada hueco y "
                "proponer una hora dentro. `slot_minutes` filtra ventanas que no llegan a esa "
                "duración mínima. Filtra también por franja (part_of_day) y días (days_ahead)."
            ),
            parameters=FreeSlotsArgs,
            handler=_find_free_slots,
            permissions=["schedules.availability.read", "agenda.appointments.read"],
            category=ToolCategory.READ,
        ),
    ]
