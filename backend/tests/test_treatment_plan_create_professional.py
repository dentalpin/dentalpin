"""Creating a plan checks its professional, like updating it already did.

``update`` and ``add_item`` call ``_validate_professional_in_clinic``, but
``create`` stored ``assigned_professional_id`` as given. An unknown id was a
500 (ForeignKeyViolation). Another clinic's dentist was stored and rendered
back with their name. Every later item then inherited that professional and
failed with "Invalid professional for this clinic".
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.patients.models import Patient

URL = "/api/v1/treatment_plan/treatment-plans"


async def _dentist(db: AsyncSession, clinic_id) -> str:
    user = User(
        email=f"dentist-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Ada",
        last_name="Elsewhere",
    )
    db.add(user)
    await db.flush()
    db.add(ClinicMembership(user_id=user.id, clinic_id=clinic_id, role="dentist"))
    await db.commit()
    return str(user.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("which", ["unknown", "other_clinic"])
async def test_create_rejects_a_professional_outside_the_clinic(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_patient: Patient,
    which: str,
) -> None:
    if which == "unknown":
        professional = str(uuid4())
    else:
        other = Clinic(id=uuid4(), name="Other", tax_id="B87654321")
        db_session.add(other)
        await db_session.flush()
        professional = await _dentist(db_session, other.id)

    r = await client.post(
        URL,
        headers=auth_headers,
        json={"patient_id": str(test_patient.id), "assigned_professional_id": professional},
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_create_accepts_a_professional_of_the_clinic(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
) -> None:
    professional = await _dentist(db_session, test_clinic.id)
    r = await client.post(
        URL,
        headers=auth_headers,
        json={"patient_id": str(test_patient.id), "assigned_professional_id": professional},
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["assigned_professional_id"] == professional
