"""A reminder sent by hand carries the check-in link (#1156).

The sweep puts a day-valid ``checkin_url`` into every reminder (ADR 0037).
``POST /notifications/send`` built its own context without it, so a reminder
sent from the appointment modal had no "I'm here" link and a provider
template declaring ``checkin_url`` got no value.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.models import Clinic, User
from app.modules.agenda.checkin import verify_checkin_token
from app.modules.agenda.models import Appointment
from app.modules.notifications.models import CommunicationMessage
from app.modules.patients.models import Patient


async def _send(client: AsyncClient, auth_headers: dict, notification_type: str, apt_id) -> None:
    response = await client.post(
        "/api/v1/notifications/send",
        json={"notification_type": notification_type, "appointment_id": str(apt_id)},
        headers=auth_headers,
    )
    assert response.status_code in (200, 201), response.text


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


async def _appointment(db: AsyncSession, clinic: Clinic, patient: Patient) -> Appointment:
    patient.email = "pat@example.com"
    professional = User(
        email=f"pro-{uuid4().hex[:8]}@test.com", password_hash="x", first_name="P", last_name="F"
    )
    db.add(professional)
    await db.flush()
    start = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=3)
    appointment = Appointment(
        clinic_id=clinic.id,
        patient_id=patient.id,
        professional_id=professional.id,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        status="scheduled",
    )
    db.add(appointment)
    await db.commit()
    return appointment


@pytest.mark.asyncio
async def test_manual_reminder_has_checkin_link(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://clinic.example")
    appointment = await _appointment(db_session, test_clinic, test_patient)
    clinic_id, apt_id = test_clinic.id, appointment.id

    await _send(client, auth_headers, "appointment_reminder", apt_id)

    url = (await _context(db_session, clinic_id, "appointment_reminder")).get("checkin_url")
    assert url and url.startswith("https://clinic.example/p/check-in/"), url
    token_apt, token_clinic, source = verify_checkin_token(url.rsplit("/", 1)[1])
    assert (token_apt, token_clinic, source) == (apt_id, clinic_id, "reminder")


@pytest.mark.asyncio
async def test_manual_confirmation_has_no_checkin_link(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the reminder carries the link; a confirmation is sent days ahead."""
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://clinic.example")
    appointment = await _appointment(db_session, test_clinic, test_patient)
    clinic_id, apt_id = test_clinic.id, appointment.id

    await _send(client, auth_headers, "appointment_confirmation", apt_id)

    assert "checkin_url" not in await _context(db_session, clinic_id, "appointment_confirmation")
