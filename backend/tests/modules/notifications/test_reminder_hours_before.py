"""Reminder lead time is validated on save, and one clinic can't stop the job (#1243)."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.modules.agenda.service import AppointmentService
from app.modules.notifications import tasks
from app.modules.notifications.models import (
    ClinicNotificationSettings,
    CommunicationMessage,
    NotificationTemplate,
)
from app.modules.patients.models import Patient

URL = "/api/v1/notifications/settings"


def _reminder(**overrides) -> dict:
    return {"appointment_reminder": {"enabled": True, "auto_send": True, **overrides}}


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, "24", 0, -5, 169, 2.5, True])
async def test_put_rejects_invalid_hours_before(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, bad
):
    response = await client.put(
        URL, json={"settings": _reminder(hours_before=bad)}, headers=auth_headers
    )
    assert response.status_code == 422, response.text

    stored = (await client.get(URL, headers=auth_headers)).json()["data"]["settings"]
    assert stored["appointment_reminder"]["hours_before"] == 24


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, "yes", 1])
async def test_put_rejects_invalid_switches(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, bad
):
    response = await client.put(
        URL, json={"settings": {"welcome": {"enabled": bad}}}, headers=auth_headers
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_put_rejects_non_object_type_entry(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    response = await client.put(
        URL, json={"settings": {"appointment_reminder": 24}}, headers=auth_headers
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("hours", [1, 48, 168])
async def test_put_accepts_valid_hours_before_and_keeps_partial_merge(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, hours: int
):
    response = await client.put(
        URL, json={"settings": _reminder(hours_before=hours)}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["settings"]["appointment_reminder"]["hours_before"] == hours

    # A partial entry doesn't reset the keys it leaves out to the schema defaults.
    response = await client.put(
        URL,
        json={"settings": {"appointment_reminder": {"auto_send": False}}},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    reminder = response.json()["data"]["settings"]["appointment_reminder"]
    assert reminder == {"enabled": True, "auto_send": False, "hours_before": hours}


async def _clinic_with_due_visit(db: AsyncSession, clinic: Clinic, config: dict) -> None:
    """Give ``clinic`` a reminder template, settings ``config`` and a visit in 3 h."""
    dentist = User(
        email=f"d-{uuid4().hex[:8]}@test.clinic", password_hash="x", first_name="D", last_name="E"
    )
    db.add(dentist)
    await db.flush()
    db.add(ClinicMembership(user_id=dentist.id, clinic_id=clinic.id, role="dentist"))
    patient = Patient(
        id=uuid4(), clinic_id=clinic.id, first_name="P", last_name="Q", email="p@example.com"
    )
    db.add(patient)
    db.add(
        NotificationTemplate(
            clinic_id=clinic.id,
            channel="email",
            template_key="appointment_reminder",
            locale="es",
            subject="Recordatorio",
            body_html="<p>{{patient_name}}</p>",
            is_system=False,
        )
    )
    existing = await db.scalar(
        select(ClinicNotificationSettings).where(ClinicNotificationSettings.clinic_id == clinic.id)
    )
    if existing:
        existing.settings = config
    else:
        db.add(ClinicNotificationSettings(clinic_id=clinic.id, settings=config))
    await db.flush()
    start = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=3)
    await AppointmentService.create_appointment(
        db,
        clinic.id,
        {
            "patient_id": patient.id,
            "professional_id": dentist.id,
            "start_time": start,
            "end_time": start + timedelta(minutes=30),
        },
    )
    await db.commit()


async def _reminders(db: AsyncSession, clinic_id) -> int:
    rows = await db.scalars(
        select(CommunicationMessage).where(
            CommunicationMessage.clinic_id == clinic_id,
            CommunicationMessage.template_key == "appointment_reminder",
        )
    )
    return len(rows.all())


async def _run_job(db: AsyncSession, monkeypatch) -> None:
    @asynccontextmanager
    async def session():
        yield db

    monkeypatch.setattr(tasks, "async_session_maker", session)
    await tasks.process_appointment_reminders()


async def _two_clinics(
    db: AsyncSession, bad_config: dict, bad_first: bool
) -> tuple[Clinic, Clinic]:
    """A clinic with ``bad_config`` and a well-configured one, both with a due visit.

    The job walks clinics by ``clinic_id``; ``bad_first`` picks the ids (and
    the insert order, which is the heap order on unfixed code) so the bad
    clinic is reached before or after the good one.
    """
    low, high = sorted([uuid4(), uuid4()])
    bad_id, good_id = (low, high) if bad_first else (high, low)
    clinics = {
        bad_id: (Clinic(id=bad_id, name="Bad", tax_id="B0", address={}, settings={}), bad_config),
        good_id: (
            Clinic(id=good_id, name="Good", tax_id="B1", address={}, settings={}),
            _reminder(hours_before=24),
        ),
    }
    for clinic_id in (low, high):
        clinic, config = clinics[clinic_id]
        db.add(clinic)
        await db.flush()
        await _clinic_with_due_visit(db, clinic, config)
    return clinics[bad_id][0], clinics[good_id][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_first", [True, False], ids=["bad_first", "good_first"])
@pytest.mark.parametrize("bad", [None, "24x", "", 0, -5, 0.5, [24], True])
async def test_stored_bad_hours_before_skips_only_that_clinic(
    db_session: AsyncSession, test_clinic: Clinic, monkeypatch, bad, bad_first: bool
):
    # A row saved before the PUT validated the value.
    bad_clinic, good_clinic = await _two_clinics(db_session, _reminder(hours_before=bad), bad_first)
    bad_id, good_id = bad_clinic.id, good_clinic.id

    await _run_job(db_session, monkeypatch)

    assert await _reminders(db_session, good_id) == 1
    assert await _reminders(db_session, bad_id) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [12.5, "24", " 6 ", 200])
async def test_stored_legacy_hours_before_that_worked_still_reminds(
    db_session: AsyncSession, test_clinic: Clinic, monkeypatch, legacy
):
    # The old page saved Number(v) and the API took any value; these built a
    # valid window before #1243 and must keep sending (visit is 3 h away).
    clinic, other = await _two_clinics(db_session, _reminder(hours_before=legacy), True)
    clinic_id, other_id = clinic.id, other.id

    await _run_job(db_session, monkeypatch)

    assert await _reminders(db_session, clinic_id) == 1
    assert await _reminders(db_session, other_id) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_first", [True, False], ids=["bad_first", "good_first"])
async def test_one_clinic_failing_does_not_stop_the_others(
    db_session: AsyncSession, test_clinic: Clinic, monkeypatch, bad_first: bool
):
    bad_clinic, good_clinic = await _two_clinics(db_session, _reminder(hours_before=24), bad_first)
    bad_id, good_id = bad_clinic.id, good_clinic.id

    real = tasks.appointment_when_context

    def explode_for_bad_clinic(start, clinic, locale):
        if clinic is not None and clinic.id == bad_id:
            raise RuntimeError("broken clinic data")
        return real(start, clinic, locale)

    monkeypatch.setattr(tasks, "appointment_when_context", explode_for_bad_clinic)

    await _run_job(db_session, monkeypatch)

    assert await _reminders(db_session, good_id) == 1
    assert await _reminders(db_session, bad_id) == 0
