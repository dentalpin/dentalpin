"""Appointment lifecycle analytics select appointments by the clinic's day.

``Appointment.start_time`` is stored in UTC; the shared filter used
``date(start_time)``, the UTC date. In a Mexico City clinic (UTC-6) a
19:00 appointment on the 12th (01:00 UTC on the 13th) was missing from the
12th's funnel, waiting times, punctuality and duration figures.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.agenda.models import Appointment
from app.modules.patients.models import Patient
from app.modules.reports.services import AppointmentLifecycleService

DAY = date(2026, 1, 12)
EVENING_UTC = datetime(2026, 1, 13, 1, 0, tzinfo=UTC)  # 19:00 local on the 12th


@pytest.mark.asyncio
async def test_funnel_counts_an_evening_appointment_on_its_local_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    test_clinic.timezone = "America/Mexico_City"
    dentist = User(
        email=f"d-{uuid4().hex[:8]}@test.clinic", password_hash="x", first_name="D", last_name="E"
    )
    db_session.add(dentist)
    await db_session.flush()
    db_session.add(
        Appointment(
            clinic_id=test_clinic.id,
            patient_id=test_patient.id,
            professional_id=dentist.id,
            start_time=EVENING_UTC,
            end_time=EVENING_UTC + timedelta(minutes=30),
            status="completed",
        )
    )
    await db_session.commit()

    day = await AppointmentLifecycleService.funnel(db_session, test_clinic.id, DAY, DAY)
    assert (day["total"], day["counts_by_status"]["completed"]) == (1, 1)
    next_day = DAY + timedelta(days=1)
    assert (
        await AppointmentLifecycleService.funnel(db_session, test_clinic.id, next_day, next_day)
    )["total"] == 0
