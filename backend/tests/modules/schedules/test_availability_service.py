"""Unit tests for the availability resolver."""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.schedules.models import (
    ClinicOverride,
    ClinicWeeklySchedule,
    ProfessionalOverride,
    ProfessionalWeeklySchedule,
    ScheduleShift,
)
from app.modules.schedules.services.availability import AvailabilityService


@pytest.mark.asyncio
async def test_resolve_weekly_only(db_session: AsyncSession, test_clinic: Clinic):
    """Clinic weekly 09–14 on Monday yields one open range + closed gaps."""
    weekly = ClinicWeeklySchedule(clinic_id=test_clinic.id, is_active=True)
    db_session.add(weekly)
    await db_session.flush()
    db_session.add(
        ScheduleShift(
            clinic_weekly_id=weekly.id,
            weekday=0,  # Monday
            start_time=time(9, 0),
            end_time=time(14, 0),
        )
    )
    await db_session.commit()

    # 2026-04-27 is a Monday.
    timezone, ranges = await AvailabilityService.resolve(
        db_session, test_clinic.id, date(2026, 4, 27), date(2026, 4, 27)
    )
    assert timezone == "Europe/Madrid"
    open_ranges = [r for r in ranges if r.state == "open"]
    assert len(open_ranges) == 1
    assert open_ranges[0].start.hour == 9
    assert open_ranges[0].end.hour == 14


@pytest.mark.asyncio
async def test_resolve_clinic_closed_override(db_session: AsyncSession, test_clinic: Clinic):
    """Override kind='closed' wins over weekly template."""
    weekly = ClinicWeeklySchedule(clinic_id=test_clinic.id, is_active=True)
    db_session.add(weekly)
    await db_session.flush()
    db_session.add(
        ScheduleShift(
            clinic_weekly_id=weekly.id,
            weekday=0,
            start_time=time(9, 0),
            end_time=time(14, 0),
        )
    )
    db_session.add(
        ClinicOverride(
            clinic_id=test_clinic.id,
            start_date=date(2026, 4, 27),
            end_date=date(2026, 4, 27),
            kind="closed",
            reason="Holiday",
        )
    )
    await db_session.commit()

    _, ranges = await AvailabilityService.resolve(
        db_session, test_clinic.id, date(2026, 4, 27), date(2026, 4, 27)
    )
    assert all(r.state == "clinic_closed" for r in ranges)
    assert any(r.reason == "Holiday" for r in ranges)


@pytest.mark.asyncio
async def test_resolve_professional_intersects_clinic(
    db_session: AsyncSession, test_clinic: Clinic, dentist_user: User
):
    """Professional 10–12 inside clinic 09–14 yields 10–12 open for that pro."""
    weekly = ClinicWeeklySchedule(clinic_id=test_clinic.id, is_active=True)
    db_session.add(weekly)
    await db_session.flush()
    db_session.add(
        ScheduleShift(
            clinic_weekly_id=weekly.id,
            weekday=0,
            start_time=time(9, 0),
            end_time=time(14, 0),
        )
    )

    pro_weekly = ProfessionalWeeklySchedule(
        clinic_id=test_clinic.id, user_id=dentist_user.id, is_active=True
    )
    db_session.add(pro_weekly)
    await db_session.flush()
    db_session.add(
        ScheduleShift(
            professional_weekly_id=pro_weekly.id,
            weekday=0,
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
    )
    await db_session.commit()

    _, ranges = await AvailabilityService.resolve(
        db_session, test_clinic.id, date(2026, 4, 27), date(2026, 4, 27), dentist_user.id
    )
    open_ranges = [r for r in ranges if r.state == "open"]
    assert len(open_ranges) == 1
    assert open_ranges[0].start.hour == 10
    assert open_ranges[0].end.hour == 12
    assert open_ranges[0].professional_id == dentist_user.id


@pytest.mark.asyncio
async def test_professional_override_unavailable(
    db_session: AsyncSession, test_clinic: Clinic, dentist_user: User
):
    """A professional override 'unavailable' makes the whole day off for that pro."""
    weekly = ClinicWeeklySchedule(clinic_id=test_clinic.id, is_active=True)
    db_session.add(weekly)
    await db_session.flush()
    db_session.add(
        ScheduleShift(
            clinic_weekly_id=weekly.id,
            weekday=0,
            start_time=time(9, 0),
            end_time=time(14, 0),
        )
    )

    db_session.add(
        ProfessionalOverride(
            clinic_id=test_clinic.id,
            user_id=dentist_user.id,
            start_date=date(2026, 4, 27),
            end_date=date(2026, 4, 27),
            kind="unavailable",
            reason="Vacation",
        )
    )
    await db_session.commit()

    _, ranges = await AvailabilityService.resolve(
        db_session, test_clinic.id, date(2026, 4, 27), date(2026, 4, 27), dentist_user.id
    )
    assert all(r.state == "professional_off" for r in ranges)
    assert any(r.reason == "Vacation" for r in ranges)


@pytest.mark.asyncio
async def test_overlapping_shifts_resolve_as_one_open_span(
    db_session: AsyncSession, test_clinic: Clinic
):
    """A shift inside another no longer reports the day closed from its end
    (#991): 09–18 plus 10–12 used to yield "closed from 12:00" on top of
    the open 09–18, and the analytics summed both open ranges."""
    weekly = ClinicWeeklySchedule(clinic_id=test_clinic.id, is_active=True)
    db_session.add(weekly)
    await db_session.flush()
    for start, end in ((time(9, 0), time(18, 0)), (time(10, 0), time(12, 0))):
        db_session.add(
            ScheduleShift(clinic_weekly_id=weekly.id, weekday=0, start_time=start, end_time=end)
        )
    await db_session.commit()

    _, ranges = await AvailabilityService.resolve(
        db_session, test_clinic.id, date(2026, 4, 27), date(2026, 4, 27)
    )
    spans = [(r.state, r.start.time(), r.end.time()) for r in ranges]
    assert [s for s in spans if s[0] == "open"] == [("open", time(9, 0), time(18, 0))]
    closed = [s for s in spans if s[0] == "clinic_closed"]
    assert all(end <= time(9, 0) or start >= time(18, 0) for _, start, end in closed), spans
