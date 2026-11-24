"""Availability and conflicts are scoped to the configured professional (#913)."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from booking_helpers import appointment, configure, professional, proof_for, tomorrow_at
from sqlalchemy import select

from app.modules.agenda.models import Appointment, Cabinet
from app.modules.online_booking.models import BookingRequest
from app.modules.online_booking.service import occupied, slots
from app.modules.schedules.models import (
    ClinicWeeklySchedule,
    ProfessionalWeeklySchedule,
    ScheduleShift,
)
from app.modules.schedules.services.availability import AvailabilityService


@pytest.mark.asyncio
async def test_availability_is_the_configured_professionals_schedule(db_session, test_clinic):
    """Hours come from the ``schedules`` module for the configured professional."""
    configured = await professional(db_session, test_clinic.id)
    other = await professional(db_session, test_clinic.id)
    weekly = ClinicWeeklySchedule(clinic_id=test_clinic.id, is_active=True)
    own = ProfessionalWeeklySchedule(
        clinic_id=test_clinic.id, user_id=configured.id, is_active=True
    )
    db_session.add_all([weekly, own])
    await db_session.flush()
    for weekday in range(7):
        db_session.add(
            ScheduleShift(
                clinic_weekly_id=weekly.id,
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(18, 0),
            )
        )
        db_session.add(
            ScheduleShift(
                professional_weekly_id=own.id,
                weekday=weekday,
                start_time=time(10, 0),
                end_time=time(11, 0),
            )
        )
    config = await configure(db_session, test_clinic.id, configured.id)
    zone = ZoneInfo("Europe/Madrid")
    day = (datetime.now(UTC) + timedelta(days=2)).astimezone(zone).date()
    starts = await slots(db_session, test_clinic.id, config, day, datetime.now(UTC))
    assert [s.astimezone(zone).strftime("%H:%M") for s in starts] == ["10:00", "10:30"]
    # Another professional with no schedule of their own would inherit clinic
    # hours (08-18); the configured one's narrower hours still win.
    config.professional_id = other.id
    starts = await slots(db_session, test_clinic.id, config, day, datetime.now(UTC))
    assert len(starts) == 20


@pytest.mark.asyncio
async def test_resolver_receives_the_configured_professional(db_session, test_clinic, monkeypatch):
    configured = await professional(db_session, test_clinic.id)
    config = await configure(db_session, test_clinic.id, configured.id)
    seen = []

    async def resolve(db, clinic_id, start, end, professional_id=None):
        seen.append(professional_id)
        return "UTC", []

    monkeypatch.setattr(AvailabilityService, "resolve", resolve)
    # A day safely inside the window in any clinic timezone: the window is
    # now checked in the clinic's zone before the resolver runs (#1101).
    day = (datetime.now(UTC) + timedelta(days=1)).date()
    assert await slots(db_session, test_clinic.id, config, day, datetime.now(UTC)) == []
    assert seen == [configured.id]


@pytest.mark.asyncio
async def test_other_professionals_appointments_do_not_block(
    client, db_session, test_clinic, open_hours
):
    """Two professionals with simultaneous appointments: only the configured one blocks."""
    configured = await professional(db_session, test_clinic.id)
    other = await professional(db_session, test_clinic.id)
    config = await configure(db_session, test_clinic.id, configured.id)
    start = tomorrow_at(10)
    db_session.add_all(
        [
            appointment(test_clinic.id, other.id, start),
            appointment(test_clinic.id, configured.id, start + timedelta(hours=1)),
            appointment(test_clinic.id, other.id, start + timedelta(hours=1)),
        ]
    )
    await db_session.commit()
    starts = await slots(db_session, test_clinic.id, config, start.date(), datetime.now(UTC))
    assert start in starts
    assert start + timedelta(hours=1) not in starts
    now = datetime.now(UTC)
    end = start + timedelta(minutes=30)
    assert not await occupied(
        db_session, test_clinic.id, start, end, now, professional_id=configured.id
    )
    assert await occupied(db_session, test_clinic.id, start, end, now, professional_id=other.id)
    response = await client.post(
        f"/api/v1/online_booking/public/{test_clinic.id}/requests",
        json={
            "start_time": start.isoformat(),
            "contact_name": "Synthetic",
            "contact_email": "scope@example.com",
            "contact_phone": "+34600123456",
            "reason": "checkup",
            "altcha": proof_for(test_clinic.id),
        },
    )
    assert response.status_code == 201, response.text
    row = await db_session.scalar(select(BookingRequest))
    assert row.professional_id == configured.id


@pytest.mark.asyncio
async def test_a_hold_blocks_only_its_professional(db_session, test_clinic, open_hours):
    first = await professional(db_session, test_clinic.id)
    second = await professional(db_session, test_clinic.id)
    config = await configure(db_session, test_clinic.id, first.id)
    start = tomorrow_at(11)
    now = datetime.now(UTC)
    db_session.add(
        BookingRequest(
            clinic_id=test_clinic.id,
            professional_id=first.id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status="confirmed",
            reason="checkup",
            confirmation_deadline=now,
        )
    )
    await db_session.commit()
    end = start + timedelta(minutes=30)
    assert await occupied(db_session, test_clinic.id, start, end, now, professional_id=first.id)
    assert not await occupied(
        db_session, test_clinic.id, start, end, now, professional_id=second.id
    )
    assert start not in await slots(db_session, test_clinic.id, config, start.date(), now)
    # The same time is free once booking is configured for the other professional.
    config.professional_id = second.id
    assert start in await slots(db_session, test_clinic.id, config, start.date(), now)


@pytest.mark.asyncio
async def test_accept_rechecks_the_chosen_professional_and_cabinet(
    client, db_session, auth_headers, test_clinic
):
    configured = await professional(db_session, test_clinic.id)
    busy_professional = await professional(db_session, test_clinic.id)
    free_professional = await professional(db_session, test_clinic.id)
    third = await professional(db_session, test_clinic.id)
    busy_cabinet, free_cabinet = (
        Cabinet(
            id=uuid4(),
            clinic_id=test_clinic.id,
            name=f"Room {n}",
            color="#123456",
            display_order=n,
            is_active=True,
        )
        for n in range(2)
    )
    db_session.add_all([busy_cabinet, free_cabinet])
    await configure(db_session, test_clinic.id, configured.id)
    base = tomorrow_at(8)
    now = datetime.now(UTC)

    def held(professional_id, slot: int) -> BookingRequest:
        start = base + timedelta(hours=slot)
        return BookingRequest(
            id=uuid4(),
            clinic_id=test_clinic.id,
            professional_id=professional_id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status="confirmed",
            reason="checkup",
            confirmation_deadline=now,
            contact_email="scope@example.com",
        )

    # Every case has its own hour so one case's hold cannot affect another.
    busy_pro, free_pro, busy_cab, free_cab, clash = (
        held(configured.id, 0),
        held(configured.id, 1),
        held(configured.id, 2),
        held(configured.id, 3),
        held(configured.id, 4),
    )
    # A confirmed hold of another professional at the same hour as free_pro.
    db_session.add_all([busy_pro, free_pro, busy_cab, free_cab, clash, held(third.id, 1)])
    db_session.add_all(
        [
            appointment(test_clinic.id, busy_professional.id, busy_pro.start_time),
            appointment(test_clinic.id, third.id, busy_cab.start_time, cabinet_id=busy_cabinet.id),
            # Another live hold of the professional chosen for ``clash``.
            held(free_professional.id, 4),
        ]
    )
    await db_session.commit()
    headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}

    async def accept(row, professional_id, cabinet_id=None):
        return await client.post(
            f"/api/v1/online_booking/requests/{row.id}/accept",
            headers=headers,
            json={
                "first_name": "Synthetic",
                "last_name": "Person",
                "professional_id": str(professional_id),
                "cabinet_id": str(cabinet_id) if cabinet_id else None,
                "duration_minutes": 30,
            },
        )

    # Switching to a professional who is busy then is rejected ...
    result = await accept(busy_pro, busy_professional.id)
    assert result.status_code == 409, result.text
    # ... switching to one who is free is accepted, although another
    # professional's confirmed hold covers the same time.
    result = await accept(free_pro, free_professional.id)
    assert result.status_code == 200, result.text
    created = await db_session.get(Appointment, free_pro.appointment_id)
    assert created.professional_id == free_professional.id
    # A cabinet in use by another professional's appointment collides ...
    result = await accept(busy_cab, configured.id, busy_cabinet.id)
    assert result.status_code == 409, result.text
    # ... a free cabinet does not.
    result = await accept(free_cab, configured.id, free_cabinet.id)
    assert result.status_code == 200, result.text
    # Another live hold of the chosen professional still blocks.
    result = await accept(clash, free_professional.id)
    assert result.status_code == 409, result.text
    # The request keeps its own professional when that one is chosen.
    result = await accept(clash, configured.id)
    assert result.status_code == 200, result.text
