"""Tests for media module endpoints."""

from datetime import UTC, datetime
from io import BytesIO
from urllib.parse import unquote
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.core.patient_access import PatientAccessLog
from app.modules.patients.models import Patient


@pytest.fixture
async def media_setup(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> dict:
    """Set up clinic and patient for media tests."""
    # Get user from /me endpoint
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = response.json()["data"]["user"]["id"]

    # Create clinic
    clinic = Clinic(
        id=uuid4(),
        name="Media Test Clinic",
        tax_id="B87654321",
        address={"street": "Test St", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(clinic)
    await db_session.flush()

    # Create admin membership
    membership = ClinicMembership(
        id=uuid4(),
        user_id=user_id,
        clinic_id=clinic.id,
        role="admin",
    )
    db_session.add(membership)

    # Create patient
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Test",
        last_name="Patient",
        phone="+34666000000",
    )
    db_session.add(patient)
    await db_session.commit()

    return {
        "clinic_id": str(clinic.id),
        "user_id": user_id,
        "patient_id": str(patient.id),
    }


def create_pdf_file() -> BytesIO:
    """Create a minimal valid PDF file for testing."""
    # Minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [] /Count 0 >>
endobj
xref
0 3
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
trailer
<< /Size 3 /Root 1 0 R >>
startxref
115
%%EOF"""
    return BytesIO(pdf_content)


@pytest.mark.asyncio
async def test_upload_document(
    client: AsyncClient, auth_headers: dict[str, str], media_setup: dict
) -> None:
    """Test uploading a document."""
    patient_id = media_setup["patient_id"]

    pdf_file = create_pdf_file()

    response = await client.post(
        f"/api/v1/media/patients/{patient_id}/documents",
        headers=auth_headers,
        files={"file": ("test_consent.pdf", pdf_file, "application/pdf")},
        data={
            "document_type": "consent",
            "title": "Consentimiento Informado",
            "description": "Consent form for treatment",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "Consentimiento Informado"
    assert data["document_type"] == "consent"
    assert data["original_filename"] == "test_consent.pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_upload_invalid_mime_type(
    client: AsyncClient, auth_headers: dict[str, str], media_setup: dict
) -> None:
    """Test uploading a file with invalid MIME type."""
    patient_id = media_setup["patient_id"]

    response = await client.post(
        f"/api/v1/media/patients/{patient_id}/documents",
        headers=auth_headers,
        files={"file": ("test.exe", BytesIO(b"MZ..."), "application/x-msdownload")},
        data={
            "document_type": "other",
            "title": "Bad File",
        },
    )

    assert response.status_code == 400
    body = response.json()
    # HTTPException returns detail field
    assert "not allowed" in body.get("detail", body.get("message", ""))


@pytest.mark.asyncio
async def test_list_patient_documents(
    client: AsyncClient, auth_headers: dict[str, str], media_setup: dict
) -> None:
    """Test listing documents for a patient."""
    patient_id = media_setup["patient_id"]

    # Upload a document first
    pdf_file = create_pdf_file()
    await client.post(
        f"/api/v1/media/patients/{patient_id}/documents",
        headers=auth_headers,
        files={"file": ("doc1.pdf", pdf_file, "application/pdf")},
        data={"document_type": "consent", "title": "Doc 1"},
    )

    # List documents
    response = await client.get(
        f"/api/v1/media/patients/{patient_id}/documents",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["data"]) >= 1


@pytest.mark.asyncio
async def test_list_documents_filter_by_type(
    client: AsyncClient, auth_headers: dict[str, str], media_setup: dict
) -> None:
    """Test filtering documents by type."""
    patient_id = media_setup["patient_id"]

    # Upload consent document
    pdf_file1 = create_pdf_file()
    await client.post(
        f"/api/v1/media/patients/{patient_id}/documents",
        headers=auth_headers,
        files={"file": ("consent.pdf", pdf_file1, "application/pdf")},
        data={"document_type": "consent", "title": "Consent"},
    )

    # Upload insurance document
    pdf_file2 = create_pdf_file()
    await client.post(
        f"/api/v1/media/patients/{patient_id}/documents",
        headers=auth_headers,
        files={"file": ("insurance.pdf", pdf_file2, "application/pdf")},
        data={"document_type": "insurance", "title": "Insurance"},
    )

    # Filter by consent type
    response = await client.get(
        f"/api/v1/media/patients/{patient_id}/documents?document_type=consent",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    for doc in data["data"]:
        assert doc["document_type"] == "consent"


@pytest.mark.asyncio
async def test_get_document(
    client: AsyncClient, auth_headers: dict[str, str], media_setup: dict
) -> None:
    """Test getting a single document."""
    patient_id = media_setup["patient_id"]

    # Upload a document first
    pdf_file = create_pdf_file()
    upload_response = await client.post(
        f"/api/v1/media/patients/{patient_id}/documents",
        headers=auth_headers,
        files={"file": ("test.pdf", pdf_file, "application/pdf")},
        data={"document_type": "report", "title": "Test Report"},
    )
    document_id = upload_response.json()["data"]["id"]

    # Get document
    response = await client.get(
        f"/api/v1/media/documents/{document_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == document_id
    assert data["title"] == "Test Report"


@pytest.mark.asyncio
async def test_download_document(
    client: AsyncClient,
    auth_headers: dict[str, str],
    media_setup: dict,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Viewer requests coalesce as views and explicit downloads stay separate."""

    class FrozenClock:
        @staticmethod
        def now(tz):
            return datetime(2026, 11, 19, 12, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr("app.core.patient_access.datetime", FrozenClock)
    patient_id = media_setup["patient_id"]

    # Upload a document first
    pdf_file = create_pdf_file()
    original_content = pdf_file.getvalue()
    pdf_file.seek(0)

    upload_response = await client.post(
        f"/api/v1/media/patients/{patient_id}/documents",
        headers=auth_headers,
        files={"file": ("download_test.pdf", pdf_file, "application/pdf")},
        data={"document_type": "other", "title": "Download Test"},
    )
    document_id = upload_response.json()["data"]["id"]

    path = f"/api/v1/media/documents/{document_id}/download"
    for _ in range(2):
        viewed = await client.get(path, headers=auth_headers)
        assert viewed.status_code == 200
        assert "attachment" in viewed.headers["content-disposition"]
        assert viewed.content == original_content

        downloaded = await client.get(path, params={"variant": "full"}, headers=auth_headers)
        assert downloaded.status_code == 200
        assert downloaded.headers["content-type"] == "application/pdf"
        assert "attachment" in downloaded.headers["content-disposition"]
        assert downloaded.content == original_content

    actions = await db_session.scalars(
        select(PatientAccessLog.action).where(PatientAccessLog.resource == "documents")
    )
    assert sorted(actions.all()) == ["download", "download", "view"]


@pytest.mark.asyncio
async def test_update_document(
    client: AsyncClient, auth_headers: dict[str, str], media_setup: dict
) -> None:
    """Test updating document metadata."""
    patient_id = media_setup["patient_id"]

    # Upload a document first
    pdf_file = create_pdf_file()
    upload_response = await client.post(
        f"/api/v1/media/patients/{patient_id}/documents",
        headers=auth_headers,
        files={"file": ("update_test.pdf", pdf_file, "application/pdf")},
        data={"document_type": "other", "title": "Original Title"},
    )
    document_id = upload_response.json()["data"]["id"]

    # Update document
    response = await client.put(
        f"/api/v1/media/documents/{document_id}",
        headers=auth_headers,
        json={
            "title": "Updated Title",
            "description": "Added description",
            "document_type": "report",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "Updated Title"
    assert data["description"] == "Added description"
    assert data["document_type"] == "report"

    # Emptying the description in the edit modal sends null: it must clear it
    # (#743), while omitted fields stay as they are.
    response = await client.put(
        f"/api/v1/media/documents/{document_id}",
        headers=auth_headers,
        json={"title": "Updated Title", "description": None},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["description"] is None
    assert data["document_type"] == "report"


@pytest.mark.asyncio
async def test_delete_document(
    client: AsyncClient, auth_headers: dict[str, str], media_setup: dict
) -> None:
    """Test soft-deleting a document."""
    patient_id = media_setup["patient_id"]

    # Upload a document first
    pdf_file = create_pdf_file()
    upload_response = await client.post(
        f"/api/v1/media/patients/{patient_id}/documents",
        headers=auth_headers,
        files={"file": ("delete_test.pdf", pdf_file, "application/pdf")},
        data={"document_type": "other", "title": "To Delete"},
    )
    document_id = upload_response.json()["data"]["id"]

    # Delete document
    response = await client.delete(
        f"/api/v1/media/documents/{document_id}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    # Verify document is not in list anymore
    list_response = await client.get(
        f"/api/v1/media/patients/{patient_id}/documents",
        headers=auth_headers,
    )
    doc_ids = [d["id"] for d in list_response.json()["data"]]
    assert document_id not in doc_ids


@pytest.mark.asyncio
async def test_cross_clinic_access_denied(
    client: AsyncClient, db_session: AsyncSession, auth_headers: dict[str, str], media_setup: dict
) -> None:
    """Test that documents from another clinic return 404."""
    # Create another clinic with its own patient
    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="X99999999",
        settings={},
    )
    db_session.add(other_clinic)
    await db_session.flush()

    other_patient = Patient(
        id=uuid4(),
        clinic_id=other_clinic.id,
        first_name="Other",
        last_name="Patient",
    )
    db_session.add(other_patient)
    await db_session.commit()

    # Try to upload to other clinic's patient
    pdf_file = create_pdf_file()
    response = await client.post(
        f"/api/v1/media/patients/{other_patient.id}/documents",
        headers=auth_headers,
        files={"file": ("test.pdf", pdf_file, "application/pdf")},
        data={"document_type": "other", "title": "Test"},
    )

    # Should return 404 (patient not found in user's clinic)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_document_not_found(
    client: AsyncClient, auth_headers: dict[str, str], media_setup: dict
) -> None:
    """Test accessing non-existent document."""
    fake_id = str(uuid4())

    response = await client.get(
        f"/api/v1/media/documents/{fake_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_document_type(
    client: AsyncClient, auth_headers: dict[str, str], media_setup: dict
) -> None:
    """Test uploading with invalid document type."""
    patient_id = media_setup["patient_id"]

    pdf_file = create_pdf_file()
    response = await client.post(
        f"/api/v1/media/patients/{patient_id}/documents",
        headers=auth_headers,
        files={"file": ("test.pdf", pdf_file, "application/pdf")},
        data={
            "document_type": "invalid_type",
            "title": "Test",
        },
    )

    assert response.status_code == 400
    body = response.json()
    # HTTPException returns detail field
    assert "Invalid document type" in body.get("detail", body.get("message", ""))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name", ["őr.pdf", "Informe – 2026.pdf", "रिपोर्ट.pdf", "García.pdf", "test.pdf"]
)
async def test_download_with_a_unicode_filename(
    client: AsyncClient, auth_headers: dict[str, str], media_setup: dict, name: str
) -> None:
    """A filename outside latin-1 downloads instead of failing in the header (#1015)."""
    uploaded = await client.post(
        f"/api/v1/media/patients/{media_setup['patient_id']}/documents",
        headers=auth_headers,
        files={"file": (name, create_pdf_file(), "application/pdf")},
        data={"document_type": "other", "title": "Report"},
    )
    assert uploaded.status_code == 201, uploaded.text

    got = await client.get(
        f"/api/v1/media/documents/{uploaded.json()['data']['id']}/download", headers=auth_headers
    )
    assert got.status_code == 200
    header = got.headers["content-disposition"]
    assert header.isascii()
    if name.isascii():
        assert header == f'attachment; filename="{name}"'
    else:
        assert unquote(header.split("filename*=UTF-8''")[1]) == name
