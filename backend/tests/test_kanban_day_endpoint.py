"""Kanban day endpoint tests (issue #51).

The snapshot is the professionals strip: one pill per working
professional today, state derived from current appointments (and from
the `schedules` module when installed).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.agenda.kanban_service import KanbanDayService
from app.modules.agenda.models import Cabinet
from app.modules.agenda.service import AppointmentService
from app.modules.patients.models import Patient


async def _world(db: AsyncSession) -> dict[str, UUID]:
    clinic = Clinic(id=uuid4(), name="K", tax_id="B0", address={}, settings={})
    dentist = User(
        id=uuid4(),
        email=f"d-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Ada",
        last_name="Who",
        is_active=True,
    )
    hygienist = User(
        id=uuid4(),
        email=f"h-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Hyg",
        last_name="Nist",
        is_active=True,
    )
    inactive = User(
        id=uuid4(),
        email=f"i-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Off",
        last_name="Line",
        is_active=False,
    )
    receptionist = User(
        id=uuid4(),
        email=f"r-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Rec",
        last_name="Ep",
        is_active=True,
    )
    cabinet = Cabinet(
        id=uuid4(),
        clinic_id=clinic.id,
        name="A",
        color="#000",
        display_order=0,
        is_active=True,
    )
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="P", last_name="Q")
    db.add_all([clinic, dentist, hygienist, inactive, receptionist, cabinet, patient])
    await db.flush()
    db.add_all(
        [
            ClinicMembership(id=uuid4(), user_id=dentist.id, clinic_id=clinic.id, role="dentist"),
            ClinicMembership(
                id=uuid4(), user_id=hygienist.id, clinic_id=clinic.id, role="hygienist"
            ),
            ClinicMembership(id=uuid4(), user_id=inactive.id, clinic_id=clinic.id, role="dentist"),
            # Receptionists must NOT appear in the strip.
            ClinicMembership(
                id=uuid4(),
                user_id=receptionist.id,
                clinic_id=clinic.id,
                role="receptionist",
            ),
        ]
    )
    await db.commit()
    return {
        "clinic_id": clinic.id,
        "dentist_id": dentist.id,
        "hygienist_id": hygienist.id,
        "inactive_id": inactive.id,
        "receptionist_id": receptionist.id,
        "cabinet_id": cabinet.id,
        "patient_id": patient.id,
    }


@pytest.mark.asyncio
async def test_strip_lists_only_active_clinical_professionals(
    db_session: AsyncSession,
) -> None:
    world = await _world(db_session)
    snap = await KanbanDayService.snapshot(db_session, world["clinic_id"], date.today())
    ids = {p["id"] for p in snap["professionals"]}
    assert str(world["dentist_id"]) in ids
    assert str(world["hygienist_id"]) in ids
    assert str(world["receptionist_id"]) not in ids
    assert str(world["inactive_id"]) not in ids


@pytest.mark.asyncio
async def test_strip_marks_in_treatment_professional(
    db_session: AsyncSession,
) -> None:
    world = await _world(db_session)

    now = datetime.now(UTC)
    today = now.date()
    # Create a scheduled appointment and push it to in_treatment through
    # the proper lifecycle (scheduled → checked_in → in_treatment).
    apt = await AppointmentService.create_appointment(
        db_session,
        world["clinic_id"],
        {
            "patient_id": world["patient_id"],
            "professional_id": world["dentist_id"],
            "cabinet_id": world["cabinet_id"],
            "start_time": datetime(today.year, today.month, today.day, 9, 0, tzinfo=UTC),
            "end_time": datetime(today.year, today.month, today.day, 9, 30, tzinfo=UTC),
        },
    )
    await AppointmentService.transition(db_session, apt, "checked_in")
    await AppointmentService.transition(db_session, apt, "in_treatment")
    await db_session.commit()

    snap = await KanbanDayService.snapshot(db_session, world["clinic_id"], today)
    dentist_pill = next(p for p in snap["professionals"] if p["id"] == str(world["dentist_id"]))
    assert dentist_pill["state"] == "in_treatment"
    assert dentist_pill["current_appointment_id"] == str(apt.id)
    assert dentist_pill["current_cabinet_id"] == str(world["cabinet_id"])


@pytest.mark.asyncio
async def test_strip_marks_off_when_schedules_has_no_hours(
    db_session: AsyncSession,
) -> None:
    # The ``schedules`` module is installed in the test harness but no
    # hours are seeded for either the clinic or the professional, so
    # AvailabilityService classifies every minute as "off" — the strip
    # surfaces that so receptionists know the professional isn't in.
    world = await _world(db_session)
    snap = await KanbanDayService.snapshot(db_session, world["clinic_id"], date.today())
    hyg = next(p for p in snap["professionals"] if p["id"] == str(world["hygienist_id"]))
    assert hyg["state"] == "off"
    assert hyg["current_appointment_id"] is None


@pytest.mark.asyncio
async def test_strip_excludes_appointments_on_other_days(
    db_session: AsyncSession,
) -> None:
    world = await _world(db_session)
    tomorrow = datetime.now(UTC) + timedelta(days=1)

    apt = await AppointmentService.create_appointment(
        db_session,
        world["clinic_id"],
        {
            "patient_id": world["patient_id"],
            "professional_id": world["dentist_id"],
            "cabinet_id": world["cabinet_id"],
            "start_time": tomorrow.replace(hour=9, minute=0, second=0, microsecond=0),
            "end_time": tomorrow.replace(hour=9, minute=30, second=0, microsecond=0),
        },
    )
    await AppointmentService.transition(db_session, apt, "checked_in")
    await AppointmentService.transition(db_session, apt, "in_treatment")
    await db_session.commit()

    # Snapshot for TODAY must NOT mark the dentist as in_treatment — they
    # have no active appointment today (tomorrow's one doesn't count).
    # UTC, matching the `tomorrow` above: with local date.today() in a
    # timezone east of UTC the "tomorrow" appointment lands on the day
    # being snapshotted and the exclusion this test checks never applies.
    snap = await KanbanDayService.snapshot(db_session, world["clinic_id"], datetime.now(UTC).date())
    dentist_pill = next(p for p in snap["professionals"] if p["id"] == str(world["dentist_id"]))
    assert dentist_pill["state"] != "in_treatment"
    assert dentist_pill["current_appointment_id"] is None
