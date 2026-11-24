"""Availability resolver — compose clinic + professional rules into time ranges.

Precedence (highest wins):
    1. professional override kind=unavailable    -> professional_off
    2. professional override kind=custom_hours   -> replaces professional weekly
    3. professional weekly (if provided)         -> trims open range
    4. clinic override kind=closed               -> clinic_closed
    5. clinic override kind=custom_hours         -> replaces clinic weekly
    6. clinic weekly                             -> base open range

Every shift's ``TIME`` is interpreted in the clinic's timezone on the
given local date; the resulting ranges are TZ-aware ``datetime`` in UTC
offset form so the frontend can render them verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    ClinicOverride,
    ClinicWeeklySchedule,
    ProfessionalOverride,
    ProfessionalWeeklySchedule,
)
from .clinic_hours import ClinicHoursService

RangeState = Literal["open", "clinic_closed", "professional_off"]


@dataclass(frozen=True)
class ResolvedRange:
    start: datetime
    end: datetime
    state: RangeState
    professional_id: UUID | None = None
    reason: str | None = None


class AvailabilityService:
    @staticmethod
    async def resolve(
        db: AsyncSession,
        clinic_id: UUID,
        start: date,
        end: date,
        professional_id: UUID | None = None,
    ) -> tuple[str, list[ResolvedRange]]:
        """Compute availability ranges for ``[start, end]`` (inclusive).

        Returns ``(timezone, ranges)`` where ``ranges`` is a merged list
        of open + closed + off ranges in chronological order.
        """
        tz_name = await ClinicHoursService.get_clinic_timezone(db, clinic_id)
        tz = ZoneInfo(tz_name)

        clinic_weekly = await _load_clinic_weekly(db, clinic_id)
        clinic_overrides = await _load_clinic_overrides(db, clinic_id, start, end)
        professional_weekly: ProfessionalWeeklySchedule | None = None
        professional_overrides: list[ProfessionalOverride] = []
        if professional_id is not None:
            professional_weekly = await _load_professional_weekly(db, clinic_id, professional_id)
            professional_overrides = await _load_professional_overrides(
                db, clinic_id, professional_id, start, end
            )

        all_ranges: list[ResolvedRange] = []
        day = start
        while day <= end:
            all_ranges.extend(
                _resolve_day(
                    day=day,
                    tz=tz,
                    clinic_weekly=clinic_weekly,
                    clinic_overrides=clinic_overrides,
                    professional_weekly=professional_weekly,
                    professional_overrides=professional_overrides,
                    professional_id=professional_id,
                )
            )
            if day == end:  # stepping past date.max would overflow (#1101)
                break
            day += timedelta(days=1)

        return tz_name, _merge_adjacent(all_ranges)


# --- Query helpers ----------------------------------------------------


async def _load_clinic_weekly(db: AsyncSession, clinic_id: UUID) -> ClinicWeeklySchedule | None:
    result = await db.execute(
        select(ClinicWeeklySchedule)
        .options(selectinload(ClinicWeeklySchedule.shifts))
        .where(ClinicWeeklySchedule.clinic_id == clinic_id)
    )
    return result.scalar_one_or_none()


async def _load_clinic_overrides(
    db: AsyncSession, clinic_id: UUID, start: date, end: date
) -> list[ClinicOverride]:
    result = await db.execute(
        select(ClinicOverride)
        .options(selectinload(ClinicOverride.shifts))
        .where(
            ClinicOverride.clinic_id == clinic_id,
            or_(
                and_(
                    ClinicOverride.start_date <= end,
                    ClinicOverride.end_date >= start,
                )
            ),
        )
    )
    return list(result.scalars().all())


async def _load_professional_weekly(
    db: AsyncSession, clinic_id: UUID, user_id: UUID
) -> ProfessionalWeeklySchedule | None:
    result = await db.execute(
        select(ProfessionalWeeklySchedule)
        .options(selectinload(ProfessionalWeeklySchedule.shifts))
        .where(
            ProfessionalWeeklySchedule.clinic_id == clinic_id,
            ProfessionalWeeklySchedule.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _load_professional_overrides(
    db: AsyncSession,
    clinic_id: UUID,
    user_id: UUID,
    start: date,
    end: date,
) -> list[ProfessionalOverride]:
    result = await db.execute(
        select(ProfessionalOverride)
        .options(selectinload(ProfessionalOverride.shifts))
        .where(
            ProfessionalOverride.clinic_id == clinic_id,
            ProfessionalOverride.user_id == user_id,
            ProfessionalOverride.start_date <= end,
            ProfessionalOverride.end_date >= start,
        )
    )
    return list(result.scalars().all())


# --- Day-level resolution --------------------------------------------


def _resolve_day(
    *,
    day: date,
    tz: ZoneInfo,
    clinic_weekly: ClinicWeeklySchedule | None,
    clinic_overrides: list[ClinicOverride],
    professional_weekly: ProfessionalWeeklySchedule | None,
    professional_overrides: list[ProfessionalOverride],
    professional_id: UUID | None,
) -> list[ResolvedRange]:
    weekday = day.weekday()  # Mon=0..Sun=6

    # 1. Pick clinic base shifts: override wins over weekly.
    clinic_shift_intervals: list[tuple[time, time]] = []
    clinic_closed_reason: str | None = None

    clinic_override = _pick_override(clinic_overrides, day)
    if clinic_override is not None:
        if clinic_override.kind == "closed":
            return [
                ResolvedRange(
                    start=_combine(day, time(0, 0), tz),
                    end=_combine(day, time(23, 59, 59), tz),
                    state="clinic_closed",
                    reason=clinic_override.reason,
                )
            ]
        clinic_shift_intervals = _sorted_shifts(
            [(s.start_time, s.end_time) for s in clinic_override.shifts]
        )
        clinic_closed_reason = clinic_override.reason
    elif clinic_weekly is not None:
        clinic_shift_intervals = _sorted_shifts(
            [(s.start_time, s.end_time) for s in clinic_weekly.shifts if s.weekday == weekday]
        )

    # No clinic hours → whole day is clinic_closed.
    if not clinic_shift_intervals:
        return [
            ResolvedRange(
                start=_combine(day, time(0, 0), tz),
                end=_combine(day, time(23, 59, 59), tz),
                state="clinic_closed",
                reason=clinic_closed_reason,
            )
        ]

    # 2. Intersect with professional hours if requested.
    if professional_id is None:
        return _intervals_to_ranges(day, tz, clinic_shift_intervals, "open", None)

    # Professional override trumps everything.
    professional_override = _pick_override(professional_overrides, day)
    if professional_override is not None:
        if professional_override.kind == "unavailable":
            return [
                ResolvedRange(
                    start=_combine(day, time(0, 0), tz),
                    end=_combine(day, time(23, 59, 59), tz),
                    state="professional_off",
                    professional_id=professional_id,
                    reason=professional_override.reason,
                )
            ]
        professional_intervals = _sorted_shifts(
            [(s.start_time, s.end_time) for s in professional_override.shifts]
        )
    elif professional_weekly is not None:
        professional_intervals = _sorted_shifts(
            [(s.start_time, s.end_time) for s in professional_weekly.shifts if s.weekday == weekday]
        )
    else:
        # No professional schedule defined — inherit clinic hours.
        professional_intervals = list(clinic_shift_intervals)

    if not professional_intervals:
        return [
            ResolvedRange(
                start=_combine(day, time(0, 0), tz),
                end=_combine(day, time(23, 59, 59), tz),
                state="professional_off",
                professional_id=professional_id,
                reason=(professional_override.reason if professional_override else None),
            )
        ]

    # Intersect clinic and professional intervals.
    intersected = _intersect(clinic_shift_intervals, professional_intervals)
    return _intervals_to_ranges(day, tz, intersected, "open", professional_id)


# --- Helpers ----------------------------------------------------------


def _pick_override(overrides: list, day: date):
    """Return the highest-priority override covering ``day``, or None.

    Highest priority = most recently created (tiebreak) since overrides
    with same date range should not overlap in practice; callers can
    surface conflicts separately.
    """
    candidates = [o for o in overrides if o.start_date <= day <= o.end_date]
    if not candidates:
        return None
    # Later start_date wins (more specific); then later created_at.
    candidates.sort(
        key=lambda o: (o.start_date, getattr(o, "created_at", None) or 0),
        reverse=True,
    )
    return candidates[0]


def _sorted_shifts(pairs: list[tuple[time, time]]) -> list[tuple[time, time]]:
    """Valid shifts by start, overlapping ones merged (#991).

    ``_intervals_to_ranges`` walks a cursor forward and needs disjoint
    intervals: a shift inside another moved it back and painted the rest of
    the day closed. Touching shifts (09–14, 14–18) stay separate ranges.
    """
    merged: list[tuple[time, time]] = []
    for start, end in sorted((p for p in pairs if p[0] < p[1]), key=lambda p: p[0]):
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _combine(day: date, t: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, t, tzinfo=tz)


def _intervals_to_ranges(
    day: date,
    tz: ZoneInfo,
    intervals: list[tuple[time, time]],
    state: RangeState,
    professional_id: UUID | None,
) -> list[ResolvedRange]:
    """Turn open intervals into a full-day sequence of ResolvedRanges.

    Produces closed ranges for gaps + the open intervals themselves.
    Gaps are emitted as the opposite of the requested ``state``:
    - open intervals + clinic_closed gaps, or
    - open intervals + professional_off gaps when a professional filter is in play.
    """
    gap_state: RangeState = "professional_off" if professional_id is not None else "clinic_closed"
    day_start = _combine(day, time(0, 0), tz)
    day_end = _combine(day, time(23, 59, 59), tz)

    ranges: list[ResolvedRange] = []
    cursor = day_start
    for start_t, end_t in intervals:
        start_dt = _combine(day, start_t, tz)
        end_dt = _combine(day, end_t, tz)
        if start_dt > cursor:
            ranges.append(
                ResolvedRange(
                    start=cursor,
                    end=start_dt,
                    state=gap_state,
                    professional_id=professional_id if gap_state != "clinic_closed" else None,
                )
            )
        ranges.append(
            ResolvedRange(
                start=start_dt,
                end=end_dt,
                state=state,
                professional_id=professional_id,
            )
        )
        cursor = end_dt

    if cursor < day_end:
        ranges.append(
            ResolvedRange(
                start=cursor,
                end=day_end,
                state=gap_state,
                professional_id=professional_id if gap_state != "clinic_closed" else None,
            )
        )
    return ranges


def _intersect(
    a: list[tuple[time, time]],
    b: list[tuple[time, time]],
) -> list[tuple[time, time]]:
    result: list[tuple[time, time]] = []
    for a_start, a_end in a:
        for b_start, b_end in b:
            start = max(a_start, b_start)
            end = min(a_end, b_end)
            if start < end:
                result.append((start, end))
    return _sorted_shifts(result)


def _merge_adjacent(ranges: list[ResolvedRange]) -> list[ResolvedRange]:
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda r: r.start)
    merged: list[ResolvedRange] = [sorted_ranges[0]]
    for r in sorted_ranges[1:]:
        last = merged[-1]
        if (
            last.end == r.start
            and last.state == r.state
            and last.professional_id == r.professional_id
            and last.reason == r.reason
        ):
            merged[-1] = ResolvedRange(
                start=last.start,
                end=r.end,
                state=last.state,
                professional_id=last.professional_id,
                reason=last.reason,
            )
        else:
            merged.append(r)
    return merged
