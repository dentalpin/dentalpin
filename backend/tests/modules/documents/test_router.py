"""HTTP coverage for the documents module (CRUD + generate + journal)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.activity_journal.models import ActivityJournalEntry
from app.modules.patients.models import Patient


@pytest.mark.asyncio
async def test_document_crud_and_generate_flow(
    client, auth_headers, test_clinic: Clinic, test_patient
) -> None:
    """Create → get → patch → filter → generate → soft-delete."""
    patient_id = str(test_patient.id)

    response = await client.get("/api/v1/documents", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["data"] == []

    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "document_type": "prescription",
            "title": "Amoxicillin Rx",
            "content": {"diagnosis": "stomatitis", "medications": []},
        },
    )
    assert response.status_code == 201
    doc = response.json()["data"]
    assert doc["status"] == "draft"
    assert doc["created_by"] is not None
    assert doc["document_type"] == "prescription"
    doc_id = doc["id"]

    response = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["id"] == doc_id

    response = await client.patch(
        f"/api/v1/documents/{doc_id}",
        headers=auth_headers,
        json={"title": "Amoxicillin 500mg"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Amoxicillin 500mg"

    response = await client.get(
        "/api/v1/documents?document_type=prescription", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = await client.post(
        "/api/v1/documents/generate", headers=auth_headers, json={"document_id": doc_id}
    )
    assert response.status_code == 200
    generated = response.json()["data"]
    assert generated["status"] == "generated"
    assert generated["file_path"].endswith(".pdf")

    response = await client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert response.status_code == 204
    response = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "archived"

    response = await client.get(f"/api/v1/documents/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_renders_and_streams_pdf(
    client, auth_headers, test_clinic: Clinic, test_patient
) -> None:
    """A generated document can be downloaded as its persisted PDF.

    The file is rendered for real (WeasyPrint), written under the
    storage backend and streamed back with attachment semantics. Before
    generation the same route answers 409.
    """
    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        json={
            "patient_id": str(test_patient.id),
            "document_type": "medical_certificate",
            "title": "Sick leave",
            "content": {"diagnosis": "flu", "description": "5 days rest"},
        },
    )
    assert response.status_code == 201
    doc_id = response.json()["data"]["id"]

    # Not generated yet → 409, not a broken 404.
    response = await client.get(f"/api/v1/documents/{doc_id}/download", headers=auth_headers)
    assert response.status_code == 409

    response = await client.post(
        "/api/v1/documents/generate", headers=auth_headers, json={"document_id": doc_id}
    )
    assert response.status_code == 200
    assert response.json()["data"]["file_path"] == f"documents/{test_clinic.id}/{doc_id}.pdf"

    response = await client.get(f"/api/v1/documents/{doc_id}/download", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert "attachment" in response.headers["content-disposition"]
    assert "medical_certificate" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_create_document_rejects_foreign_patient(
    client, auth_headers, test_clinic: Clinic, db_session: AsyncSession
) -> None:
    """A patient owned by another clinic must never be referenceable."""
    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B87654321",
        address={"street": "Other St", "city": "Barcelona"},
    )
    db_session.add(other_clinic)
    await db_session.flush()
    foreign_patient = Patient(
        id=uuid4(),
        clinic_id=other_clinic.id,
        first_name="Foreign",
        last_name="Patient",
    )
    db_session.add(foreign_patient)
    await db_session.commit()

    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        json={
            "patient_id": str(foreign_patient.id),
            "document_type": "prescription",
            "title": "Cross-clinic leak",
            "content": {"diagnosis": "x", "medications": []},
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_malformed_uuid_returns_422(client, auth_headers, test_clinic) -> None:
    """Non-UUID identifiers are rejected by validation, not swallowed."""
    response = await client.get("/api/v1/documents/not-a-uuid", headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_letterhead_settings_roundtrip(client, auth_headers, test_clinic: Clinic) -> None:
    """Letterhead overrides persist namespaced under clinic settings.

    Keys omitted from the payload stay unset (→ ``null``) so the renderer
    falls back to the clinic profile for just those fields.
    """
    response = await client.get("/api/v1/documents/settings/letterhead", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"] == {
        "name": None,
        "address": None,
        "phone": None,
        "email": None,
        "registration_number": None,
        "logo": None,
    }

    response = await client.put(
        "/api/v1/documents/settings/letterhead",
        headers=auth_headers,
        json={"name": "My Clinic", "phone": "+34911111111"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "My Clinic"
    assert response.json()["data"]["phone"] == "+34911111111"
    assert response.json()["data"]["address"] is None

    response = await client.get("/api/v1/documents/settings/letterhead", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "My Clinic"
    assert response.json()["data"]["phone"] == "+34911111111"
    assert response.json()["data"]["registration_number"] is None

    # A full overwrite clears previously stored keys.
    response = await client.put(
        "/api/v1/documents/settings/letterhead",
        headers=auth_headers,
        json={"name": "Renamed"},
    )
    assert response.status_code == 200
    response = await client.get("/api/v1/documents/settings/letterhead", headers=auth_headers)
    assert response.json()["data"]["name"] == "Renamed"
    assert response.json()["data"]["phone"] is None


@pytest.mark.asyncio
async def test_generate_writes_activity_journal_row(
    client, auth_headers, test_clinic: Clinic, test_patient, db_session: AsyncSession
) -> None:
    """``document.generated`` is published transactionally and the
    activity_journal subscription records an attributed row."""
    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        json={
            "patient_id": str(test_patient.id),
            "document_type": "referral",
            "title": "Referred to ortho",
            "content": {"referred_to": "Dr. Ortho", "specialty": "orthodontics"},
        },
    )
    assert response.status_code == 201
    doc_id = response.json()["data"]["id"]

    response = await client.post(
        "/api/v1/documents/generate", headers=auth_headers, json={"document_id": doc_id}
    )
    assert response.status_code == 200

    stmt = select(ActivityJournalEntry).where(
        ActivityJournalEntry.clinic_id == test_clinic.id,
        ActivityJournalEntry.event_type == "document.generated",
    )
    rows = (await db_session.execute(stmt)).scalars().all()
    assert len(rows) == 1
    entry = rows[0]
    assert entry.source_table == "document"
    assert str(entry.source_entity_id) == doc_id
    assert entry.actor_id is not None
    assert entry.payload["title"] == "Referred to ortho"


@pytest.mark.asyncio
async def test_editing_a_generated_document_drops_its_pdf(
    client, auth_headers, test_clinic: Clinic, test_patient
) -> None:
    """The stored PDF never outlives the content it was rendered from (#1006)."""
    created = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        json={
            "patient_id": str(test_patient.id),
            "document_type": "medical_certificate",
            "title": "Sick leave",
            "content": {"diagnosis": "flu", "description": "5 days rest"},
        },
    )
    assert created.status_code == 201
    url = f"/api/v1/documents/{created.json()['data']['id']}"

    no_file = await client.patch(url, headers=auth_headers, json={"status": "generated"})
    assert no_file.status_code == 422, no_file.text

    generate = {"document_id": created.json()["data"]["id"]}
    assert (
        await client.post("/api/v1/documents/generate", headers=auth_headers, json=generate)
    ).status_code == 200

    # Re-sending what is stored keeps the file, also through archive and restore.
    for body in ({"title": "Sick leave"}, {"status": "archived"}, {"status": "generated"}):
        assert (await client.patch(url, headers=auth_headers, json=body)).status_code == 200
    assert (await client.get(f"{url}/download", headers=auth_headers)).status_code == 200

    edited = await client.patch(
        url,
        headers=auth_headers,
        json={"content": {"diagnosis": "flu", "description": "10 days rest"}},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["status"] == "draft"
    assert edited.json()["data"]["file_path"] is None
    assert (await client.get(f"{url}/download", headers=auth_headers)).status_code == 409

    assert (
        await client.post("/api/v1/documents/generate", headers=auth_headers, json=generate)
    ).status_code == 200
    stale = await client.patch(
        url, headers=auth_headers, json={"title": "Sick note", "status": "generated"}
    )
    assert stale.status_code == 422, stale.text
