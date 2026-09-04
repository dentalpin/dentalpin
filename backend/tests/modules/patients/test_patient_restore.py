"""patients restore: archived -> active, no-op when active, 404 when unknown."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.patients.models import Patient
from app.modules.patients.service import PatientService


@pytest.mark.asyncio
async def test_restore_archived_patient_then_noop(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    await PatientService.archive_patient(db_session, test_patient)
    assert test_patient.status == "archived"

    response = await client.post(
        f"/api/v1/patients/{test_patient.id}/restore", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "active"

    again = await client.post(f"/api/v1/patients/{test_patient.id}/restore", headers=auth_headers)
    assert again.status_code == 200
    assert again.json()["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_restore_unknown_patient_404s(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    response = await client.post(f"/api/v1/patients/{uuid4()}/restore", headers=auth_headers)
    assert response.status_code == 404
