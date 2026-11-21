"""A lead converts into one patient, even when two requests race.

``convert`` refused an already-converted lead, but read the lead's status
without a lock. A double click on "Convert" sent two requests that both saw
``new``, and each created a patient: the clinic got a duplicate patient and
the lead linked only the second one. Production hands each request its own
session, so this test does too.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.database import async_session_maker, get_db
from app.main import app
from app.modules.leads.models import Lead
from app.modules.patients.models import Patient

from .test_leads import BASE, _create_lead


@pytest.mark.asyncio
async def test_a_double_click_on_convert_creates_one_patient(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic: Clinic
):
    lead = await _create_lead(client, auth_headers)
    await db_session.commit()
    body = {"first_name": "Marta", "last_name": "Ruiz", "phone": "+34 699 888 777"}

    # The real dependency: one session per request, committed on success.
    app.dependency_overrides.pop(get_db, None)

    async def convert() -> int:
        r = await client.post(f"{BASE}{lead['id']}/convert", json=body, headers=auth_headers)
        return r.status_code

    outcomes = await asyncio.gather(convert(), convert())

    assert sorted(outcomes) == [200, 409]
    async with async_session_maker() as fresh:
        patients = (
            await fresh.scalars(
                select(Patient.id).where(
                    Patient.clinic_id == test_clinic.id, Patient.last_name == "Ruiz"
                )
            )
        ).all()
        linked = await fresh.scalar(select(Lead.patient_id).where(Lead.id == lead["id"]))
        count = await fresh.scalar(
            select(func.count()).select_from(Lead).where(Lead.clinic_id == test_clinic.id)
        )
    assert len(patients) == 1
    assert linked == patients[0]
    assert count == 1
