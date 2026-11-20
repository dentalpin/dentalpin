"""``find_free_slots`` sees every booking on the last day it searches.

It fetched the professional's appointments between UTC midnights, while the
open hours come back on the clinic's clock. In a Mexico City clinic (UTC-6)
the last day's evening (from 18:00 local, i.e. after 23:59 UTC) was never
fetched, so a booked 19:00 slot was offered to the copilot as free.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.modules.agenda.service import AppointmentService
from app.modules.patients.models import Patient
from app.modules.schedules import tools
from app.modules.schedules.services.availability import AvailabilityService

DAY = date(2031, 3, 3)  # searched with days_ahead=1, so the last day is the 4th
TZ = "America/Mexico_City"
# 18:00–20:00 local on the 4th is 00:00–02:00 UTC on the 5th.
OPEN_START = datetime(2031, 3, 5, 0, 0, tzinfo=UTC)
OPEN_END = datetime(2031, 3, 5, 2, 0, tzinfo=UTC)
BOOKED = datetime(2031, 3, 5, 1, 0, tzinfo=UTC)  # 19:00 local


@pytest.mark.asyncio
async def test_evening_booking_on_the_last_day_is_not_offered(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient, monkeypatch
):
    test_clinic.timezone = TZ
    dentist = User(
        email=f"d-{uuid4().hex[:8]}@test.clinic", password_hash="x", first_name="D", last_name="E"
    )
    db_session.add(dentist)
    await db_session.flush()
    db_session.add(ClinicMembership(user_id=dentist.id, clinic_id=test_clinic.id, role="dentist"))
    await AppointmentService.create_appointment(
        db_session,
        test_clinic.id,
        {
            "patient_id": test_patient.id,
            "professional_id": dentist.id,
            "start_time": BOOKED,
            "end_time": BOOKED + timedelta(minutes=30),
        },
    )
    await db_session.commit()

    async def resolve(db, clinic_id, start, end, professional_id=None):
        return TZ, [SimpleNamespace(start=OPEN_START, end=OPEN_END, state="open")]

    monkeypatch.setattr(AvailabilityService, "resolve", staticmethod(resolve))
    ctx = SimpleNamespace(db=db_session, clinic_id=test_clinic.id)
    result = await tools._find_free_slots(
        ctx,
        tools.FreeSlotsArgs(professional_id=dentist.id, date_from=DAY, days_ahead=1),
    )
    windows = [
        (w["start"].astimezone(UTC), w["end"].astimezone(UTC)) for w in result["free_windows"]
    ]
    assert windows == [(OPEN_START, BOOKED), (BOOKED + timedelta(minutes=30), OPEN_END)]
