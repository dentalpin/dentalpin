"""``find_free_slots`` never offers time that has already passed (#1008)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.schedules import tools
from app.modules.schedules.services.availability import AvailabilityService


@pytest.mark.asyncio
async def test_windows_start_from_now(db_session: AsyncSession, test_clinic: Clinic, monkeypatch):
    now = datetime.now(UTC)
    over = (now - timedelta(hours=7), now - timedelta(hours=3))
    running = (now - timedelta(hours=2), now + timedelta(hours=3))
    nearly_over = (now - timedelta(hours=1), now + timedelta(minutes=10))
    later = (now + timedelta(hours=4), now + timedelta(hours=6))

    async def resolve(db, clinic_id, start, end, professional_id=None):
        return "UTC", [
            SimpleNamespace(start=s, end=e, state="open")
            for s, e in (over, running, nearly_over, later)
        ]

    monkeypatch.setattr(AvailabilityService, "resolve", staticmethod(resolve))
    result = await tools._find_free_slots(
        SimpleNamespace(db=db_session, clinic_id=test_clinic.id),
        tools.FreeSlotsArgs(professional_id=uuid4(), slot_minutes=30),
    )
    windows = [(w["start"], w["end"]) for w in result["free_windows"]]
    assert len(windows) == 2, windows
    first, second = windows
    assert now <= first[0] <= now + timedelta(minutes=2)
    assert first[0].second == first[0].microsecond == 0
    assert first[1] == running[1]
    assert second == later
