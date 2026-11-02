"""Cabinet assignment lifecycle tests (issue #51).

Covers:
- Creating an appointment without a cabinet (deferred assignment).
- `AppointmentService.assign_cabinet` happy path + reassign + unassign.
- Denormalized `cabinet_assigned_at` / `cabinet_assigned_by` stay in sync.
- Audit trail (`appointment_cabinet_events`) is append-only and correct.
- Bus event `APPOINTMENT_CABINET_CHANGED` fires with the right payload.
- Slot-conflict 409 when reassigning to an occupied cabinet.
- Transition to `in_treatment` is blocked when `cabinet_id IS NULL`
  (`CabinetRequiredError`) and succeeds once the cabinet is assigned.
- Multi-tenancy on the history endpoint / service.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.core.events import EventType, event_bus
from app.modules.agenda.models import (
    Appointment,
    AppointmentCabinetEvent,
    Cabinet,
)
from app.modules.agenda.service import (
    AppointmentService,
    CabinetRequiredError,
)
from app.modules.patients.models import Patient


async def _world(db: AsyncSession) -> dict[str, UUID]:
    clinic = Clinic(id=uuid4(), name="CB", tax_id="B0", address={"city": "M"}, settings={})
    admin = User(
        id=uuid4(),
        email=f"a-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="A",
        last_name="D",
        is_active=True,
    )
    dentist = User(
        id=uuid4(),
        email=f"d-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Dra",
        last_name="Who",
        is_active=True,
    )
    cabinet_a = Cabinet(
        id=uuid4(),
        clinic_id=clinic.id,
        name="A",
        color="#000",
        display_order=0,
        is_active=True,
    )
    cabinet_b = Cabinet(
        id=uuid4(),
        clinic_id=clinic.id,
        name="B",
        color="#fff",
        display_order=1,
        is_active=True,
    )
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="P", last_name="Q")
    db.add_all([clinic, admin, dentist, cabinet_a, cabinet_b, patient])
    await db.flush()
    db.add_all(
        [
            ClinicMembership(id=uuid4(), user_id=admin.id, clinic_id=clinic.id, role="admin"),
            ClinicMembership(id=uuid4(), user_id=dentist.id, clinic_id=clinic.id, role="dentist"),
        ]
    )
    await db.commit()
    return {
        "clinic_id": clinic.id,
        "admin_id": admin.id,
        "dentist_id": dentist.id,
        "cabinet_a": cabinet_a.id,
        "cabinet_b": cabinet_b.id,
        "patient_id": patient.id,
    }


async def _mkapt(
    db: AsyncSession,
    world: dict[str, UUID],
    *,
    start: datetime | None = None,
    cabinet_id: UUID | None = None,
) -> Appointment:
    start = start or datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    apt = await AppointmentService.create_appointment(
        db,
        world["clinic_id"],
        {
            "patient_id": world["patient_id"],
            "professional_id": world["dentist_id"],
            "cabinet_id": cabinet_id,
            "start_time": start,
            "end_time": start + timedelta(minutes=30),
        },
        created_by=world["admin_id"],
    )
    await db.commit()
    return apt


@pytest.mark.asyncio
async def test_create_without_cabinet_leaves_audit_empty(
    db_session: AsyncSession,
) -> None:
    world = await _world(db_session)
    apt = await _mkapt(db_session, world)

    assert apt.cabinet_id is None
    assert apt.cabinet is None
    assert apt.cabinet_assigned_at is None

    events = (
        (
            await db_session.execute(
                select(AppointmentCabinetEvent).where(
                    AppointmentCabinetEvent.appointment_id == apt.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert events == []


@pytest.mark.asyncio
async def test_create_with_cabinet_seeds_initial_event(
    db_session: AsyncSession,
) -> None:
    world = await _world(db_session)
    apt = await _mkapt(db_session, world, cabinet_id=world["cabinet_a"])

    assert apt.cabinet_id == world["cabinet_a"]
    assert apt.cabinet_assigned_at is not None
    assert apt.cabinet_assigned_by == world["admin_id"]

    events = (
        (
            await db_session.execute(
                select(AppointmentCabinetEvent).where(
                    AppointmentCabinetEvent.appointment_id == apt.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].from_cabinet_id is None
    assert events[0].to_cabinet_id == world["cabinet_a"]


@pytest.mark.asyncio
async def test_assign_then_reassign_then_unassign(
    db_session: AsyncSession,
) -> None:
    world = await _world(db_session)
    apt = await _mkapt(db_session, world)

    # Assign A
    await AppointmentService.assign_cabinet(
        db_session, apt, world["cabinet_a"], changed_by=world["admin_id"]
    )
    await db_session.commit()
    assert apt.cabinet_id == world["cabinet_a"]
    assert apt.cabinet == "A"
    assert apt.cabinet_assigned_at is not None

    # Reassign to B
    await AppointmentService.assign_cabinet(
        db_session, apt, world["cabinet_b"], changed_by=world["admin_id"]
    )
    await db_session.commit()
    assert apt.cabinet_id == world["cabinet_b"]

    # Unassign
    await AppointmentService.assign_cabinet(db_session, apt, None, changed_by=world["admin_id"])
    await db_session.commit()
    assert apt.cabinet_id is None
    assert apt.cabinet is None
    assert apt.cabinet_assigned_at is None
    assert apt.cabinet_assigned_by is None

    events = (
        (
            await db_session.execute(
                select(AppointmentCabinetEvent)
                .where(AppointmentCabinetEvent.appointment_id == apt.id)
                .order_by(AppointmentCabinetEvent.changed_at)
            )
        )
        .scalars()
        .all()
    )
    assert [(e.from_cabinet_id, e.to_cabinet_id) for e in events] == [
        (None, world["cabinet_a"]),
        (world["cabinet_a"], world["cabinet_b"]),
        (world["cabinet_b"], None),
    ]


@pytest.mark.asyncio
async def test_assign_same_cabinet_is_noop(db_session: AsyncSession) -> None:
    world = await _world(db_session)
    apt = await _mkapt(db_session, world, cabinet_id=world["cabinet_a"])

    before = len(
        (
            await db_session.execute(
                select(AppointmentCabinetEvent).where(
                    AppointmentCabinetEvent.appointment_id == apt.id
                )
            )
        )
        .scalars()
        .all()
    )
    await AppointmentService.assign_cabinet(
        db_session, apt, world["cabinet_a"], changed_by=world["admin_id"]
    )
    await db_session.commit()
    after = len(
        (
            await db_session.execute(
                select(AppointmentCabinetEvent).where(
                    AppointmentCabinetEvent.appointment_id == apt.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert before == after


@pytest.mark.asyncio
async def test_assign_publishes_bus_event(db_session: AsyncSession) -> None:
    world = await _world(db_session)
    apt = await _mkapt(db_session, world)

    captured: list[tuple[str, dict[str, Any]]] = []

    def _spy(data: dict[str, Any]) -> None:
        captured.append((EventType.APPOINTMENT_CABINET_CHANGED, data))

    event_bus.subscribe(EventType.APPOINTMENT_CABINET_CHANGED, _spy)
    try:
        await AppointmentService.assign_cabinet(
            db_session, apt, world["cabinet_a"], changed_by=world["admin_id"]
        )
        await db_session.commit()
    finally:
        event_bus.unsubscribe(EventType.APPOINTMENT_CABINET_CHANGED, _spy)

    assert len(captured) == 1
    _, payload = captured[0]
    assert payload["appointment_id"] == str(apt.id)
    assert payload["from_cabinet_id"] is None
    assert payload["to_cabinet_id"] == str(world["cabinet_a"])
    assert payload["changed_by"] == str(world["admin_id"])


@pytest.mark.asyncio
async def test_assign_conflict_raises_integrity_error(
    db_session: AsyncSession,
) -> None:
    world = await _world(db_session)
    start = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
    # Two appointments at the same slot, different cabinets initially so
    # the unique slot index isn't triggered on create.
    apt1 = await _mkapt(db_session, world, start=start, cabinet_id=world["cabinet_a"])
    apt2 = await _mkapt(db_session, world, start=start, cabinet_id=world["cabinet_b"])
    assert apt1.id != apt2.id

    with pytest.raises(IntegrityError):
        await AppointmentService.assign_cabinet(
            db_session, apt2, world["cabinet_a"], changed_by=world["admin_id"]
        )


@pytest.mark.asyncio
async def test_transition_to_in_treatment_requires_cabinet(
    db_session: AsyncSession,
) -> None:
    world = await _world(db_session)
    apt = await _mkapt(db_session, world)  # no cabinet
    await AppointmentService.transition(db_session, apt, "checked_in", changed_by=world["admin_id"])
    await db_session.commit()

    with pytest.raises(CabinetRequiredError):
        await AppointmentService.transition(
            db_session, apt, "in_treatment", changed_by=world["admin_id"]
        )


@pytest.mark.asyncio
async def test_transition_to_in_treatment_succeeds_after_assignment(
    db_session: AsyncSession,
) -> None:
    world = await _world(db_session)
    apt = await _mkapt(db_session, world)

    await AppointmentService.transition(db_session, apt, "checked_in", changed_by=world["admin_id"])
    await AppointmentService.assign_cabinet(
        db_session, apt, world["cabinet_a"], changed_by=world["admin_id"]
    )
    await AppointmentService.transition(
        db_session, apt, "in_treatment", changed_by=world["admin_id"]
    )
    await db_session.commit()

    assert apt.status == "in_treatment"
    assert apt.cabinet_id == world["cabinet_a"]


@pytest.mark.asyncio
async def test_list_cabinet_events_respects_clinic(db_session: AsyncSession) -> None:
    world_a = await _world(db_session)
    world_b = await _world(db_session)
    apt_a = await _mkapt(db_session, world_a, cabinet_id=world_a["cabinet_a"])

    events_a = await AppointmentService.list_cabinet_events(
        db_session, world_a["clinic_id"], apt_a.id
    )
    assert len(events_a) == 1

    events_b = await AppointmentService.list_cabinet_events(
        db_session, world_b["clinic_id"], apt_a.id
    )
    assert events_b == []


@pytest.mark.asyncio
async def test_delete_cabinet_with_cancelled_history_answers_409(
    client,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    """Only cancelled appointments left still reference the cabinet; the
    DELETE used to fail on the FK with a 500 (#750)."""
    membership = (
        (
            await db_session.execute(
                select(ClinicMembership).where(ClinicMembership.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .first()
    )
    used = Cabinet(id=uuid4(), clinic_id=test_clinic.id, name="Used", color="#000000")
    unused = Cabinet(id=uuid4(), clinic_id=test_clinic.id, name="Unused", color="#ffffff")
    db_session.add_all([used, unused])
    await db_session.flush()
    start = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    db_session.add(
        Appointment(
            clinic_id=test_clinic.id,
            patient_id=test_patient.id,
            professional_id=membership.user_id,
            cabinet_id=used.id,
            cabinet=used.name,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status="cancelled",
        )
    )
    await db_session.commit()

    blocked = await client.delete(f"/api/v1/agenda/cabinets/{used.id}", headers=auth_headers)
    assert blocked.status_code == 409, blocked.text
    assert "deactivate" in blocked.json()["message"]

    deleted = await client.delete(f"/api/v1/agenda/cabinets/{unused.id}", headers=auth_headers)
    assert deleted.status_code == 204, deleted.text
