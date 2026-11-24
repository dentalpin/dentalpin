"""Shared fixtures: synthetic availability, seeded templates and a fake mail sink."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio

from app.modules.schedules.services.availability import AvailabilityService, ResolvedRange


@pytest.fixture
def open_hours(monkeypatch):
    async def resolve(db, clinic_id, start, end, professional_id=None):
        return "UTC", [
            ResolvedRange(
                start=datetime.combine(start, time.min, UTC),
                end=datetime.combine(start + timedelta(days=1), time.min, UTC),
                state="open",
            )
        ]

    monkeypatch.setattr(AvailabilityService, "resolve", resolve)


@pytest_asyncio.fixture
async def email_templates(db_session):
    """Seed the system templates the way the module migration does."""
    from app.modules.online_booking.migrations.versions import ob_0003_seed_email_templates as seed

    for row in seed._rows():
        await db_session.execute(seed._INSERT, row)
    await db_session.commit()


@pytest.fixture
def delivery(monkeypatch, email_templates):
    """Capture what the gateway hands to the email service; nothing is sent."""
    from app.core.email.service import email_service

    sent = []

    async def send(message, **kwargs):
        sent.append(message)
        return SimpleNamespace(is_success=True, status="success", provider="test")

    monkeypatch.setattr(email_service, "send", send)
    return sent
