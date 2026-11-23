"""Accepting a booking for a new patient follows the patients surname rule (#1044)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from booking_helpers import professional
from sqlalchemy import func, select

from app.modules.online_booking.models import BookingRequest
from app.modules.patients.models import Patient


async def _confirmed_request(db, clinic_id, professional_id) -> BookingRequest:
    start = datetime.now(UTC) + timedelta(days=1)
    item = BookingRequest(
        id=uuid4(),
        clinic_id=clinic_id,
        professional_id=professional_id,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        status="confirmed",
        reason="checkup",
        confirmation_deadline=datetime.now(UTC),
        contact_name="Cher",
        contact_phone="+34 600 000 000",
    )
    db.add(item)
    await db.commit()
    return item


@pytest.mark.asyncio
async def test_accept_requires_surname_so_the_patient_stays_editable(
    client, db_session, auth_headers, test_clinic
):
    staff = await professional(db_session, test_clinic.id)
    item = await _confirmed_request(db_session, test_clinic.id, staff.id)
    url = f"/api/v1/online_booking/requests/{item.id}/accept"
    headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}
    body = {
        "first_name": "Cher",
        "professional_id": str(staff.id),
        "duration_minutes": 30,
    }

    async def patient_count() -> int:
        return await db_session.scalar(
            select(func.count(Patient.id)).where(Patient.clinic_id == test_clinic.id)
        )

    before = await patient_count()
    for last_name in ("", "   "):
        response = await client.post(url, headers=headers, json={**body, "last_name": last_name})
        assert response.status_code == 422, response.text
    response = await client.post(url, headers=headers, json=body)
    assert response.status_code == 422, response.text
    assert await patient_count() == before
    await db_session.refresh(item)
    assert item.status == "confirmed" and item.patient_id is None

    response = await client.post(url, headers=headers, json={**body, "last_name": "Synthetic"})
    assert response.status_code == 200, response.text
    await db_session.refresh(item)
    patient = await db_session.get(Patient, item.patient_id)
    assert patient.last_name == "Synthetic"

    # The demographics form sends the stored names back with the edited field.
    response = await client.put(
        f"/api/v1/patients/{patient.id}",
        headers=headers,
        json={
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "phone": "+34 600 000 001",
        },
    )
    assert response.status_code == 200, response.text
