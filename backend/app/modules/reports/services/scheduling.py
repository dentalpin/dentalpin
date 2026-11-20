"""Scheduling report service."""

from datetime import date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import User
from app.core.utils.dates import clinic_day_range, clinic_zone_for
from app.modules.agenda.models import Appointment


async def _clinic_days(
    db: AsyncSession, clinic_id: UUID, date_from: date, date_to: date
) -> tuple[datetime, datetime]:
    """``[start, end)`` of the report period on the clinic's clock (#932).

    ``start_time`` is stored in UTC; ``date(start_time)`` is the UTC date.
    """
    return clinic_day_range(await clinic_zone_for(db, clinic_id), date_from, date_to)


class SchedulingReportService:
    """Service for scheduling/appointment reports."""

    @staticmethod
    async def get_summary(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> dict[str, Any]:
        """Get scheduling summary for a period.

        Returns:
            - total_appointments: Total appointments in period
            - completed: Completed appointments
            - cancelled: Cancelled appointments
            - no_show: No-show appointments
            - scheduled: Still scheduled (future)
            - completion_rate: completed / (completed + cancelled + no_show)
            - cancellation_rate: cancelled / total decided
            - no_show_rate: no_show / total decided
        """
        day_start, day_end = await _clinic_days(db, clinic_id, date_from, date_to)
        result = await db.execute(
            select(
                func.count(Appointment.id).label("total"),
                func.coalesce(
                    func.sum(case((Appointment.status == "completed", 1), else_=0)), 0
                ).label("completed"),
                func.coalesce(
                    func.sum(case((Appointment.status == "cancelled", 1), else_=0)), 0
                ).label("cancelled"),
                func.coalesce(
                    func.sum(case((Appointment.status == "no_show", 1), else_=0)), 0
                ).label("no_show"),
                func.coalesce(
                    func.sum(case((Appointment.status == "scheduled", 1), else_=0)), 0
                ).label("scheduled"),
                func.coalesce(
                    func.sum(case((Appointment.status == "confirmed", 1), else_=0)), 0
                ).label("confirmed"),
                func.coalesce(
                    func.sum(case((Appointment.status == "checked_in", 1), else_=0)), 0
                ).label("checked_in"),
                func.coalesce(
                    func.sum(case((Appointment.status == "in_treatment", 1), else_=0)), 0
                ).label("in_treatment"),
            ).where(
                Appointment.clinic_id == clinic_id,
                Appointment.start_time >= day_start,
                Appointment.start_time < day_end,
            )
        )
        totals = result.one()

        # Calculate rates
        total_decided = totals.completed + totals.cancelled + totals.no_show
        completion_rate = (totals.completed / total_decided * 100) if total_decided > 0 else 0.0
        cancellation_rate = (totals.cancelled / total_decided * 100) if total_decided > 0 else 0.0
        no_show_rate = (totals.no_show / total_decided * 100) if total_decided > 0 else 0.0

        return {
            "period_start": date_from,
            "period_end": date_to,
            "total_appointments": totals.total,
            "completed": totals.completed,
            "cancelled": totals.cancelled,
            "no_show": totals.no_show,
            "scheduled": totals.scheduled,
            "confirmed": totals.confirmed,
            "checked_in": totals.checked_in,
            "in_treatment": totals.in_treatment,
            "completion_rate": round(completion_rate, 1),
            "cancellation_rate": round(cancellation_rate, 1),
            "no_show_rate": round(no_show_rate, 1),
        }

    @staticmethod
    async def get_first_visits(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> dict[str, Any]:
        """Get first visits (new patients) statistics.

        A first visit is the first appointment for a patient in the clinic.
        """
        day_start, day_end = await _clinic_days(db, clinic_id, date_from, date_to)
        # Get patients whose first appointment falls within the period
        # Subquery to find each patient's first appointment date
        first_apt_subq = (
            select(
                Appointment.patient_id,
                func.min(Appointment.start_time).label("first_appointment"),
            )
            .where(
                Appointment.clinic_id == clinic_id,
                Appointment.status.notin_(["cancelled"]),
            )
            .group_by(Appointment.patient_id)
            .subquery()
        )

        # Count patients whose first appointment is in the period
        result = await db.execute(
            select(func.count(first_apt_subq.c.patient_id)).where(
                first_apt_subq.c.first_appointment >= day_start,
                first_apt_subq.c.first_appointment < day_end,
            )
        )
        new_patients = result.scalar() or 0

        # Total appointments in period (for context)
        result = await db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.clinic_id == clinic_id,
                Appointment.start_time >= day_start,
                Appointment.start_time < day_end,
                Appointment.status.notin_(["cancelled"]),
            )
        )
        total_appointments = result.scalar() or 0

        return {
            "period_start": date_from,
            "period_end": date_to,
            "new_patients": new_patients,
            "total_appointments": total_appointments,
            "first_visit_rate": round(
                (new_patients / total_appointments * 100) if total_appointments > 0 else 0,
                1,
            ),
        }

    @staticmethod
    async def get_hours_by_professional(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Get hours worked by professional."""
        day_start, day_end = await _clinic_days(db, clinic_id, date_from, date_to)
        # Calculate duration in minutes for each appointment
        result = await db.execute(
            select(
                Appointment.professional_id,
                func.count(Appointment.id).label("appointment_count"),
                func.coalesce(
                    func.sum(case((Appointment.status == "completed", 1), else_=0)), 0
                ).label("completed_count"),
                func.coalesce(
                    func.sum(case((Appointment.status == "cancelled", 1), else_=0)), 0
                ).label("cancelled_count"),
                func.coalesce(
                    func.sum(case((Appointment.status == "no_show", 1), else_=0)), 0
                ).label("no_show_count"),
                # Sum duration in minutes (completed appointments only)
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Appointment.status == "completed",
                                extract("epoch", Appointment.end_time - Appointment.start_time)
                                / 60,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_minutes"),
            )
            .where(
                Appointment.clinic_id == clinic_id,
                Appointment.start_time >= day_start,
                Appointment.start_time < day_end,
                Appointment.professional_id.isnot(None),
            )
            .group_by(Appointment.professional_id)
        )
        rows = result.all()

        # Get professional names
        prof_ids = [r.professional_id for r in rows if r.professional_id]
        prof_names: dict[UUID, str] = {}
        if prof_ids:
            result = await db.execute(select(User).where(User.id.in_(prof_ids)))
            for user in result.scalars():
                prof_names[user.id] = f"{user.first_name} {user.last_name}"

        return [
            {
                "professional_id": row.professional_id,
                "professional_name": prof_names.get(row.professional_id, "-"),
                "appointment_count": row.appointment_count,
                "completed_count": row.completed_count,
                "cancelled_count": row.cancelled_count,
                "no_show_count": row.no_show_count,
                "total_minutes": int(row.total_minutes),
                "total_hours": round(row.total_minutes / 60, 1),
            }
            for row in rows
        ]

    @staticmethod
    async def get_cabinet_utilization(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Get cabinet/chair utilization."""
        day_start, day_end = await _clinic_days(db, clinic_id, date_from, date_to)
        result = await db.execute(
            select(
                Appointment.cabinet,
                func.count(Appointment.id).label("appointment_count"),
                func.coalesce(
                    func.sum(case((Appointment.status == "completed", 1), else_=0)), 0
                ).label("completed_count"),
                # Sum duration in minutes
                func.coalesce(
                    func.sum(extract("epoch", Appointment.end_time - Appointment.start_time) / 60),
                    0,
                ).label("total_minutes"),
            )
            .where(
                Appointment.clinic_id == clinic_id,
                Appointment.start_time >= day_start,
                Appointment.start_time < day_end,
                Appointment.cabinet.isnot(None),
            )
            .group_by(Appointment.cabinet)
            .order_by(Appointment.cabinet)
        )

        return [
            {
                "cabinet": row.cabinet,
                "appointment_count": row.appointment_count,
                "completed_count": row.completed_count,
                "total_minutes": int(row.total_minutes),
                "total_hours": round(row.total_minutes / 60, 1),
            }
            for row in result.all()
        ]

    @staticmethod
    async def get_by_day_of_week(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Get appointment distribution by day of week (the clinic's weekdays)."""
        zone = (await clinic_zone_for(db, clinic_id)).key
        day_start, day_end = clinic_day_range(ZoneInfo(zone), date_from, date_to)
        result = await db.execute(
            select(
                extract("dow", func.timezone(zone, Appointment.start_time)).label("day_of_week"),
                func.count(Appointment.id).label("appointment_count"),
                func.coalesce(
                    func.sum(case((Appointment.status == "completed", 1), else_=0)), 0
                ).label("completed_count"),
                func.coalesce(
                    func.sum(case((Appointment.status == "cancelled", 1), else_=0)), 0
                ).label("cancelled_count"),
                func.coalesce(
                    func.sum(case((Appointment.status == "no_show", 1), else_=0)), 0
                ).label("no_show_count"),
            )
            .where(
                Appointment.clinic_id == clinic_id,
                Appointment.start_time >= day_start,
                Appointment.start_time < day_end,
            )
            .group_by("day_of_week")
            .order_by("day_of_week")
        )

        day_names = {
            0: "sunday",
            1: "monday",
            2: "tuesday",
            3: "wednesday",
            4: "thursday",
            5: "friday",
            6: "saturday",
        }

        return [
            {
                "day_of_week": int(row.day_of_week),
                "day_name": day_names.get(int(row.day_of_week), "unknown"),
                "appointment_count": row.appointment_count,
                "completed_count": row.completed_count,
                "cancelled_count": row.cancelled_count,
                "no_show_count": row.no_show_count,
            }
            for row in result.all()
        ]
