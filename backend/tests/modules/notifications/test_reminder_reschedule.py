"""A rescheduled appointment gets a reminder for its new time (#1035)."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
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


@pytest.mark.asyncio
async def test_one_reminder_per_start_time(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient, monkeypatch
):
    dentist = User(
        email=f"d-{uuid4().hex[:8]}@test.clinic", password_hash="x", first_name="D", last_name="E"
    )
    db_session.add(dentist)
    await db_session.flush()
    db_session.add(ClinicMembership(user_id=dentist.id, clinic_id=test_clinic.id, role="dentist"))
    db_session.add(
        NotificationTemplate(
            clinic_id=test_clinic.id,
            channel="email",
            template_key="appointment_reminder",
            locale="es",
            subject="Recordatorio",
            body_html="<p>{{patient_name}}</p>",
            is_system=False,
        )
    )
    existing = await db_session.scalar(
        select(ClinicNotificationSettings).where(
            ClinicNotificationSettings.clinic_id == test_clinic.id
        )
    )
    config = {"appointment_reminder": {"enabled": True, "auto_send": True, "hours_before": 24}}
    if existing:
        existing.settings = config
    else:
        db_session.add(ClinicNotificationSettings(clinic_id=test_clinic.id, settings=config))
    start = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=3)
    visit = await AppointmentService.create_appointment(
        db_session,
        test_clinic.id,
        {
            "patient_id": test_patient.id,
            "professional_id": dentist.id,
            "start_time": start,
            "end_time": start + timedelta(minutes=30),
        },
    )
    await db_session.commit()
    visit_id, clinic_id = visit.id, test_clinic.id

    @asynccontextmanager
    async def session():
        yield db_session

    monkeypatch.setattr(tasks, "async_session_maker", session)

    async def reminded_for() -> list[str]:
        rows = await db_session.scalars(
            select(CommunicationMessage)
            .where(
                CommunicationMessage.clinic_id == clinic_id,
                CommunicationMessage.template_key == "appointment_reminder",
            )
            .order_by(CommunicationMessage.created_at)
        )
        return [row.context_data["appointment_start_at"] for row in rows]

    await tasks.process_appointment_reminders()
    await tasks.process_appointment_reminders()
    assert len(await reminded_for()) == 1

    moved = start + timedelta(hours=5)
    visit.start_time, visit.end_time = moved, moved + timedelta(minutes=30)
    await db_session.commit()
    await tasks.process_appointment_reminders()
    await tasks.process_appointment_reminders()
    assert await tasks.send_single_reminder(visit_id, clinic_id) is False  # already reminded

    sent_for = await reminded_for()
    assert [datetime.fromisoformat(value) for value in sent_for] == [start, moved]
