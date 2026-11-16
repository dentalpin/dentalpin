"""Two patients are linked once, even when two requests race.

The service pre-checks "already linked, in either direction" and the table
only has a unique key on the ordered pair ``(patient_id, related_patient_id)``.
Two concurrent requests both passed the pre-check. A→B twice raised the
IntegrityError into a 500. A→B and B→A were both stored, so each patient's
family list showed the other twice. Production hands each request its own
session, so these tests do too (#870).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.database import async_session_maker, get_db
from app.main import app
from app.modules.patient_relationships.models import PatientRelationship
from app.modules.patients.models import Patient


async def _own_session_per_request() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


@pytest.mark.asyncio
@pytest.mark.parametrize("direction", ["same", "reversed"])
async def test_concurrent_links_store_the_pair_once(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    direction: str,
) -> None:
    sibling = Patient(clinic_id=test_clinic.id, first_name="Sibling", last_name="Patient")
    db_session.add(sibling)
    await db_session.commit()
    a, b = str(test_patient.id), str(sibling.id)
    pairs = [(a, b), (a, b)] if direction == "same" else [(a, b), (b, a)]

    app.dependency_overrides[get_db] = _own_session_per_request

    async def link(owner: str, other: str) -> int:
        r = await client.post(
            f"/api/v1/patient_relationships/patients/{owner}/relationships",
            json={"related_patient_id": other, "relationship_type": "sibling"},
            headers=auth_headers,
        )
        return r.status_code

    outcomes = await asyncio.gather(*(link(o, x) for o, x in pairs))

    assert sorted(outcomes) == [201, 409]
    async with async_session_maker() as fresh:
        count = await fresh.scalar(
            select(func.count())
            .select_from(PatientRelationship)
            .where(PatientRelationship.clinic_id == test_clinic.id)
        )
    assert count == 1
