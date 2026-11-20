"""``appointment.scheduled`` matches recalls on the clinic's calendar month.

The handler took ``start_time.date()``, the UTC date. A 19:00 appointment
on Jan 31 in Mexico City (01:00 UTC on Feb 1) linked a recall due in
February, and an 08:00 appointment on Feb 1 in Tokyo (23:00 UTC on Jan 31)
did not link one.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.agenda.models import Appointment
from app.modules.patients.models import Patient
from app.modules.recalls.events import on_appointment_scheduled
from app.modules.recalls.models import Recall

FEBRUARY = date(2026, 2, 1)


async def _scenario(
    db: AsyncSession, clinic: Clinic, patient: Patient, zone: str, start: datetime
) -> Recall:
    clinic.timezone = zone
    dentist = User(
        email=f"d-{uuid4().hex[:8]}@test.clinic", password_hash="x", first_name="D", last_name="E"
    )
    db.add(dentist)
    await db.flush()
    appointment = Appointment(
        clinic_id=clinic.id,
        patient_id=patient.id,
        professional_id=dentist.id,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        status="scheduled",
    )
    recall = Recall(
        clinic_id=clinic.id,
        patient_id=patient.id,
        due_month=FEBRUARY,
        reason="hygiene",
        status="pending",
    )
    db.add_all([appointment, recall])
    await db.flush()
    await on_appointment_scheduled(
        {
            "appointment_id": str(appointment.id),
            "clinic_id": str(clinic.id),
            "patient_id": str(patient.id),
            "start_time": start.isoformat(),
        },
        db=db,
    )
    await db.flush()
    await db.refresh(recall)
    return recall


@pytest.mark.asyncio
async def test_a_january_evening_appointment_does_not_take_a_february_recall(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    # Jan 31, 19:00 in Mexico City.
    start = datetime(2026, 2, 1, 1, 0, tzinfo=UTC)
    recall = await _scenario(db_session, test_clinic, test_patient, "America/Mexico_City", start)
    assert recall.linked_appointment_id is None
    assert recall.status == "pending"


@pytest.mark.asyncio
async def test_a_february_morning_appointment_takes_the_february_recall(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    # Feb 1, 08:00 in Tokyo.
    start = datetime(2026, 1, 31, 23, 0, tzinfo=UTC)
    recall = await _scenario(db_session, test_clinic, test_patient, "Asia/Tokyo", start)
    assert recall.linked_appointment_id is not None
    assert recall.status == "contacted_scheduled"
