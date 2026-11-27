"""An appointment must end strictly after it starts (#1242).

Covers create and update over REST (including an update that sends only
one of the two times, checked against the stored other one) and the two
copilot write tools. A row that is already bad can still be edited when
the edit leaves the times alone.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.context import AgentContext, AgentMode
from app.core.agents.models import Agent, AgentSession
from app.core.agents.tools.registry import tool_registry
from app.core.auth.models import ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.agenda.models import Appointment
from app.modules.agenda.service import AppointmentService

pytestmark = pytest.mark.asyncio

URL = "/api/v1/agenda/appointments"
START = datetime(2031, 3, 3, 10, 0, tzinfo=UTC)


async def _dentist(db: AsyncSession, clinic_id) -> User:
    user = User(
        id=uuid4(),
        email=f"dentist-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Dentist",
        last_name="Range",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    db.add(ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic_id, role="dentist"))
    await db.commit()
    return user


def _body(patient, dentist, start: datetime, end: datetime) -> dict:
    return {
        "patient_id": str(patient.id),
        "professional_id": str(dentist.id),
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }


async def _times(db: AsyncSession, appointment_id) -> tuple[datetime, datetime]:
    db.expire_all()
    row = await db.get(Appointment, appointment_id)
    return row.start_time, row.end_time


@pytest.mark.parametrize("minutes", [-120, 0], ids=["inverted", "zero_length"])
async def test_create_rejects_end_not_after_start(
    client, auth_headers, db_session, test_clinic, test_patient, minutes
):
    dentist = await _dentist(db_session, test_clinic.id)
    body = _body(test_patient, dentist, START, START + timedelta(minutes=minutes))
    res = await client.post(URL, json=body, headers=auth_headers)
    assert res.status_code == 400, res.text
    assert res.json()["message"] == "end_time must be after start_time"


async def test_create_accepts_valid_range(
    client, auth_headers, db_session, test_clinic, test_patient
):
    dentist = await _dentist(db_session, test_clinic.id)
    body = _body(test_patient, dentist, START, START + timedelta(minutes=30))
    res = await client.post(URL, json=body, headers=auth_headers)
    assert res.status_code == 201, res.text


@pytest.mark.parametrize(
    "patch",
    [
        {"end_time": (START - timedelta(hours=1)).isoformat()},  # end before stored start
        {"end_time": START.isoformat()},  # end equal to stored start
        {"start_time": (START + timedelta(hours=2)).isoformat()},  # start after stored end
        {
            "start_time": (START + timedelta(hours=1)).isoformat(),
            "end_time": START.isoformat(),
        },
    ],
    ids=["end_only_before_start", "end_only_equal_start", "start_only_after_end", "both"],
)
async def test_update_rejects_merged_range(
    client, auth_headers, db_session, test_clinic, test_patient, patch
):
    dentist = await _dentist(db_session, test_clinic.id)
    created = await client.post(
        URL,
        json=_body(test_patient, dentist, START, START + timedelta(minutes=60)),
        headers=auth_headers,
    )
    appt_id = created.json()["data"]["id"]

    res = await client.put(f"{URL}/{appt_id}", json=patch, headers=auth_headers)
    assert res.status_code == 400, res.text
    assert res.json()["message"] == "end_time must be after start_time"
    assert await _times(db_session, appt_id) == (START, START + timedelta(minutes=60))


async def test_update_single_time_valid_range_still_works(
    client, auth_headers, db_session, test_clinic, test_patient
):
    dentist = await _dentist(db_session, test_clinic.id)
    created = await client.post(
        URL,
        json=_body(test_patient, dentist, START, START + timedelta(minutes=60)),
        headers=auth_headers,
    )
    appt_id = created.json()["data"]["id"]
    new_end = START + timedelta(minutes=90)
    res = await client.put(
        f"{URL}/{appt_id}", json={"end_time": new_end.isoformat()}, headers=auth_headers
    )
    assert res.status_code == 200, res.text
    assert await _times(db_session, appt_id) == (START, new_end)


async def test_legacy_bad_row_can_still_be_edited_without_times(
    client, auth_headers, db_session, test_clinic, test_patient
):
    dentist = await _dentist(db_session, test_clinic.id)
    created = await client.post(
        URL,
        json=_body(test_patient, dentist, START, START + timedelta(minutes=60)),
        headers=auth_headers,
    )
    row_id = created.json()["data"]["id"]
    # Make it a row stored before the check existed.
    await db_session.execute(
        update(Appointment)
        .where(Appointment.id == row_id)
        .values(end_time=START - timedelta(hours=1))
    )
    await db_session.commit()

    res = await client.put(f"{URL}/{row_id}", json={"color": "#FF0000"}, headers=auth_headers)
    assert res.status_code == 200, res.text

    res = await client.put(
        f"{URL}/{row_id}",
        json={"end_time": (START + timedelta(minutes=30)).isoformat()},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text


async def _ctx(db: AsyncSession, clinic_id, supervisor_id) -> AgentContext:
    from app.modules.copilot.bridge import COPILOT_GUARDRAILS

    agent = Agent(clinic_id=clinic_id, name="copilot", type="copilot", mode="autonomous", config={})
    db.add(agent)
    await db.flush()
    session = AgentSession(agent_id=agent.id, clinic_id=clinic_id)
    db.add(session)
    await db.flush()
    return AgentContext(
        agent_id=agent.id,
        session_id=session.id,
        clinic_id=clinic_id,
        mode=AgentMode.AUTONOMOUS,
        permissions=["agenda.appointments.write"],
        tools=tool_registry,
        db=db,
        supervisor_id=supervisor_id,
        guardrail_config=COPILOT_GUARDRAILS,
    )


async def test_book_appointment_tool_rejects_inverted_range(db_session, test_clinic, test_patient):
    dentist = await _dentist(db_session, test_clinic.id)
    ctx = await _ctx(db_session, test_clinic.id, dentist.id)
    res = await tool_registry.call(
        ctx,
        "agenda.book_appointment",
        {
            "patient_id": str(test_patient.id),
            "professional_id": str(dentist.id),
            "start_time": START.isoformat(),
            "end_time": (START - timedelta(hours=2)).isoformat(),
        },
    )
    assert res.ok, res.error
    assert res.data["error"] == "invalid_time_range"
    total = (await AppointmentService.list_appointments(db_session, test_clinic.id))[1]
    assert total == 0


async def test_reschedule_appointment_tool_rejects_inverted_range(
    db_session, test_clinic, test_patient
):
    dentist = await _dentist(db_session, test_clinic.id)
    appt = await AppointmentService.create_appointment(
        db_session,
        test_clinic.id,
        {
            "patient_id": test_patient.id,
            "professional_id": dentist.id,
            "start_time": START,
            "end_time": START + timedelta(minutes=30),
        },
    )
    await db_session.commit()
    ctx = await _ctx(db_session, test_clinic.id, dentist.id)
    new_start = START + timedelta(days=1)
    res = await tool_registry.call(
        ctx,
        "agenda.reschedule_appointment",
        {
            "appointment_id": str(appt.id),
            "start_time": new_start.isoformat(),
            "end_time": new_start.isoformat(),
        },
    )
    assert res.ok, res.error
    assert res.data["error"] == "invalid_time_range"
    assert await _times(db_session, appt.id) == (START, START + timedelta(minutes=30))
