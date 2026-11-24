"""Reason buffers, quotas and per-contact limits, scoped to the configured professional.

Everything here is synthetic. Only the professional configured in the booking
settings is counted: another professional's appointments, holds and accepted
requests neither block a slot nor use up a quota.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from booking_helpers import appointment, configure, professional, tomorrow_at
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.online_booking.exceptions import BookingConflictError
from app.modules.online_booking.models import BookingRequest, BookingSettings
from app.modules.online_booking.service import LIMIT_REACHED, occupied, reserve, slots

CHECKUP = {
    "id": "checkup",
    "name_es": "Revisión",
    "name_en": "Check-up",
    "duration_minutes": 30,
    "active": True,
}


def reason(**extra) -> dict:
    return {**CHECKUP, **extra}


def request(
    clinic_id,
    at,
    professional_id=None,
    status="pending_confirmation",
    email="s@example.invalid",
    **kw,
) -> BookingRequest:
    return BookingRequest(
        id=uuid4(),
        clinic_id=clinic_id,
        professional_id=professional_id,
        start_time=at,
        end_time=at + timedelta(minutes=30),
        status=status,
        reason="checkup",
        confirmation_deadline=datetime.now(UTC) + timedelta(minutes=10),
        contact_email=email,
        contact_phone="+34600000000",
        **kw,
    )


async def setup(db, clinic_id, **settings):
    """A configured professional, another professional and the settings row."""
    configured = await professional(db, clinic_id)
    other = await professional(db, clinic_id)
    config = await configure(db, clinic_id, configured.id)
    for key, value in settings.items():
        setattr(config, key, value)
    await db.commit()
    return config, configured, other


@pytest.mark.asyncio
async def test_reason_buffers_widen_the_blocked_time(db_session, test_clinic, open_hours):
    now = datetime.now(UTC)
    chosen = reason(buffer_before=15, buffer_after=15)
    config, *_ = await setup(db_session, test_clinic.id, reasons=[chosen])
    await reserve(db_session, test_clinic.id, config, request(test_clinic.id, tomorrow_at(10)), now)
    await db_session.commit()
    available = await slots(
        db_session, test_clinic.id, config, tomorrow_at(10).date(), now, 30, chosen
    )
    assert tomorrow_at(10, 30) not in available
    assert tomorrow_at(9, 30) not in available
    assert tomorrow_at(9) in available
    assert tomorrow_at(11) in available
    assert tomorrow_at(8, 30) in available


@pytest.mark.asyncio
async def test_daily_limit_rejects_the_next_request(db_session, test_clinic, open_hours):
    now = datetime.now(UTC)
    chosen = reason(buffer_before=15, buffer_after=15)
    config, *_ = await setup(db_session, test_clinic.id, reasons=[chosen], daily_limit=1)
    await reserve(db_session, test_clinic.id, config, request(test_clinic.id, tomorrow_at(10)), now)
    await db_session.commit()
    assert (
        await slots(db_session, test_clinic.id, config, tomorrow_at(10).date(), now, 30, chosen)
        == []
    )
    with pytest.raises(BookingConflictError, match=LIMIT_REACHED):
        await reserve(
            db_session, test_clinic.id, config, request(test_clinic.id, tomorrow_at(12)), now
        )


@pytest.mark.parametrize("scope", ["global_week", "reason_day", "reason_week"])
@pytest.mark.asyncio
async def test_global_and_reason_quota(db_session, test_clinic, open_hours, scope):
    now = datetime.now(UTC)
    chosen = reason(
        daily_limit=1 if scope == "reason_day" else None,
        weekly_limit=1 if scope == "reason_week" else None,
    )
    config, *_ = await setup(
        db_session,
        test_clinic.id,
        reasons=[chosen],
        weekly_limit=1 if scope == "global_week" else None,
    )
    await reserve(db_session, test_clinic.id, config, request(test_clinic.id, tomorrow_at(10)), now)
    await db_session.commit()
    with pytest.raises(BookingConflictError, match=LIMIT_REACHED):
        await reserve(
            db_session, test_clinic.id, config, request(test_clinic.id, tomorrow_at(12)), now
        )


@pytest.mark.asyncio
async def test_active_patient_limit_counts_only_the_configured_professional(
    db_session, test_clinic, open_hours
):
    now = datetime.now(UTC)
    config, configured, other = await setup(db_session, test_clinic.id, active_patient_limit=1)
    # The same contact already holds a slot with another professional: not counted.
    db_session.add(request(test_clinic.id, tomorrow_at(8), other.id, email="one@example.invalid"))
    await db_session.commit()
    await reserve(
        db_session,
        test_clinic.id,
        config,
        request(test_clinic.id, tomorrow_at(10), email="one@example.invalid"),
        now,
    )
    await db_session.commit()
    with pytest.raises(BookingConflictError, match="Active request limit"):
        await reserve(
            db_session,
            test_clinic.id,
            config,
            request(test_clinic.id, tomorrow_at(12), email="one@example.invalid"),
            now,
        )


@pytest.mark.asyncio
async def test_quota_ignores_other_professionals_holds_and_accepted_requests(
    db_session, test_clinic, open_hours
):
    now = datetime.now(UTC)
    config, configured, other = await setup(db_session, test_clinic.id, daily_limit=1)
    day = tomorrow_at(10).date()
    db_session.add(request(test_clinic.id, tomorrow_at(8), other.id))
    held_elsewhere = appointment(test_clinic.id, other.id, tomorrow_at(9))
    db_session.add(held_elsewhere)
    await db_session.flush()
    db_session.add(
        request(
            test_clinic.id,
            tomorrow_at(9),
            configured.id,
            status="accepted",
            appointment_id=held_elsewhere.id,
        )
    )
    await db_session.commit()
    # Neither the other professional's hold nor the request reception gave to
    # them uses the configured professional's daily quota.
    assert await slots(db_session, test_clinic.id, config, day, now)
    await reserve(db_session, test_clinic.id, config, request(test_clinic.id, tomorrow_at(12)), now)
    await db_session.commit()
    # Their own hold does.
    assert await slots(db_session, test_clinic.id, config, day, now) == []


@pytest.mark.asyncio
async def test_an_accepted_request_counts_for_the_professional_who_got_the_appointment(
    db_session, test_clinic, open_hours
):
    now = datetime.now(UTC)
    config, configured, other = await setup(db_session, test_clinic.id, daily_limit=1)
    booked = appointment(test_clinic.id, configured.id, tomorrow_at(9))
    db_session.add(booked)
    await db_session.flush()
    db_session.add(
        request(
            test_clinic.id,
            tomorrow_at(9),
            other.id,
            status="accepted",
            appointment_id=booked.id,
        )
    )
    await db_session.commit()
    assert await slots(db_session, test_clinic.id, config, tomorrow_at(9).date(), now) == []


@pytest.mark.asyncio
async def test_accepted_buffer_follows_the_moved_appointment(db_session, test_clinic, open_hours):
    now = datetime.now(UTC)
    config, configured, _ = await setup(db_session, test_clinic.id)
    moved = appointment(test_clinic.id, configured.id, tomorrow_at(12))
    db_session.add(moved)
    await db_session.flush()
    db_session.add(
        request(
            test_clinic.id,
            tomorrow_at(10),
            configured.id,
            status="accepted",
            appointment_id=moved.id,
            buffer_before=15,
            buffer_after=15,
        )
    )
    await db_session.commit()
    available = await slots(db_session, test_clinic.id, config, tomorrow_at(10).date(), now, 30)
    assert tomorrow_at(10) in available
    assert tomorrow_at(11, 30) not in available
    assert tomorrow_at(12, 30) not in available
    assert tomorrow_at(13) in available


@pytest.mark.asyncio
async def test_other_professionals_buffers_and_holds_do_not_block(
    db_session, test_clinic, open_hours
):
    now = datetime.now(UTC)
    config, configured, other = await setup(db_session, test_clinic.id)
    moved = appointment(test_clinic.id, other.id, tomorrow_at(12))
    db_session.add(moved)
    await db_session.flush()
    db_session.add(
        request(
            test_clinic.id,
            tomorrow_at(10),
            other.id,
            status="accepted",
            appointment_id=moved.id,
            buffer_before=15,
            buffer_after=15,
        )
    )
    db_session.add(
        request(test_clinic.id, tomorrow_at(14), other.id, buffer_before=30, buffer_after=30)
    )
    await db_session.commit()
    available = await slots(db_session, test_clinic.id, config, tomorrow_at(10).date(), now, 30)
    for blocked_for_other in (
        tomorrow_at(11, 30),
        tomorrow_at(12),
        tomorrow_at(12, 30),
        tomorrow_at(14),
    ):
        assert blocked_for_other in available
    end = tomorrow_at(12) + timedelta(minutes=30)
    assert not await occupied(
        db_session, test_clinic.id, tomorrow_at(12), end, now, professional_id=configured.id
    )
    assert await occupied(
        db_session, test_clinic.id, tomorrow_at(12), end, now, professional_id=other.id
    )


@pytest.mark.asyncio
async def test_simultaneous_daily_quota_is_atomic(db_session, test_clinic, open_hours):
    from app.config import settings

    await setup(db_session, test_clinic.id, daily_limit=1)
    engine = create_async_engine(settings.DATABASE_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def attempt(hour):
        async with maker() as db:
            cfg = await db.get(BookingSettings, test_clinic.id)
            try:
                await reserve(
                    db,
                    test_clinic.id,
                    cfg,
                    request(test_clinic.id, tomorrow_at(hour), email=f"s{hour}@example.invalid"),
                    datetime.now(UTC),
                )
                await db.commit()
                return "created"
            except BookingConflictError:
                await db.rollback()
                return "limited"

    try:
        assert sorted(await asyncio.gather(attempt(10), attempt(12))) == ["created", "limited"]
    finally:
        await engine.dispose()
