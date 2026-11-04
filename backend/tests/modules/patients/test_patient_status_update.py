"""PUT with a status is the same act as archive/restore, so it must run their
cascades, and it accepts only the two statuses a patient can have."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.media.models import Document
from app.modules.patients.models import Patient


async def _document(db: AsyncSession, clinic: Clinic, patient: Patient) -> Document:
    user_id = (await db.execute(select(User))).scalars().first().id
    doc = Document(
        clinic_id=clinic.id,
        patient_id=patient.id,
        document_type="other",
        title="Consentimiento",
        original_filename="consent.pdf",
        storage_path=f"/tmp/{uuid4()}.pdf",
        mime_type="application/pdf",
        file_size=1024,
        uploaded_by=user_id,
    )
    db.add(doc)
    await db.commit()
    return doc


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["", "/extended"])
async def test_put_archived_then_active_runs_the_document_cascade(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    suffix: str,
) -> None:
    doc = await _document(db_session, test_clinic, test_patient)
    url = f"/api/v1/patients/{test_patient.id}{suffix}"

    archived = await client.put(url, json={"status": "archived"}, headers=auth_headers)
    assert archived.status_code == 200, archived.text
    assert archived.json()["data"]["status"] == "archived"
    await db_session.refresh(doc)
    assert doc.status == "archived"

    restored = await client.put(url, json={"status": "active"}, headers=auth_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["status"] == "active"
    await db_session.refresh(doc)
    assert doc.status != "archived"


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["", "/extended"])
async def test_put_rejects_unknown_status(
    client: AsyncClient, auth_headers: dict, test_patient: Patient, suffix: str
) -> None:
    response = await client.put(
        f"/api/v1/patients/{test_patient.id}{suffix}",
        json={"status": "zzbogus"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_put_status_alongside_other_fields_applies_both(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
) -> None:
    response = await client.put(
        f"/api/v1/patients/{test_patient.id}",
        json={"status": "archived", "first_name": "Renamed"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "archived"
    assert data["first_name"] == "Renamed"


@pytest.mark.asyncio
async def test_put_null_status_is_not_a_server_error(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
) -> None:
    response = await client.put(
        f"/api/v1/patients/{test_patient.id}",
        json={"status": None},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_put_active_repairs_a_status_stored_before_validation(
    client: AsyncClient,
    auth_headers: dict,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    test_patient.status = "zzbogus"
    await db_session.commit()

    response = await client.put(
        f"/api/v1/patients/{test_patient.id}",
        json={"status": "active"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "active"
