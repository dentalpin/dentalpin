"""A data-subject request only links a patient of its own clinic.

``patient_id`` is optional on a DSR, but when given it was stored as is.
An unknown id was a 500 (ForeignKeyViolation). Another clinic's patient was
stored, so this clinic's DSR register held a request linked to a patient it
cannot see, and the ``gdpr.request.created`` event carried that id. Consents
and erasure already return 404 here (#562).
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.gdpr.models import GdprRequest
from app.modules.gdpr.tools import CreateRequestArgs, _create_request
from app.modules.patients.models import Patient

URL = "/api/v1/gdpr/requests"
BODY = {"requester_name": "Ana", "requester_email": "ana@test.com", "request_type": "access"}


async def _outsider(db: AsyncSession, which: str) -> str:
    if which == "unknown":
        return str(uuid4())
    other = Clinic(id=uuid4(), name="Other", tax_id="B99999991")
    db.add(other)
    await db.flush()
    patient = Patient(clinic_id=other.id, first_name="Eve", last_name="Elsewhere")
    db.add(patient)
    await db.commit()
    return str(patient.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("which", ["unknown", "other_clinic"])
async def test_create_rejects_a_patient_outside_the_clinic_and_stores_nothing(
    client: AsyncClient, auth_headers, db_session: AsyncSession, test_clinic: Clinic, which
) -> None:
    r = await client.post(
        URL,
        json={**BODY, "patient_id": await _outsider(db_session, which)},
        headers=auth_headers,
    )
    assert r.status_code == 404, r.text
    assert r.json()["message"] == "Patient not found"
    assert await db_session.scalar(select(func.count()).select_from(GdprRequest)) == 0


@pytest.mark.asyncio
async def test_create_still_takes_a_request_without_a_patient_or_with_the_clinics(
    client: AsyncClient, auth_headers, test_clinic: Clinic, test_patient: Patient
) -> None:
    assert (await client.post(URL, json=BODY, headers=auth_headers)).status_code == 201
    r = await client.post(
        URL, json={**BODY, "patient_id": str(test_patient.id)}, headers=auth_headers
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["patient_id"] == str(test_patient.id)


@pytest.mark.asyncio
async def test_tool_reports_a_patient_outside_the_clinic(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    ctx = SimpleNamespace(db=db_session, clinic_id=test_clinic.id)
    out = await _create_request(
        ctx, CreateRequestArgs(**BODY, patient_id=await _outsider(db_session, "other_clinic"))
    )
    assert out == {"error": "patient not found"}
