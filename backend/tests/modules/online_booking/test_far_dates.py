"""Days far outside the booking window answer an empty list, not a 500 (#1101)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from booking_helpers import configure, professional

from app.modules.online_booking.service import slots
from app.modules.schedules.services.availability import AvailabilityService


@pytest.mark.asyncio
async def test_public_availability_for_the_max_date_is_empty(client, db_session, test_clinic):
    """Uses the real resolver: the window check must run before it."""
    configured = await professional(db_session, test_clinic.id)
    await configure(db_session, test_clinic.id, configured.id)
    url = f"/api/v1/online_booking/public/{test_clinic.id}/availability"
    response = await client.get(url, params={"day": date.max.isoformat()})
    assert response.status_code == 200
    assert response.json()["data"]["starts"] == []


@pytest.mark.asyncio
async def test_slots_skip_the_resolver_outside_the_window(db_session, test_clinic, monkeypatch):
    configured = await professional(db_session, test_clinic.id)
    config = await configure(db_session, test_clinic.id, configured.id)
    calls = []

    async def resolve(db, clinic_id, start, end, professional_id=None):
        calls.append(start)
        return "UTC", []

    monkeypatch.setattr(AvailabilityService, "resolve", resolve)
    now = datetime.now(UTC)
    for day in (date.min, date.max, now.date() + timedelta(days=config.window_days + 2)):
        assert await slots(db_session, test_clinic.id, config, day, now) == []
    assert calls == []


@pytest.mark.asyncio
async def test_resolver_handles_the_last_representable_day(db_session, test_clinic):
    tz_name, ranges = await AvailabilityService.resolve(
        db_session, test_clinic.id, date.max, date.max
    )
    assert tz_name
    assert all(r.start.date() <= date.max for r in ranges)
