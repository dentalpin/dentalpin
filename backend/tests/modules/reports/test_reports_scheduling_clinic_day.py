"""The scheduling report counts appointments on the clinic's days.

``Appointment.start_time`` is stored in UTC. The report filtered with
``date(start_time)`` (the UTC date) and bucketed weekdays with
``extract(dow, start_time)`` (the UTC weekday). In a Mexico City clinic
(UTC-6) a Monday 19:00 appointment (Tuesday 01:00 UTC) was missing from
Monday's report and counted as a Tuesday.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.agenda.models import Appointment
from app.modules.patients.models import Patient
from app.modules.reports.services.scheduling import SchedulingReportService

MONDAY = date(2026, 1, 12)
# 19:00 on Monday 12/01 in Mexico City is 01:00 UTC on Tuesday 13/01.
EVENING_UTC = datetime(2026, 1, 13, 1, 0, tzinfo=UTC)


async def _evening_appointment(db: AsyncSession, clinic: Clinic, patient: Patient) -> User:
    clinic.timezone = "America/Mexico_City"
    dentist = User(
        email=f"d-{uuid4().hex[:8]}@test.clinic", password_hash="x", first_name="D", last_name="E"
    )
    db.add(dentist)
    await db.flush()
    db.add(
        Appointment(
            clinic_id=clinic.id,
            patient_id=patient.id,
            professional_id=dentist.id,
            cabinet="Gabinete 1",
            start_time=EVENING_UTC,
            end_time=EVENING_UTC + timedelta(minutes=30),
            status="completed",
        )
    )
    await db.commit()
    return dentist


@pytest.mark.asyncio
async def test_period_filters_use_the_clinic_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    dentist = await _evening_appointment(db_session, test_clinic, test_patient)
    cid = test_clinic.id

    summary = await SchedulingReportService.get_summary(db_session, cid, MONDAY, MONDAY)
    assert summary["total_appointments"] == 1
    first = await SchedulingReportService.get_first_visits(db_session, cid, MONDAY, MONDAY)
    assert (first["new_patients"], first["total_appointments"]) == (1, 1)
    hours = await SchedulingReportService.get_hours_by_professional(db_session, cid, MONDAY, MONDAY)
    assert [(h["professional_id"], h["total_minutes"]) for h in hours] == [(dentist.id, 30)]
    cabinets = await SchedulingReportService.get_cabinet_utilization(
        db_session, cid, MONDAY, MONDAY
    )
    assert [c["cabinet"] for c in cabinets] == ["Gabinete 1"]

    tuesday = MONDAY + timedelta(days=1)
    assert (await SchedulingReportService.get_summary(db_session, cid, tuesday, tuesday))[
        "total_appointments"
    ] == 0


@pytest.mark.asyncio
async def test_weekday_buckets_use_the_clinic_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    await _evening_appointment(db_session, test_clinic, test_patient)
    rows = await SchedulingReportService.get_by_day_of_week(
        db_session, test_clinic.id, MONDAY, MONDAY + timedelta(days=6)
    )
    assert [(r["day_name"], r["appointment_count"]) for r in rows] == [("monday", 1)]
