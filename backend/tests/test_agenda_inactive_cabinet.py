"""An inactive cabinet can't receive appointments (#1237).

Creating an appointment into it, moving one into it through
``PUT /appointments/{id}`` or assigning it through
``PATCH /appointments/{id}/cabinet`` answers 400. An appointment already in
a cabinet that was deactivated afterwards stays readable and editable as
long as the edit doesn't move it into another inactive cabinet.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.agenda.models import Cabinet
from app.modules.patients.models import Patient

BASE = "/api/v1/agenda"


@pytest_asyncio.fixture
async def world(db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]
    clinic = Clinic(id=uuid4(), name="ICA", tax_id="B11111111", address={"city": "M"}, settings={})
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(ClinicMembership(id=uuid4(), user_id=user_id, clinic_id=clinic.id, role="admin"))
    dentist = User(
        id=uuid4(),
        email=f"d-{uuid4().hex[:8]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Ada",
        last_name="L",
        is_active=True,
    )
    active = Cabinet(id=uuid4(), clinic_id=clinic.id, name="Active", color="#000", display_order=0)
    old = Cabinet(id=uuid4(), clinic_id=clinic.id, name="Old", color="#f00", display_order=1)
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="P", last_name="Q")
    db_session.add_all([dentist, active, old, patient])
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=dentist.id, clinic_id=clinic.id, role="dentist")
    )
    await db_session.commit()
    return {
        "dentist": str(dentist.id),
        "patient": str(patient.id),
        "active": str(active.id),
        "old": str(old.id),
    }


def _slot(day: int = 2) -> tuple[str, str]:
    start = datetime.now(UTC).replace(microsecond=0, second=0) + timedelta(days=day)
    return start.isoformat(), (start + timedelta(minutes=30)).isoformat()


async def _deactivate(client: AsyncClient, headers: dict[str, str], cabinet_id: str) -> None:
    r = await client.put(
        f"{BASE}/cabinets/{cabinet_id}", json={"is_active": False}, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["is_active"] is False


async def _book(client, headers, world, cabinet_id, day: int = 2):
    start, end = _slot(day)
    return await client.post(
        f"{BASE}/appointments",
        json={
            "patient_id": world["patient"],
            "professional_id": world["dentist"],
            "cabinet_id": cabinet_id,
            "start_time": start,
            "end_time": end,
        },
        headers=headers,
    )


@pytest.mark.asyncio
async def test_create_into_inactive_cabinet_answers_400(client, auth_headers, world):
    await _deactivate(client, auth_headers, world["old"])
    r = await _book(client, auth_headers, world, world["old"])
    assert r.status_code == 400, r.text
    assert "inactive" in r.json()["message"].lower()


@pytest.mark.asyncio
async def test_create_by_name_into_inactive_cabinet_answers_400(client, auth_headers, world):
    await _deactivate(client, auth_headers, world["old"])
    start, end = _slot()
    r = await client.post(
        f"{BASE}/appointments",
        json={
            "patient_id": world["patient"],
            "professional_id": world["dentist"],
            "cabinet": "Old",
            "start_time": start,
            "end_time": end,
        },
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_assign_inactive_cabinet_answers_400(client, auth_headers, world):
    r = await _book(client, auth_headers, world, world["active"])
    assert r.status_code == 201, r.text
    appt_id = r.json()["data"]["id"]
    await _deactivate(client, auth_headers, world["old"])

    r = await client.patch(
        f"{BASE}/appointments/{appt_id}/cabinet",
        json={"cabinet_id": world["old"]},
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text
    assert "inactive" in r.json()["message"].lower()


@pytest.mark.asyncio
async def test_update_moving_into_inactive_cabinet_answers_400(client, auth_headers, world):
    r = await _book(client, auth_headers, world, world["active"])
    appt_id = r.json()["data"]["id"]
    await _deactivate(client, auth_headers, world["old"])

    r = await client.put(
        f"{BASE}/appointments/{appt_id}",
        json={"cabinet_id": world["old"]},
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text
    r = await client.get(f"{BASE}/appointments/{appt_id}", headers=auth_headers)
    assert r.json()["data"]["cabinet_id"] == world["active"]


@pytest.mark.asyncio
async def test_existing_appointment_in_deactivated_cabinet_stays_editable(
    client, auth_headers, world
):
    r = await _book(client, auth_headers, world, world["old"])
    assert r.status_code == 201, r.text
    appt_id = r.json()["data"]["id"]
    await _deactivate(client, auth_headers, world["old"])

    r = await client.get(f"{BASE}/appointments/{appt_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["cabinet_id"] == world["old"]

    # The appointment modal resends the cabinet it already sits in.
    r = await client.put(
        f"{BASE}/appointments/{appt_id}",
        json={"cabinet_id": world["old"], "treatment_type": "still here"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["cabinet_id"] == world["old"]
    assert r.json()["data"]["treatment_type"] == "still here"

    # Re-assigning the same cabinet is a no-op, not an error.
    r = await client.patch(
        f"{BASE}/appointments/{appt_id}/cabinet",
        json={"cabinet_id": world["old"]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text

    # Moving it out to an active cabinet works.
    r = await client.patch(
        f"{BASE}/appointments/{appt_id}/cabinet",
        json={"cabinet_id": world["active"]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["cabinet_id"] == world["active"]


@pytest.mark.asyncio
async def test_reactivated_cabinet_is_bookable_again(client, auth_headers, world):
    await _deactivate(client, auth_headers, world["old"])
    r = await client.put(
        f"{BASE}/cabinets/{world['old']}", json={"is_active": True}, headers=auth_headers
    )
    assert r.status_code == 200
    r = await _book(client, auth_headers, world, world["old"])
    assert r.status_code == 201, r.text
