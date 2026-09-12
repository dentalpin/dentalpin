"""patients restore: archived -> active, no-op when active, 404s, media cascade."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
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


@pytest.mark.asyncio
async def test_restore_other_clinic_patient_404s(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999991",
        address={"street": "Calle Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other_clinic)
    await db_session.flush()
    other_patient = Patient(
        clinic_id=other_clinic.id, first_name="Otra", last_name="Clínica", status="archived"
    )
    db_session.add(other_patient)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/patients/{other_patient.id}/restore", headers=auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_restore_reverses_media_archive_cascade(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    from app.core.auth.models import User
    from app.modules.media.models import Document

    uploader = (
        await db_session.execute(select(User).where(User.email == "test@example.com"))
    ).scalar_one()
    doc = Document(
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        status="active",
        document_type="consent",
        title="Consentimiento",
        original_filename="consent.pdf",
        storage_path="test/consent.pdf",
        mime_type="application/pdf",
        file_size=10,
        uploaded_by=uploader.id,
    )
    db_session.add(doc)
    await db_session.commit()

    await PatientService.archive_patient(db_session, test_patient)
    await db_session.commit()
    await db_session.refresh(doc)
    assert doc.status == "archived"

    response = await client.post(
        f"/api/v1/patients/{test_patient.id}/restore", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    await db_session.refresh(doc)
    assert doc.status == "active"
