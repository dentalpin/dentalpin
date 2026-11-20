"""Productivity and visit-frequency reports cut their window on clinic days.

Both compared ``Appointment.start_time`` (an instant) with bare dates, which
Postgres reads as UTC midnights. In a Mexico City clinic (UTC-6) a 19:00
appointment on the 11th is 01:00 UTC on the 12th: it was counted in the
12th's productivity and visits, and missing from the 11th's.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.agenda.models import Appointment
from app.modules.patients.models import Patient
from app.modules.reports.services import OperationalReportService, PatientStatsService

DAY = date(2026, 1, 12)
EVENING_BEFORE_UTC = datetime(2026, 1, 12, 1, 0, tzinfo=UTC)  # 19:00 on the 11th
MORNING_UTC = datetime(2026, 1, 12, 16, 0, tzinfo=UTC)  # 10:00 on the 12th


async def _seed(db: AsyncSession, clinic: Clinic, patient: Patient) -> None:
    clinic.timezone = "America/Mexico_City"
    dentist = User(
        email=f"d-{uuid4().hex[:8]}@test.clinic", password_hash="x", first_name="D", last_name="E"
    )
    db.add(dentist)
    await db.flush()
    for start in (EVENING_BEFORE_UTC, MORNING_UTC):
        db.add(
            Appointment(
                clinic_id=clinic.id,
                patient_id=patient.id,
                professional_id=dentist.id,
                start_time=start,
                end_time=start + timedelta(minutes=30),
                status="completed",
            )
        )
    await db.commit()


@pytest.mark.asyncio
async def test_productivity_counts_appointments_on_their_local_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    await _seed(db_session, test_clinic, test_patient)

    async def completed(day: date) -> int:
        report = await OperationalReportService.productivity(db_session, test_clinic.id, day, day)
        return report["completed_total"]

    assert await completed(DAY - timedelta(days=1)) == 1
    assert await completed(DAY) == 1


@pytest.mark.asyncio
async def test_visit_frequency_uses_local_days_for_window_and_history(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    await _seed(db_session, test_clinic, test_patient)

    report = await PatientStatsService.visit_frequency(db_session, test_clinic.id, DAY, DAY)
    # One visit on the 12th, by a patient already seen on the 11th.
    assert (report["total_visits"], report["new_patients"], report["returning_patients"]) == (
        1,
        0,
        1,
    )
