"""Appointment lifecycle analytics (issue #49).

Four SQL-only aggregators that read directly from ``appointments`` and
``appointment_status_events`` (both owned by the ``agenda`` module). The
``reports`` module already declares ``agenda`` as a dependency, so direct
imports respect the module isolation contract.

Every method returns a Pydantic-ready dict so the router can validate it
against the schemas in ``app.modules.reports.schemas`` without any
massaging in Python.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.dates import clinic_day_range, clinic_zone_for
from app.modules.agenda.models import Appointment, AppointmentStatusEvent

# A scan window of more than a year would make these queries expensive
# and the resulting numbers operationally useless (trend blur). Callers
# that need historical drilldown can paginate by sub-periods.
MAX_RANGE_DAYS = 365


def _validate_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise ValueError("date_to must be on or after date_from")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise ValueError(f"date range exceeds {MAX_RANGE_DAYS} days")


async def _filtered_appointments(
    db: AsyncSession,
    clinic_id: UUID,
    date_from: date,
    date_to: date,
    cabinet_id: UUID | None,
    professional_id: UUID | None,
):
    """Build the common Appointment filter used by every analytics method.

    ``start_time`` is stored in UTC, so the period is cut on the clinic's
    days (``date(start_time)`` was the UTC date, #933).
    """
    day_start, day_end = clinic_day_range(await clinic_zone_for(db, clinic_id), date_from, date_to)
    conditions = [
        Appointment.clinic_id == clinic_id,
        Appointment.start_time >= day_start,
        Appointment.start_time < day_end,
    ]
    if cabinet_id is not None:
        conditions.append(Appointment.cabinet_id == cabinet_id)
    if professional_id is not None:
        conditions.append(Appointment.professional_id == professional_id)
    return conditions


class AppointmentLifecycleService:
    """Analytics on status transitions: waiting, punctuality, duration,
    funnel.

    All math happens in SQL; we never stream full rows back to Python.
    """

    # -------------------------------------------------------------------
    # Waiting time: event(to=in_treatment).changed_at
    #             - event(to=checked_in).changed_at
    # -------------------------------------------------------------------
    @staticmethod
    async def waiting_times(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
        cabinet_id: UUID | None = None,
        professional_id: UUID | None = None,
    ) -> dict:
        _validate_range(date_from, date_to)

        checked_in = (
            select(
                AppointmentStatusEvent.appointment_id.label("apt_id"),
                func.min(AppointmentStatusEvent.changed_at).label("at"),
            )
            .where(
                AppointmentStatusEvent.clinic_id == clinic_id,
                AppointmentStatusEvent.to_status == "checked_in",
            )
            .group_by(AppointmentStatusEvent.appointment_id)
            .subquery()
        )
        in_treatment = (
            select(
                AppointmentStatusEvent.appointment_id.label("apt_id"),
                func.min(AppointmentStatusEvent.changed_at).label("at"),
            )
            .where(
                AppointmentStatusEvent.clinic_id == clinic_id,
                AppointmentStatusEvent.to_status == "in_treatment",
            )
            .group_by(AppointmentStatusEvent.appointment_id)
            .subquery()
        )

        wait_minutes = (func.extract("epoch", in_treatment.c.at - checked_in.c.at) / 60.0).label(
            "wait_minutes"
        )

        conditions = await _filtered_appointments(
            db, clinic_id, date_from, date_to, cabinet_id, professional_id
        )

        base = (
            select(wait_minutes)
            .select_from(Appointment)
            .join(checked_in, checked_in.c.apt_id == Appointment.id)
            .join(in_treatment, in_treatment.c.apt_id == Appointment.id)
            .where(and_(*conditions))
        ).subquery()

        agg = await db.execute(
            select(
                func.count().label("n"),
                func.avg(base.c.wait_minutes).label("avg"),
                func.percentile_cont(0.5).within_group(base.c.wait_minutes.asc()).label("median"),
                func.percentile_cont(0.9).within_group(base.c.wait_minutes.asc()).label("p90"),
            )
        )
        row = agg.one()

        # Distribution — CASE buckets so we stay in SQL.
        bucket_expr = case(
            (base.c.wait_minutes < 5, "0-5"),
            (base.c.wait_minutes < 10, "5-10"),
            (base.c.wait_minutes < 20, "10-20"),
            else_="20+",
        ).label("bucket")

        dist_rows = (
            await db.execute(select(bucket_expr, func.count().label("count")).group_by(bucket_expr))
        ).all()
        # Fixed order regardless of buckets that had zero samples.
        order = ["0-5", "5-10", "10-20", "20+"]
        counts = {b: 0 for b in order}
        for bucket, count in dist_rows:
            counts[bucket] = int(count)

        return {
            "period_start": date_from,
            "period_end": date_to,
            "sample_size": int(row.n or 0),
            "avg_minutes": float(row.avg) if row.avg is not None else None,
            "median_minutes": float(row.median) if row.median is not None else None,
            "p90_minutes": float(row.p90) if row.p90 is not None else None,
            "distribution": [{"label": b, "count": counts[b]} for b in order],
        }

    # -------------------------------------------------------------------
    # Punctuality: delta(check_in - scheduled start)
    # -------------------------------------------------------------------
    @staticmethod
    async def punctuality(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
        cabinet_id: UUID | None = None,
        professional_id: UUID | None = None,
    ) -> dict:
        _validate_range(date_from, date_to)

        checked_in = (
            select(
                AppointmentStatusEvent.appointment_id.label("apt_id"),
                func.min(AppointmentStatusEvent.changed_at).label("at"),
            )
            .where(
                AppointmentStatusEvent.clinic_id == clinic_id,
                AppointmentStatusEvent.to_status == "checked_in",
            )
            .group_by(AppointmentStatusEvent.appointment_id)
            .subquery()
        )

        delta_minutes = (
            func.extract("epoch", checked_in.c.at - Appointment.start_time) / 60.0
        ).label("delta_minutes")

        conditions = await _filtered_appointments(
            db, clinic_id, date_from, date_to, cabinet_id, professional_id
        )

        base = (
            select(delta_minutes)
            .select_from(Appointment)
            .join(checked_in, checked_in.c.apt_id == Appointment.id)
            .where(and_(*conditions))
        ).subquery()

        agg = await db.execute(
            select(
                func.count().label("n"),
                func.avg(base.c.delta_minutes).label("avg"),
                func.percentile_cont(0.5).within_group(base.c.delta_minutes.asc()).label("median"),
                func.coalesce(
                    func.sum(
                        case(
                            (func.abs(base.c.delta_minutes) <= 5, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("on_time"),
            )
        )
        row = agg.one()
        n = int(row.n or 0)
        on_time_pct = (float(row.on_time) / n * 100) if n > 0 else None

        bucket_expr = case(
            (base.c.delta_minutes < -5, "early"),
            (base.c.delta_minutes <= 5, "on_time"),
            (base.c.delta_minutes <= 15, "late_short"),
            else_="late_long",
        ).label("bucket")

        dist_rows = (
            await db.execute(select(bucket_expr, func.count().label("count")).group_by(bucket_expr))
        ).all()
        order = ["early", "on_time", "late_short", "late_long"]
        counts = {b: 0 for b in order}
        for bucket, count in dist_rows:
            counts[bucket] = int(count)

        return {
            "period_start": date_from,
            "period_end": date_to,
            "sample_size": n,
            "avg_delta_minutes": float(row.avg) if row.avg is not None else None,
            "median_delta_minutes": (float(row.median) if row.median is not None else None),
            "on_time_pct": round(on_time_pct, 1) if on_time_pct is not None else None,
            "distribution": [{"label": b, "count": counts[b]} for b in order],
        }

    # -------------------------------------------------------------------
    # Duration variance: planned (end - start) vs actual (completed - in_treatment)
    # -------------------------------------------------------------------
    @staticmethod
    async def duration_variance(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
        cabinet_id: UUID | None = None,
        professional_id: UUID | None = None,
    ) -> dict:
        _validate_range(date_from, date_to)

        in_treatment = (
            select(
                AppointmentStatusEvent.appointment_id.label("apt_id"),
                func.min(AppointmentStatusEvent.changed_at).label("at"),
            )
            .where(
                AppointmentStatusEvent.clinic_id == clinic_id,
                AppointmentStatusEvent.to_status == "in_treatment",
            )
            .group_by(AppointmentStatusEvent.appointment_id)
            .subquery()
        )
        completed = (
            select(
                AppointmentStatusEvent.appointment_id.label("apt_id"),
                func.max(AppointmentStatusEvent.changed_at).label("at"),
            )
            .where(
                AppointmentStatusEvent.clinic_id == clinic_id,
                AppointmentStatusEvent.to_status == "completed",
            )
            .group_by(AppointmentStatusEvent.appointment_id)
            .subquery()
        )

        planned = func.extract("epoch", Appointment.end_time - Appointment.start_time) / 60.0
        actual = func.extract("epoch", completed.c.at - in_treatment.c.at) / 60.0
        delta = (actual - planned).label("delta_minutes")
        # Guard against zero-length planned durations (shouldn't happen
        # in production data but still sanest to short-circuit).
        overrun_pct = case(
            (planned > 0, (actual - planned) / planned * 100.0),
            else_=None,
        ).label("overrun_pct")

        conditions = await _filtered_appointments(
            db, clinic_id, date_from, date_to, cabinet_id, professional_id
        )

        base = (
            select(delta, overrun_pct)
            .select_from(Appointment)
            .join(in_treatment, in_treatment.c.apt_id == Appointment.id)
            .join(completed, completed.c.apt_id == Appointment.id)
            .where(and_(*conditions))
        ).subquery()

        agg = await db.execute(
            select(
                func.count().label("n"),
                func.avg(base.c.delta_minutes).label("avg_delta"),
                func.avg(base.c.overrun_pct).label("avg_overrun"),
                func.coalesce(
                    func.sum(case((base.c.delta_minutes > 0, 1), else_=0)),
                    0,
                ).label("overrun_count"),
                func.coalesce(
                    func.sum(case((base.c.delta_minutes <= 0, 1), else_=0)),
                    0,
                ).label("under_count"),
            )
        )
        row = agg.one()

        return {
            "period_start": date_from,
            "period_end": date_to,
            "sample_size": int(row.n or 0),
            "avg_overrun_pct": (float(row.avg_overrun) if row.avg_overrun is not None else None),
            "avg_delta_minutes": (float(row.avg_delta) if row.avg_delta is not None else None),
            "overrun_count": int(row.overrun_count or 0),
            "under_count": int(row.under_count or 0),
        }

    # -------------------------------------------------------------------
    # Funnel: counts by current status + rates
    # -------------------------------------------------------------------
    @staticmethod
    async def funnel(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
        cabinet_id: UUID | None = None,
        professional_id: UUID | None = None,
    ) -> dict:
        _validate_range(date_from, date_to)

        conditions = await _filtered_appointments(
            db, clinic_id, date_from, date_to, cabinet_id, professional_id
        )

        result = await db.execute(
            select(Appointment.status, func.count().label("count"))
            .where(and_(*conditions))
            .group_by(Appointment.status)
        )
        counts: dict[str, int] = {
            "scheduled": 0,
            "confirmed": 0,
            "checked_in": 0,
            "in_treatment": 0,
            "completed": 0,
            "cancelled": 0,
            "no_show": 0,
        }
        for status, count in result.all():
            counts[status] = int(count)

        total = sum(counts.values())
        decided = counts["completed"] + counts["cancelled"] + counts["no_show"]
        return {
            "period_start": date_from,
            "period_end": date_to,
            "total": total,
            "counts_by_status": counts,
            "completion_rate": (
                round(counts["completed"] / decided * 100, 1) if decided > 0 else None
            ),
            "no_show_rate": (round(counts["no_show"] / decided * 100, 1) if decided > 0 else None),
            "cancellation_rate": (
                round(counts["cancelled"] / decided * 100, 1) if decided > 0 else None
            ),
        }
