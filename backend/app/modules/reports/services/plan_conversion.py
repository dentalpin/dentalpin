"""Treatment-plan conversion analytics, cohort-based on doctor confirmation."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.agenda.models import Appointment
from app.modules.treatment_plan.models import (
    AppointmentTreatment,
    PlannedTreatmentItem,
    TreatmentPlan,
)


class PlanConversionReportService:
    """Measures conversion from plans offered to booked and completed care.

    The cohort is plans confirmed during the selected clinic-local date
    window. A booking is any non-cancelled appointment linked to a plan item;
    completed care is a plan with at least one completed item. Cancelled and
    deleted plans are excluded; draft plans are not yet an offer to a patient.
    """

    @staticmethod
    async def get(db: AsyncSession, clinic_id, date_from: date, date_to: date) -> dict[str, Any]:
        if date_to < date_from:
            raise ValueError("date_to must be on or after date_from")

        timezone = await db.scalar(select(Clinic.timezone).where(Clinic.id == clinic_id))
        tz = ZoneInfo(timezone or "UTC")
        start_at = datetime.combine(date_from, time.min, tzinfo=tz)
        end_at = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz)

        item_count = (
            select(func.count(PlannedTreatmentItem.id))
            .where(
                PlannedTreatmentItem.treatment_plan_id == TreatmentPlan.id,
                PlannedTreatmentItem.clinic_id == clinic_id,
                PlannedTreatmentItem.status != "cancelled",
            )
            .correlate(TreatmentPlan)
            .scalar_subquery()
        )
        completed_count = (
            select(func.count(PlannedTreatmentItem.id))
            .where(
                PlannedTreatmentItem.treatment_plan_id == TreatmentPlan.id,
                PlannedTreatmentItem.clinic_id == clinic_id,
                PlannedTreatmentItem.status == "completed",
            )
            .correlate(TreatmentPlan)
            .scalar_subquery()
        )
        has_booking = (
            select(AppointmentTreatment.id)
            .join(
                PlannedTreatmentItem,
                PlannedTreatmentItem.id == AppointmentTreatment.planned_treatment_item_id,
            )
            .join(Appointment, Appointment.id == AppointmentTreatment.appointment_id)
            .where(
                PlannedTreatmentItem.treatment_plan_id == TreatmentPlan.id,
                PlannedTreatmentItem.clinic_id == clinic_id,
                Appointment.clinic_id == clinic_id,
                Appointment.status != "cancelled",
            )
            .limit(1)
            .correlate(TreatmentPlan)
            .exists()
        )

        plans = (
            await db.execute(
                select(
                    TreatmentPlan.id,
                    TreatmentPlan.status,
                    item_count.label("items"),
                    completed_count.label("done"),
                    has_booking.label("booked"),
                ).where(
                    TreatmentPlan.clinic_id == clinic_id,
                    TreatmentPlan.deleted_at.is_(None),
                    TreatmentPlan.confirmed_at >= start_at,
                    TreatmentPlan.confirmed_at < end_at,
                    TreatmentPlan.status.in_(
                        ["pending", "active", "completed", "archived", "closed"]
                    ),
                )
            )
        ).all()

        plan_count = len(plans)
        booked_plans = sum(bool(row.booked) for row in plans)
        completed_plans = sum(
            row.status in ("completed", "archived") and int(row.done or 0) > 0 for row in plans
        )
        items_total = sum(int(row.items or 0) for row in plans)
        items_completed = sum(int(row.done or 0) for row in plans)
        return {
            "period_start": date_from,
            "period_end": date_to,
            "confirmed_plans": plan_count,
            "booked_plans": booked_plans,
            "completed_plans": completed_plans,
            "items_total": items_total,
            "items_completed": items_completed,
            "booking_conversion_rate": booked_plans / plan_count if plan_count else 0.0,
            "plan_completion_rate": completed_plans / plan_count if plan_count else 0.0,
            "item_completion_rate": items_completed / items_total if items_total else 0.0,
        }
