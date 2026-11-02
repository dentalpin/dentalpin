"""State machine + audit trail tests for appointment status transitions.

Validates:

- Every valid transition in :data:`VALID_TRANSITIONS` succeeds and appends a
  status event with the expected ``from_status`` / ``to_status``.
- Every invalid transition raises :class:`InvalidTransitionError` and does
  not mutate the appointment.
- Same-state transitions raise :class:`AlreadyInStateError`.
- ``Appointment.current_status_since`` is updated in lock step with each
  transition.
- The synthetic initial event is inserted on ``create_appointment``.
- ``cancel_appointment`` (``DELETE /appointments/{id}``) delegates into
  ``transition`` so the audit trail captures it.
- ``update_appointment`` with a ``status`` field goes through ``transition``
  and records the event — preserving the drag & drop / PUT compat path.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.agenda.models import Appointment, AppointmentStatusEvent, Cabinet
from app.modules.agenda.service import (
    VALID_TRANSITIONS,
    AlreadyInStateError,
    AppointmentService,
    InvalidTransitionError,
)
from app.modules.patients.models import Patient


async def _mkworld(db: AsyncSession) -> dict[str, UUID]:
    """Minimal fixtures: clinic + admin + dentist + cabinet + patient."""
    clinic = Clinic(
        id=uuid4(),
        name="TX Clinic",
        tax_id="B00000001",
        address={"city": "Madrid"},
        settings={},
    )
    admin = User(
        id=uuid4(),
        email=f"admin-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Admin",
        last_name="User",
        is_active=True,
    )
    dentist = User(
        id=uuid4(),
        email=f"dentist-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Dentist",
        last_name="User",
        is_active=True,
    )
    db.add_all([clinic, admin, dentist])
    await db.flush()
    db.add_all(
        [
            ClinicMembership(id=uuid4(), user_id=admin.id, clinic_id=clinic.id, role="admin"),
            ClinicMembership(
                id=uuid4(),
                user_id=dentist.id,
                clinic_id=clinic.id,
                role="dentist",
            ),
        ]
    )
    cabinet = Cabinet(
        id=uuid4(),
        clinic_id=clinic.id,
        name="Gabinete 1",
        color="#3B82F6",
        display_order=0,
        is_active=True,
    )
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Juan",
        last_name="Paciente",
    )
    db.add_all([cabinet, patient])
    await db.commit()

    return {
        "clinic_id": clinic.id,
        "admin_id": admin.id,
        "dentist_id": dentist.id,
        "cabinet_id": cabinet.id,
        "patient_id": patient.id,
    }


_PATHS: dict[str, list[str]] = {
    "scheduled": [],
    "confirmed": ["confirmed"],
    "checked_in": ["checked_in"],
    "in_treatment": ["checked_in", "in_treatment"],
    "completed": ["checked_in", "in_treatment", "completed"],
    "cancelled": ["cancelled"],
    "no_show": ["no_show"],
}


async def _mkapt(
    db: AsyncSession,
    world: dict[str, UUID],
    *,
    start: datetime | None = None,
    status: str = "scheduled",
) -> Appointment:
    # Spread starts so the unique slot index doesn't collide across tests
    # that build multiple appointments in the same DB.
    start = start or datetime(2026, 4, 22, 10, 0, tzinfo=UTC) + timedelta(
        minutes=30 * hash(status) % 180
    )
    apt = await AppointmentService.create_appointment(
        db,
        world["clinic_id"],
        {
            "patient_id": world["patient_id"],
            "professional_id": world["dentist_id"],
            "cabinet_id": world["cabinet_id"],
            "cabinet": "Gabinete 1",
            "start_time": start,
            "end_time": start + timedelta(minutes=30),
        },
        created_by=world["admin_id"],
    )
    for step in _PATHS[status]:
        apt = await AppointmentService.transition(db, apt, step, changed_by=world["admin_id"])
    await db.commit()
    return apt


@pytest.mark.asyncio
async def test_create_records_initial_event(db_session: AsyncSession) -> None:
    world = await _mkworld(db_session)
    apt = await _mkapt(db_session, world)

    events = (
        (
            await db_session.execute(
                select(AppointmentStatusEvent).where(
                    AppointmentStatusEvent.appointment_id == apt.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].from_status is None
    assert events[0].to_status == "scheduled"
    assert events[0].changed_by == world["admin_id"]


@pytest.mark.asyncio
async def test_current_status_since_moves_with_transition(
    db_session: AsyncSession,
) -> None:
    world = await _mkworld(db_session)
    apt = await _mkapt(db_session, world)
    original_since = apt.current_status_since

    await AppointmentService.transition(db_session, apt, "checked_in", changed_by=world["admin_id"])
    await db_session.commit()

    assert apt.status == "checked_in"
    assert apt.current_status_since > original_since


@pytest.mark.asyncio
async def test_same_state_raises_already_in_state(db_session: AsyncSession) -> None:
    world = await _mkworld(db_session)
    apt = await _mkapt(db_session, world)

    with pytest.raises(AlreadyInStateError):
        await AppointmentService.transition(
            db_session, apt, "scheduled", changed_by=world["admin_id"]
        )


@pytest.mark.asyncio
async def test_invalid_transition_rejected(db_session: AsyncSession) -> None:
    world = await _mkworld(db_session)
    apt = await _mkapt(db_session, world, status="completed")

    with pytest.raises(InvalidTransitionError):
        await AppointmentService.transition(
            db_session, apt, "scheduled", changed_by=world["admin_id"]
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,target",
    sorted((src, tgt) for src, targets in VALID_TRANSITIONS.items() for tgt in targets),
)
async def test_all_valid_transitions_succeed(
    db_session: AsyncSession, source: str, target: str
) -> None:
    world = await _mkworld(db_session)
    apt = await _mkapt(db_session, world, status=source)

    await AppointmentService.transition(
        db_session, apt, target, changed_by=world["admin_id"], note=f"via {source}"
    )
    await db_session.commit()

    assert apt.status == target
    last_event = (
        (
            await db_session.execute(
                select(AppointmentStatusEvent)
                .where(AppointmentStatusEvent.appointment_id == apt.id)
                .order_by(AppointmentStatusEvent.changed_at.desc())
            )
        )
        .scalars()
        .first()
    )
    assert last_event is not None
    assert last_event.from_status == source
    assert last_event.to_status == target
    assert last_event.note == f"via {source}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,target",
    [
        (src, tgt)
        for src in VALID_TRANSITIONS
        for tgt in VALID_TRANSITIONS
        if tgt != src and tgt not in VALID_TRANSITIONS[src]
    ],
)
async def test_all_invalid_transitions_rejected(
    db_session: AsyncSession, source: str, target: str
) -> None:
    world = await _mkworld(db_session)
    apt = await _mkapt(db_session, world, status=source)

    with pytest.raises(InvalidTransitionError):
        await AppointmentService.transition(db_session, apt, target, changed_by=world["admin_id"])

    assert apt.status == source


@pytest.mark.asyncio
async def test_cancel_appointment_goes_through_transition(
    db_session: AsyncSession,
) -> None:
    world = await _mkworld(db_session)
    apt = await _mkapt(db_session, world)

    await AppointmentService.cancel_appointment(db_session, apt, changed_by=world["admin_id"])
    await db_session.commit()

    assert apt.status == "cancelled"
    events = (
        (
            await db_session.execute(
                select(AppointmentStatusEvent)
                .where(AppointmentStatusEvent.appointment_id == apt.id)
                .order_by(AppointmentStatusEvent.changed_at)
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 2
    assert events[-1].from_status == "scheduled"
    assert events[-1].to_status == "cancelled"
    assert events[-1].changed_by == world["admin_id"]


@pytest.mark.asyncio
async def test_cancel_already_cancelled_is_noop(db_session: AsyncSession) -> None:
    world = await _mkworld(db_session)
    apt = await _mkapt(db_session, world, status="cancelled")

    before = len(
        (
            await db_session.execute(
                select(AppointmentStatusEvent).where(
                    AppointmentStatusEvent.appointment_id == apt.id
                )
            )
        )
        .scalars()
        .all()
    )
    await AppointmentService.cancel_appointment(db_session, apt, changed_by=world["admin_id"])
    await db_session.commit()
    after = len(
        (
            await db_session.execute(
                select(AppointmentStatusEvent).where(
                    AppointmentStatusEvent.appointment_id == apt.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert before == after


@pytest.mark.asyncio
async def test_update_with_status_funnels_through_transition(
    db_session: AsyncSession,
) -> None:
    world = await _mkworld(db_session)
    apt = await _mkapt(db_session, world)

    await AppointmentService.update_appointment(
        db_session,
        apt,
        {"status": "confirmed"},
        changed_by=world["admin_id"],
    )
    await db_session.commit()

    assert apt.status == "confirmed"
    events = (
        (
            await db_session.execute(
                select(AppointmentStatusEvent)
                .where(AppointmentStatusEvent.appointment_id == apt.id)
                .order_by(AppointmentStatusEvent.changed_at)
            )
        )
        .scalars()
        .all()
    )
    assert [e.to_status for e in events] == ["scheduled", "confirmed"]


@pytest.mark.asyncio
async def test_update_without_status_does_not_create_event(
    db_session: AsyncSession,
) -> None:
    world = await _mkworld(db_session)
    apt = await _mkapt(db_session, world)

    await AppointmentService.update_appointment(
        db_session,
        apt,
        {"notes": "Bring pre-op form"},
        changed_by=world["admin_id"],
    )
    await db_session.commit()

    events = (
        (
            await db_session.execute(
                select(AppointmentStatusEvent).where(
                    AppointmentStatusEvent.appointment_id == apt.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1


@pytest.mark.asyncio
async def test_concurrent_check_ins_record_one_event(db_session: AsyncSession):
    """Two check-ins at once (kiosk and reception, or a double click) both
    passed the status check on their unlocked copy and wrote two
    scheduled→checked_in events. The second now waits and finds the
    appointment already checked in (#774)."""
    import asyncio

    from app.database import async_session_maker

    world = await _mkworld(db_session)
    apt = await _mkapt(db_session, world)
    await db_session.commit()

    async with async_session_maker() as first, async_session_maker() as second:
        mine = await first.get(Appointment, apt.id)
        theirs = await second.get(Appointment, apt.id)
        await AppointmentService.transition(first, mine, "checked_in")
        other = asyncio.create_task(AppointmentService.transition(second, theirs, "checked_in"))
        await asyncio.sleep(0.3)  # the second check-in reaches the lock
        await first.commit()
        with pytest.raises(AlreadyInStateError):
            await other
        await second.rollback()

    async with async_session_maker() as db:
        events = (
            (
                await db.execute(
                    select(AppointmentStatusEvent).where(
                        AppointmentStatusEvent.appointment_id == apt.id,
                        AppointmentStatusEvent.to_status == "checked_in",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(events) == 1
