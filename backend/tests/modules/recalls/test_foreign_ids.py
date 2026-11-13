"""A recall only references this clinic's professionals and this patient's
appointments.

``linked_appointment_id`` and ``assigned_professional_id`` are plain FKs. An
unknown id was a 500 (ForeignKeyViolation). Another clinic's id was stored.
Another patient's appointment was stored too, and completing that visit
closed this patient's recall (``on_appointment_completed``).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.patients.models import Patient


async def _user(db: AsyncSession, clinic_id, role: str) -> str:
    user = User(
        email=f"{role}-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Ada",
        last_name="Lovelace",
    )
    db.add(user)
    await db.flush()
    db.add(ClinicMembership(user_id=user.id, clinic_id=clinic_id, role=role))
    await db.commit()
    return str(user.id)


@pytest_asyncio.fixture
async def dentist_id(db_session: AsyncSession, test_clinic: Clinic) -> str:
    return await _user(db_session, test_clinic.id, "dentist")


@pytest_asyncio.fixture
async def other_clinic_dentist_id(db_session: AsyncSession) -> str:
    other = Clinic(id=uuid4(), name="Other", tax_id="B87654321")
    db_session.add(other)
    await db_session.flush()
    return await _user(db_session, other.id, "dentist")


@pytest_asyncio.fixture
async def recall_id(client: AsyncClient, auth_headers: dict, test_patient: Patient) -> str:
    r = await client.post(
        "/api/v1/recalls/",
        headers=auth_headers,
        json={"patient_id": str(test_patient.id), "due_month": "2026-08-01", "reason": "hygiene"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def _appointment(client: AsyncClient, headers: dict, patient_id: str, dentist_id: str) -> str:
    r = await client.post(
        "/api/v1/agenda/appointments",
        headers=headers,
        json={
            "patient_id": patient_id,
            "professional_id": dentist_id,
            "cabinet": "Gabinete 1",
            "start_time": "2026-09-10T09:00:00Z",
            "end_time": "2026-09-10T09:30:00Z",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


@pytest_asyncio.fixture
async def other_patients_appointment(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic, dentist_id
) -> str:
    other = Patient(id=uuid4(), clinic_id=test_clinic.id, first_name="Other", last_name="Person")
    db_session.add(other)
    await db_session.commit()
    return await _appointment(client, auth_headers, str(other.id), dentist_id)


@pytest.mark.asyncio
async def test_link_rejects_an_unknown_appointment(
    client: AsyncClient, auth_headers: dict, recall_id: str
) -> None:
    r = await client.post(
        f"/api/v1/recalls/{recall_id}/link-appointment",
        headers=auth_headers,
        json={"appointment_id": str(uuid4())},
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_link_rejects_another_patients_appointment(
    client: AsyncClient, auth_headers: dict, recall_id: str, other_patients_appointment: str
) -> None:
    r = await client.post(
        f"/api/v1/recalls/{recall_id}/link-appointment",
        headers=auth_headers,
        json={"appointment_id": other_patients_appointment},
    )
    assert r.status_code == 400, r.text
    detail = await client.get(f"/api/v1/recalls/{recall_id}", headers=auth_headers)
    assert detail.json()["data"]["linked_appointment_id"] is None


@pytest.mark.asyncio
async def test_attempt_rejects_another_patients_appointment(
    client: AsyncClient, auth_headers: dict, recall_id: str, other_patients_appointment: str
) -> None:
    r = await client.post(
        f"/api/v1/recalls/{recall_id}/attempts",
        headers=auth_headers,
        json={
            "channel": "phone",
            "outcome": "scheduled",
            "linked_appointment_id": other_patients_appointment,
        },
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_link_accepts_the_patients_own_appointment(
    client: AsyncClient,
    auth_headers: dict,
    recall_id: str,
    test_patient: Patient,
    dentist_id: str,
) -> None:
    own = await _appointment(client, auth_headers, str(test_patient.id), dentist_id)
    r = await client.post(
        f"/api/v1/recalls/{recall_id}/link-appointment",
        headers=auth_headers,
        json={"appointment_id": own},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["linked_appointment_id"] == own


@pytest.mark.asyncio
@pytest.mark.parametrize("which", ["unknown", "other_clinic"])
async def test_professional_must_belong_to_the_clinic(
    client: AsyncClient,
    auth_headers: dict,
    test_patient: Patient,
    recall_id: str,
    other_clinic_dentist_id: str,
    which: str,
) -> None:
    professional = str(uuid4()) if which == "unknown" else other_clinic_dentist_id

    created = await client.post(
        "/api/v1/recalls/",
        headers=auth_headers,
        json={
            "patient_id": str(test_patient.id),
            "due_month": "2026-10-01",
            "reason": "checkup",
            "assigned_professional_id": professional,
        },
    )
    assert created.status_code == 400, created.text

    patched = await client.patch(
        f"/api/v1/recalls/{recall_id}",
        headers=auth_headers,
        json={"assigned_professional_id": professional},
    )
    assert patched.status_code == 400, patched.text


@pytest.mark.asyncio
async def test_professional_of_the_clinic_is_accepted(
    client: AsyncClient, auth_headers: dict, recall_id: str, dentist_id: str
) -> None:
    r = await client.patch(
        f"/api/v1/recalls/{recall_id}",
        headers=auth_headers,
        json={"assigned_professional_id": dentist_id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["assigned_professional_id"] == dentist_id
