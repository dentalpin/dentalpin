"""Appointment messages print the clinic's wall-clock time, not UTC.

``Appointment.start_time`` is stored in UTC. The confirmation, cancellation
and reminder messages formatted it with ``strftime`` as stored, so a Madrid
patient booked for 10:00 was told 09:00 (08:00 in summer), and a Mexico City
patient booked for 19:00 on the 14th was told 01:00 on the 15th.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.agenda.models import Appointment
from app.modules.notifications import tasks
from app.modules.notifications.handlers import NotificationHandlers
from app.modules.notifications.models import CommunicationMessage
from app.modules.notifications.service import NotificationService
from app.modules.patients.models import Patient

# 2026-01-15 01:00 UTC is 2026-01-14 19:00 in Mexico City (UTC-6).
START_UTC = datetime(2026, 1, 15, 1, 0, tzinfo=UTC)
LOCAL_DATE, LOCAL_TIME = "14/01/2026", "19:00"


async def _setup(
    db: AsyncSession, clinic: Clinic, patient: Patient, status: str, start: datetime = START_UTC
) -> Appointment:
    clinic.timezone = "America/Mexico_City"
    professional = User(
        email=f"pro-{uuid4().hex[:8]}@test.com",
        password_hash="x",
        first_name="Pro",
        last_name="Fesional",
    )
    db.add(professional)
    await db.flush()
    appointment = Appointment(
        clinic_id=clinic.id,
        patient_id=patient.id,
        professional_id=professional.id,
        start_time=start,
        end_time=start + timedelta(hours=1),
        status=status,
    )
    db.add(appointment)
    await db.commit()
    return appointment


async def _context(db: AsyncSession, clinic_id, template_key: str) -> dict:
    row = (
        await db.execute(
            select(CommunicationMessage).where(
                CommunicationMessage.clinic_id == clinic_id,
                CommunicationMessage.template_key == template_key,
            )
        )
    ).scalar_one()
    return row.context_data


@pytest.mark.asyncio
async def test_confirmation_uses_clinic_time(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    appointment = await _setup(db_session, test_clinic, test_patient, "scheduled")
    await NotificationHandlers.on_appointment_scheduled(
        {"clinic_id": str(test_clinic.id), "appointment_id": str(appointment.id)}, db=db_session
    )
    context = await _context(db_session, test_clinic.id, "appointment_confirmation")
    assert (context["appointment_date"], context["appointment_time"]) == (LOCAL_DATE, LOCAL_TIME)


@pytest.mark.asyncio
async def test_cancellation_uses_clinic_time(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    appointment = await _setup(db_session, test_clinic, test_patient, "cancelled")
    await NotificationHandlers.on_appointment_cancelled(
        {"clinic_id": str(test_clinic.id), "appointment_id": str(appointment.id)}, db=db_session
    )
    context = await _context(db_session, test_clinic.id, "appointment_cancelled")
    assert (context["appointment_date"], context["appointment_time"]) == (LOCAL_DATE, LOCAL_TIME)


@pytest.mark.asyncio
async def test_single_reminder_uses_clinic_time(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    appointment = await _setup(db_session, test_clinic, test_patient, "scheduled")
    clinic_id = test_clinic.id

    @asynccontextmanager
    async def _session():
        yield db_session

    with patch.object(tasks, "async_session_maker", _session):
        assert await tasks.send_single_reminder(appointment.id, clinic_id)
    context = await _context(db_session, clinic_id, "appointment_reminder")
    assert (context["appointment_date"], context["appointment_time"]) == (LOCAL_DATE, LOCAL_TIME)


@pytest.mark.asyncio
async def test_scheduled_reminder_uses_clinic_time(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    start = (datetime.now(UTC) + timedelta(hours=3)).replace(second=0, microsecond=0)
    await _setup(db_session, test_clinic, test_patient, "scheduled", start)
    clinic_id = test_clinic.id
    await NotificationService.get_or_create_clinic_settings(db_session, clinic_id)
    await db_session.commit()

    @asynccontextmanager
    async def _session():
        yield db_session

    with patch.object(tasks, "async_session_maker", _session):
        await tasks.process_appointment_reminders()
    local = start.astimezone(ZoneInfo("America/Mexico_City"))
    context = await _context(db_session, clinic_id, "appointment_reminder")
    assert (context["appointment_date"], context["appointment_time"]) == (
        local.strftime("%d/%m/%Y"),
        local.strftime("%H:%M"),
    )


@pytest.mark.asyncio
async def test_manual_send_uses_clinic_time(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
):
    appointment = await _setup(db_session, test_clinic, test_patient, "scheduled")
    clinic_id, patient_id, appointment_id = test_clinic.id, test_patient.id, appointment.id
    response = await client.post(
        "/api/v1/notifications/send",
        json={
            "notification_type": "appointment_reminder",
            "patient_id": str(patient_id),
            "appointment_id": str(appointment_id),
        },
        headers=auth_headers,
    )
    assert response.status_code in (200, 201), response.text
    context = await _context(db_session, clinic_id, "appointment_reminder")
    assert (context["appointment_date"], context["appointment_time"]) == (LOCAL_DATE, LOCAL_TIME)
