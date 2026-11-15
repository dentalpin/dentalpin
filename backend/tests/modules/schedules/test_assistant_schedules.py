"""Assistant shift management, resolved availability and workload reports."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.agenda.models import Appointment
from app.modules.patients.models import Patient
from app.modules.schedules.models import (
    ClinicWeeklySchedule,
    ProfessionalWeeklySchedule,
    ScheduleShift,
)
from app.modules.schedules.services import AnalyticsService


@pytest.fixture
async def assistant_user(db_session: AsyncSession, test_clinic) -> User:
    user = User(
        id=uuid4(),
        email=f"assistant-{uuid4().hex[:8]}@example.test",
        password_hash=hash_password("AssistantPass1234"),
        first_name="Ana",
        last_name="Assistant",
        is_active=True,
        token_version=0,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=test_clinic.id, role="assistant")
    )
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_assistant_weekly_shift_controls_resolved_availability(
    client: AsyncClient, auth_headers: dict, test_clinic, assistant_user: User
):
    await client.put(
        "/api/v1/schedules/clinic-hours",
        headers=auth_headers,
        json={"days": [{"weekday": 0, "shifts": [{"start_time": "08:00", "end_time": "18:00"}]}]},
    )
    saved = await client.put(
        f"/api/v1/schedules/assistants/{assistant_user.id}/hours",
        headers=auth_headers,
        json={"days": [{"weekday": 0, "shifts": [{"start_time": "09:00", "end_time": "13:00"}]}]},
    )
    assert saved.status_code == 200, saved.text

    availability = await client.get(
        "/api/v1/schedules/availability?start=2026-11-16&end=2026-11-16"
        f"&assistant_id={assistant_user.id}",
        headers=auth_headers,
    )
    assert availability.status_code == 200, availability.text
    ranges = availability.json()["data"]["ranges"]
    open_ranges = [row for row in ranges if row["state"] == "open"]
    assert len(open_ranges) == 1
    assert open_ranges[0]["assistant_id"] == str(assistant_user.id)


@pytest.mark.asyncio
async def test_assistant_override_and_workload_report(
    client: AsyncClient, auth_headers: dict, test_clinic, assistant_user: User
):
    override = await client.post(
        f"/api/v1/schedules/assistants/{assistant_user.id}/overrides",
        headers=auth_headers,
        json={
            "start_date": "2026-11-16",
            "end_date": "2026-11-16",
            "kind": "unavailable",
            "reason": "Обучение",
            "shifts": [],
        },
    )
    assert override.status_code == 201, override.text

    report = await client.get(
        "/api/v1/schedules/analytics/assistant-workload?start=2026-11-16&end=2026-11-16",
        headers=auth_headers,
    )
    assert report.status_code == 200, report.text
    data = report.json()["data"]
    row = next(item for item in data["rows"] if item["assistant_id"] == str(assistant_user.id))
    assert row["appointment_count"] == 0
    assert row["conflict_count"] == 0
    assert data["conflicts"] == []

    availability = await client.get(
        "/api/v1/schedules/availability?start=2026-11-16&end=2026-11-16"
        f"&assistant_id={assistant_user.id}",
        headers=auth_headers,
    )
    assert availability.status_code == 200
    assert all(r["state"] != "open" for r in availability.json()["data"]["ranges"])


@pytest.mark.asyncio
async def test_workload_reports_overlaps_and_appointments_outside_assistant_shift(
    db_session: AsyncSession, test_clinic, assistant_user: User
):
    clinic_hours = ClinicWeeklySchedule(clinic_id=test_clinic.id, is_active=True)
    assistant_hours = ProfessionalWeeklySchedule(
        clinic_id=test_clinic.id, user_id=assistant_user.id, is_active=True
    )
    db_session.add_all([clinic_hours, assistant_hours])
    await db_session.flush()
    db_session.add_all(
        [
            ScheduleShift(
                clinic_weekly_id=clinic_hours.id,
                weekday=0,
                start_time=time(8),
                end_time=time(18),
            ),
            ScheduleShift(
                professional_weekly_id=assistant_hours.id,
                weekday=0,
                start_time=time(9),
                end_time=time(13),
            ),
        ]
    )
    patient = Patient(
        clinic_id=test_clinic.id,
        first_name="Schedule",
        last_name="Test",
        phone="+34911111111",
    )
    db_session.add(patient)
    await db_session.flush()
    for start, finish in (
        (datetime(2026, 11, 16, 8, 30, tzinfo=UTC), datetime(2026, 11, 16, 9, 0, tzinfo=UTC)),
        (datetime(2026, 11, 16, 8, 45, tzinfo=UTC), datetime(2026, 11, 16, 9, 45, tzinfo=UTC)),
        (datetime(2026, 11, 16, 16, 0, tzinfo=UTC), datetime(2026, 11, 16, 16, 30, tzinfo=UTC)),
    ):
        db_session.add(
            Appointment(
                clinic_id=test_clinic.id,
                patient_id=patient.id,
                professional_id=assistant_user.id,
                assistant_id=assistant_user.id,
                start_time=start,
                end_time=finish,
                status="scheduled",
            )
        )
    await db_session.commit()

    report = await AnalyticsService.assistant_workload(
        db_session, test_clinic.id, date(2026, 11, 16), date(2026, 11, 16)
    )
    row = next(r for r in report["rows"] if r["assistant_id"] == assistant_user.id)
    assert row["appointment_count"] == 3
    assert row["booked_minutes"] == 120
    assert row["available_minutes"] == 240
    assert row["conflict_count"] == 2
    assert {c["kind"] for c in report["conflicts"]} == {"overlap", "outside_shift"}
