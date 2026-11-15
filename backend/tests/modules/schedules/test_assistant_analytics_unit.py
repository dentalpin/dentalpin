"""Assistant capacity/conflict calculations without PostgreSQL fixtures."""

from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.schedules.services import AnalyticsService
from app.modules.schedules.services.availability import AvailabilityService, ResolvedRange
from app.modules.schedules.services.professional_hours import ProfessionalHoursService


class _AppointmentRows:
    def __init__(self, appointments):
        self.appointments = appointments

    def scalars(self):
        return self

    def all(self):
        return self.appointments


@pytest.mark.asyncio
async def test_assistant_load_separates_double_bookings_and_out_of_shift_records():
    assistant_id = uuid4()
    day = date(2026, 11, 16)
    open_range = ResolvedRange(
        start=datetime.combine(day, time(9), tzinfo=UTC),
        end=datetime.combine(day, time(13), tzinfo=UTC),
        state="open",
        professional_id=assistant_id,
    )
    appointments = [
        SimpleNamespace(
            id=uuid4(),
            start_time=datetime(2026, 11, 16, 9, 30, tzinfo=UTC),
            end_time=datetime(2026, 11, 16, 10, 0, tzinfo=UTC),
            status="scheduled",
        ),
        SimpleNamespace(
            id=uuid4(),
            start_time=datetime(2026, 11, 16, 9, 45, tzinfo=UTC),
            end_time=datetime(2026, 11, 16, 10, 15, tzinfo=UTC),
            status="confirmed",
        ),
        SimpleNamespace(
            id=uuid4(),
            start_time=datetime(2026, 11, 16, 14, 0, tzinfo=UTC),
            end_time=datetime(2026, 11, 16, 14, 30, tzinfo=UTC),
            status="scheduled",
        ),
    ]
    db = SimpleNamespace(execute=AsyncMock(return_value=_AppointmentRows(appointments)))

    with (
        patch.object(
            ProfessionalHoursService,
            "list_assistants",
            new=AsyncMock(
                return_value=[{"user_id": assistant_id, "first_name": "A", "last_name": "B"}]
            ),
        ),
        patch.object(
            AvailabilityService,
            "resolve",
            new=AsyncMock(return_value=("UTC", [open_range])),
        ),
    ):
        data = await AnalyticsService.assistant_workload(db, uuid4(), day, day)

    row = data["rows"][0]
    assert row["appointment_count"] == 3
    assert row["booked_minutes"] == 90
    assert row["available_minutes"] == 240
    assert row["utilization_rate"] == 0.375
    assert row["conflict_count"] == 2
    assert {conflict["kind"] for conflict in data["conflicts"]} == {"overlap", "outside_shift"}
