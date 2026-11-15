"""API-level tests for the appointment status lifecycle.

Covers the two new endpoints:

- ``POST /agenda/appointments/{id}/transitions``
- ``GET  /agenda/appointments/{id}/transitions``

Plus:
- Multi-tenancy: clinic A cannot see clinic B's history.
- Bus events: every transition publishes the generic
  ``APPOINTMENT_STATUS_CHANGED`` plus the specific event for the target
  state (e.g. ``APPOINTMENT_CHECKED_IN``).
- ``PUT /agenda/appointments/{id}`` with a ``status`` field still records
  the transition (drag & drop backward compatibility).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.core.events import EventType, event_bus
from app.modules.agenda.service import AppointmentService


@pytest_asyncio.fixture
async def clinic_setup(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> dict:
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = response.json()["data"]["user"]["id"]

    clinic = Clinic(
        id=uuid4(),
        name="Test Clinic",
        tax_id="B99999999",
        address={"city": "Madrid"},
        settings={},
    )
    db_session.add(clinic)
    await db_session.flush()

    db_session.add(ClinicMembership(id=uuid4(), user_id=user_id, clinic_id=clinic.id, role="admin"))

    dentist = User(
        id=uuid4(),
        email=f"dentist-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Ada",
        last_name="Lovelace",
        is_active=True,
    )
    db_session.add(dentist)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=dentist.id, clinic_id=clinic.id, role="dentist")
    )

    from app.modules.agenda.models import Cabinet

    db_session.add(
        Cabinet(
            id=uuid4(),
            clinic_id=clinic.id,
            name="Gabinete 1",
            color="#3B82F6",
            display_order=0,
            is_active=True,
        )
    )
    await db_session.commit()

    return {
        "clinic_id": str(clinic.id),
        "user_id": user_id,
        "dentist_id": str(dentist.id),
    }


@pytest.mark.asyncio
async def test_assistant_assignment_is_active_and_clinic_scoped(
    db_session: AsyncSession, clinic_setup: dict
) -> None:
    clinic_id = UUID(clinic_setup["clinic_id"])
    assistant = User(
        id=uuid4(),
        email=f"assistant-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Ari",
        last_name="Assistant",
        is_active=True,
    )
    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id=f"B{uuid4().int % 10**8:08d}",
        address={"city": "Madrid"},
        settings={},
    )
    db_session.add_all([assistant, other_clinic])
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(), user_id=assistant.id, clinic_id=clinic_id, role="assistant"
        )
    )
    await db_session.commit()

    assert await AppointmentService.validate_assistant_access(db_session, clinic_id, assistant.id)
    assert not await AppointmentService.validate_assistant_access(
        db_session, other_clinic.id, assistant.id
    )

    assistant.is_active = False
    await db_session.commit()
    assert not await AppointmentService.validate_assistant_access(
        db_session, clinic_id, assistant.id
    )


@pytest.mark.asyncio
async def test_appointment_assistant_must_be_active_clinic_member(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_setup: dict,
    db_session: AsyncSession,
) -> None:
    patient = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "A", "last_name": "Patient"},
    )
    patient_id = patient.json()["data"]["id"]
    assistant = User(
        id=uuid4(),
        email=f"assistant-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Ari",
        last_name="Assistant",
        is_active=True,
    )
    db_session.add(assistant)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(),
            user_id=assistant.id,
            clinic_id=UUID(clinic_setup["clinic_id"]),
            role="assistant",
        )
    )
    await db_session.commit()

    booking = {
        "patient_id": patient_id,
        "professional_id": clinic_setup["dentist_id"],
        "assistant_id": str(assistant.id),
        "start_time": "2026-05-01T09:00:00Z",
        "end_time": "2026-05-01T09:30:00Z",
    }
    created = await client.post("/api/v1/agenda/appointments", headers=auth_headers, json=booking)
    assert created.status_code == 201, created.text
    assert created.json()["data"]["assistant_id"] == str(assistant.id)
    assert created.json()["data"]["assistant"]["first_name"] == "Ari"

    assistant.is_active = False
    await db_session.commit()
    rejected = await client.post(
        "/api/v1/agenda/appointments", headers=auth_headers, json=booking
    )
    assert rejected.status_code == 400, rejected.text


class BusSpy:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []
        self._handlers: list[tuple[str, Any]] = []

    def hook(self) -> None:
        for ev in (
            EventType.APPOINTMENT_STATUS_CHANGED,
            EventType.APPOINTMENT_CONFIRMED,
            EventType.APPOINTMENT_CHECKED_IN,
            EventType.APPOINTMENT_IN_TREATMENT,
            EventType.APPOINTMENT_COMPLETED,
            EventType.APPOINTMENT_CANCELLED,
            EventType.APPOINTMENT_NO_SHOW,
        ):
            handler = self._handler_for(ev)
            event_bus.subscribe(ev, handler)
            self._handlers.append((ev, handler))

    def _handler_for(self, ev: str):
        def _handler(data: dict[str, Any]) -> None:
            self.events.append((ev, data))

        return _handler

    def unhook(self) -> None:
        for ev, handler in self._handlers:
            event_bus.unsubscribe(ev, handler)

    def names(self) -> list[str]:
        return [name for name, _ in self.events]


@pytest.fixture
def bus_spy() -> BusSpy:
    spy = BusSpy()
    spy.hook()
    yield spy
    spy.unhook()


@pytest.mark.asyncio
async def test_post_transition_returns_history_and_publishes_events(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_setup: dict,
    bus_spy: BusSpy,
) -> None:
    patient = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "P", "last_name": "Q"},
    )
    patient_id = patient.json()["data"]["id"]

    created = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": clinic_setup["dentist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-01T09:00:00Z",
            "end_time": "2026-05-01T09:30:00Z",
        },
    )
    assert created.status_code == 201
    apt_id = created.json()["data"]["id"]

    bus_spy.events.clear()
    resp = await client.post(
        f"/api/v1/agenda/appointments/{apt_id}/transitions",
        headers=auth_headers,
        json={"to_status": "checked_in", "note": "arrived early"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "checked_in"
    assert body["history"] is not None
    assert [e["to_status"] for e in body["history"]] == ["scheduled", "checked_in"]
    assert body["history"][-1]["note"] == "arrived early"
    assert body["history"][-1]["changed_by_name"]

    names = bus_spy.names()
    assert EventType.APPOINTMENT_STATUS_CHANGED in names
    assert EventType.APPOINTMENT_CHECKED_IN in names


@pytest.mark.asyncio
async def test_invalid_transition_returns_400(
    client: AsyncClient, auth_headers: dict[str, str], clinic_setup: dict
) -> None:
    patient = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "P", "last_name": "Q"},
    )
    patient_id = patient.json()["data"]["id"]
    created = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": clinic_setup["dentist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-02T09:00:00Z",
            "end_time": "2026-05-02T09:30:00Z",
        },
    )
    apt_id = created.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/agenda/appointments/{apt_id}/transitions",
        headers=auth_headers,
        json={"to_status": "completed"},
    )
    assert resp.status_code == 400
    assert "Cannot transition" in resp.json()["message"]


@pytest.mark.asyncio
async def test_same_state_transition_returns_409(
    client: AsyncClient, auth_headers: dict[str, str], clinic_setup: dict
) -> None:
    patient = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "P", "last_name": "Q"},
    )
    patient_id = patient.json()["data"]["id"]
    created = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": clinic_setup["dentist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-03T09:00:00Z",
            "end_time": "2026-05-03T09:30:00Z",
        },
    )
    apt_id = created.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/agenda/appointments/{apt_id}/transitions",
        headers=auth_headers,
        json={"to_status": "scheduled"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_transitions_returns_chronological_history(
    client: AsyncClient, auth_headers: dict[str, str], clinic_setup: dict
) -> None:
    patient = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "P", "last_name": "Q"},
    )
    patient_id = patient.json()["data"]["id"]
    created = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": clinic_setup["dentist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-04T09:00:00Z",
            "end_time": "2026-05-04T09:30:00Z",
        },
    )
    apt_id = created.json()["data"]["id"]

    for to in ("checked_in", "in_treatment", "completed"):
        r = await client.post(
            f"/api/v1/agenda/appointments/{apt_id}/transitions",
            headers=auth_headers,
            json={"to_status": to},
        )
        assert r.status_code == 200

    resp = await client.get(
        f"/api/v1/agenda/appointments/{apt_id}/transitions",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    events = resp.json()["data"]
    assert [e["to_status"] for e in events] == [
        "scheduled",
        "checked_in",
        "in_treatment",
        "completed",
    ]


@pytest.mark.asyncio
async def test_put_status_still_creates_event(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_setup: dict,
    bus_spy: BusSpy,
) -> None:
    """Legacy drag & drop path — ``PUT /appointments/{id}`` with a new
    ``status`` must still go through the audit trail.
    """
    patient = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "P", "last_name": "Q"},
    )
    patient_id = patient.json()["data"]["id"]
    created = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": clinic_setup["dentist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-05T09:00:00Z",
            "end_time": "2026-05-05T09:30:00Z",
        },
    )
    apt_id = created.json()["data"]["id"]

    bus_spy.events.clear()
    resp = await client.put(
        f"/api/v1/agenda/appointments/{apt_id}",
        headers=auth_headers,
        json={"status": "confirmed"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "confirmed"

    hist = await client.get(
        f"/api/v1/agenda/appointments/{apt_id}/transitions",
        headers=auth_headers,
    )
    assert [e["to_status"] for e in hist.json()["data"]] == ["scheduled", "confirmed"]
    assert EventType.APPOINTMENT_CONFIRMED in bus_spy.names()
