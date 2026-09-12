"""Operational family: staff productivity from agenda + treatment plans.

Sources: ``agenda`` + ``treatment_plan`` (both inside
``reports.depends``) — computed on demand, no tables. Completion rate
itself already lives in the scheduling summary; this family adds the
per-professional and per-cabinet cuts the manager dashboard needs.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import User
from app.modules.agenda.models import Appointment
from app.modules.treatment_plan.models import TreatmentPlan


class OperationalReportService:
    """Completed-appointment productivity in a window."""

    @staticmethod
    async def productivity(
        db: AsyncSession, clinic_id: UUID, date_from: date, date_to: date
    ) -> dict:
        """Completed appointments per professional and per cabinet.

        ``date_to`` is inclusive. Professionals resolve to display
        names; cabinets fall back to ``unassigned`` (booking exists
        before any cabinet decision).
        """
        window_end = date_to + timedelta(days=1)
        base = [
            Appointment.clinic_id == clinic_id,
            Appointment.status == "completed",
            Appointment.start_time >= date_from,
            Appointment.start_time < window_end,
        ]
        by_pro = (
            await db.execute(
                select(
                    Appointment.professional_id,
                    func.concat(User.first_name, " ", User.last_name).label("name"),
                    func.count(Appointment.id).label("completed"),
                )
                .join(User, User.id == Appointment.professional_id)
                .where(*base)
                .group_by(Appointment.professional_id, User.first_name, User.last_name)
                .order_by(func.count(Appointment.id).desc())
            )
        ).all()
        by_cab = (
            await db.execute(
                select(
                    func.coalesce(Appointment.cabinet, "unassigned").label("cabinet"),
                    func.count(Appointment.id).label("completed"),
                )
                .where(*base)
                .group_by("cabinet")
                .order_by(func.count(Appointment.id).desc())
            )
        ).all()
        total = sum(r.completed for r in by_pro)
        plans = (
            await db.execute(
                select(TreatmentPlan.status, func.count(TreatmentPlan.id))
                .where(TreatmentPlan.clinic_id == clinic_id)
                .group_by(TreatmentPlan.status)
            )
        ).all()
        return {
            "completed_total": total,
            "by_professional": [
                {
                    "professional_id": str(r.professional_id),
                    "professional_name": r.name,
                    "completed": r.completed,
                }
                for r in by_pro
            ],
            "by_cabinet": [{"cabinet": r.cabinet, "completed": r.completed} for r in by_cab],
            "plan_pipeline": [{"status": status, "count": count} for status, count in plans],
        }
