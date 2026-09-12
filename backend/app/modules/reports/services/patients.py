"""Patient-stats family: demographics + visit frequency.

Sources: ``patients`` + ``agenda`` (both inside ``reports.depends``) —
computed on demand, no tables. Age bands and area are approximations
documented below, never fabricated precision: unknown birth dates and
unparseable addresses land in explicit ``unknown`` buckets.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agenda.models import Appointment
from app.modules.patients.models import Patient

AGE_BANDS: tuple[tuple[str, int | None, int | None], ...] = (
    ("0-17", 0, 17),
    ("18-34", 18, 34),
    ("35-54", 35, 54),
    ("55-74", 55, 74),
    ("75+", 75, None),
)


class PatientStatsService:
    """Demographics snapshot + visit frequency in a window."""

    @staticmethod
    async def demographics(db: AsyncSession, clinic_id: UUID) -> dict:
        """Age bands, gender split, area split, totals.

        Area reads ``address->>'city'`` with an ``unknown`` fallback —
        the address JSON has no contracted shape, so anything
        unparseable groups under ``unknown`` rather than being guessed.
        Archived patients are left out, as everywhere else in the app.
        """
        today = date.today()
        rows = (
            await db.execute(
                select(
                    Patient.date_of_birth,
                    Patient.gender,
                    Patient.address.op("->>")("city").label("city"),
                ).where(Patient.clinic_id == clinic_id, Patient.status != "archived")
            )
        ).all()

        bands: dict[str, int] = {label: 0 for label, _, _ in AGE_BANDS}
        bands["unknown"] = 0
        genders: dict[str, int] = {}
        areas: dict[str, int] = {}
        for dob, gender, city in rows:
            if dob is None:
                bands["unknown"] += 1
            else:
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                label = next(
                    (lbl for lbl, lo, hi in AGE_BANDS if lo <= age and (hi is None or age <= hi)),
                    "unknown",
                )
                bands[label] += 1
            genders[gender or "unknown"] = genders.get(gender or "unknown", 0) + 1
            area = (city or "").strip() or "unknown"
            areas[area] = areas.get(area, 0) + 1
        return {
            "total_patients": len(rows),
            "age_bands": [{"band": k, "count": v} for k, v in bands.items()],
            "genders": [{"gender": k, "count": v} for k, v in sorted(genders.items())],
            "areas": sorted(
                [{"area": k, "count": v} for k, v in areas.items()],
                key=lambda r: -r["count"],
            )[:50],
        }

    @staticmethod
    async def visit_frequency(
        db: AsyncSession, clinic_id: UUID, date_from: date, date_to: date
    ) -> dict:
        """New-vs-returning + visits per patient in the window.

        ``new`` = patient whose only appointment ever is inside the
        window; ``returning`` = anyone with an appointment outside it
        (or several inside). Cancelled and no-show appointments never
        count as visits.
        """
        kept = ("scheduled", "confirmed", "checked_in", "in_treatment", "completed")
        # date_to is inclusive: the window closes at the next midnight.
        window_end = date_to + timedelta(days=1)
        in_window = (
            select(Appointment.patient_id, func.count(Appointment.id).label("n"))
            .where(
                Appointment.clinic_id == clinic_id,
                Appointment.patient_id.is_not(None),
                Appointment.status.in_(kept),
                Appointment.start_time >= date_from,
                Appointment.start_time < window_end,
            )
            .group_by(Appointment.patient_id)
            .subquery()
        )
        ever_before = (
            select(Appointment.patient_id)
            .where(
                Appointment.clinic_id == clinic_id,
                Appointment.patient_id.is_not(None),
                Appointment.status.in_(kept),
                Appointment.start_time < date_from,
            )
            .distinct()
            .subquery()
        )
        rows = (
            await db.execute(
                select(
                    in_window.c.patient_id,
                    in_window.c.n,
                    ever_before.c.patient_id.is_not(None).label("seen_before"),
                ).outerjoin(ever_before, ever_before.c.patient_id == in_window.c.patient_id)
            )
        ).all()
        new_patients = sum(1 for _, _, seen in rows if not seen)
        returning = sum(1 for _, _, seen in rows if seen)
        total_visits = sum(n for _, n, _ in rows)
        active = len(rows)
        return {
            "new_patients": new_patients,
            "returning_patients": returning,
            "total_visits": total_visits,
            "visits_per_patient": round(total_visits / active, 2) if active else 0.0,
        }
