"""Synthetic coverage for informed consent signing and retention."""

from __future__ import annotations

import base64
import hashlib
import io
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select

from app.core.auth.models import Clinic
from app.core.patient_access import PatientAccessLog
from app.modules.activity_journal.models import ActivityJournalEntry
from app.modules.documents.models import (
    ConsentEvidence,
    ConsentSigningLink,
    ConsentTemplate,
    GeneratedDocument,
)
from app.modules.patients.models import Patient


def signature() -> str:
    image = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    ImageDraw.Draw(image).line((2, 2, 35, 16), fill="black", width=2)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


async def new_consent(client, auth_headers, patient):
    template = await client.post(
        "/api/v1/documents/consent-templates",
        headers=auth_headers,
        json={"title": "Synthetic consent", "body": "Synthetic treatment text"},
    )
    assert template.status_code == 201, template.text
    created = await client.post(
        "/api/v1/documents/consents",
        headers=auth_headers,
        json={"template_id": template.json()["data"]["id"], "patient_id": str(patient.id)},
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]["id"]


async def make_link(client, headers, doc, purpose="sign"):
    response = await client.post(
        f"/api/v1/documents/consents/{doc}/links?purpose={purpose}", headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["token"]


@pytest.mark.asyncio
async def test_signed_pdf_immutable_representative_and_revocation(
    client, auth_headers, test_patient, db_session
):
    doc = await new_consent(client, auth_headers, test_patient)
    token = await make_link(client, auth_headers, doc)
    assert (await client.get("/api/v1/documents/public/consents/current")).status_code == 404
    public = await client.get(
        "/api/v1/documents/public/consents/current", headers={"Authorization": f"Bearer {token}"}
    )
    assert public.status_code == 200
    assert public.json()["data"]["text"] == "Synthetic treatment text"
    assert (
        await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 401
    payload = {
        "signer_name": "Synthetic guardian",
        "relationship_to_patient": "guardian",
        "signature": signature(),
    }
    response = await client.post(
        "/api/v1/documents/public/consents/current/sign",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 200, response.text
    journal = (
        (
            await db_session.execute(
                select(ActivityJournalEntry).where(
                    ActivityJournalEntry.event_type == "document.generated",
                    ActivityJournalEntry.clinic_id == test_patient.clinic_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(journal) == 1
    assert (
        await client.post(
            "/api/v1/documents/public/consents/current/sign",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
    ).status_code in (404, 409)
    assert (
        await client.get(
            "/api/v1/documents/public/consents/current",
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/documents/{doc}", headers=auth_headers, json={"title": "Changed"}
        )
    ).status_code == 409
    assert (
        await client.delete(f"/api/v1/documents/{doc}", headers=auth_headers)
    ).status_code == 409
    assert (
        await client.post(
            "/api/v1/documents/generate", headers=auth_headers, json={"document_id": doc}
        )
    ).status_code == 409
    pdf = await client.get(f"/api/v1/documents/{doc}/download", headers=auth_headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    evidence = await client.get(f"/api/v1/documents/consents/{doc}/evidence", headers=auth_headers)
    original = evidence.json()["data"][0]
    assert original["relationship_to_patient"] == "guardian"
    assert original["sha256"] == hashlib.sha256(pdf.content).hexdigest()
    signed_download = await client.get(
        f"/api/v1/documents/consents/{doc}/evidence/sign/download", headers=auth_headers
    )
    assert signed_download.status_code == 200 and signed_download.content == pdf.content
    if shutil.which("pdftotext"):
        text = subprocess.run(
            ["pdftotext", "-", "-"], input=pdf.content, capture_output=True, check=True
        ).stdout.decode()
        assert "Synthetic treatment text" in text
        assert "Synthetic guardian" in text
    if shutil.which("pdfimages"):
        images = (
            subprocess.run(
                ["pdfimages", "-list", "-"], input=pdf.content, capture_output=True, check=True
            )
            .stdout.decode()
            .splitlines()
        )
        assert len(images) > 2, "signed PDF must contain the drawn signature image"
    revoke = await make_link(client, auth_headers, doc, "revoke")
    assert (
        await client.post(
            "/api/v1/documents/public/consents/current/sign",
            headers={"Authorization": f"Bearer {revoke}"},
            json=payload,
        )
    ).status_code == 200
    assert (
        await client.get(f"/api/v1/documents/{doc}/download", headers=auth_headers)
    ).content == pdf.content
    rev_pdf = await client.get(
        f"/api/v1/documents/consents/{doc}/evidence/revoke/download", headers=auth_headers
    )
    assert rev_pdf.status_code == 200 and rev_pdf.content != pdf.content
    evidence = (
        await client.get(f"/api/v1/documents/consents/{doc}/evidence", headers=auth_headers)
    ).json()["data"]
    assert {e["purpose"] for e in evidence} == {"sign", "revoke"}
    assert (
        next(e for e in evidence if e["purpose"] == "revoke")["sha256"]
        == hashlib.sha256(rev_pdf.content).hexdigest()
    )
    rows = (await db_session.execute(select(ConsentEvidence))).scalars().all()
    assert all(row.signed_at and row.user_agent and row.ip_address for row in rows)
    access = (await db_session.execute(select(PatientAccessLog))).scalars().all()
    assert any(
        row.patient_id == test_patient.id and row.resource == "documents" and row.action == "view"
        for row in access
    )
    assert (
        sum(
            row.patient_id == test_patient.id
            and row.resource == "document_pdf"
            and row.action == "download"
            for row in access
        )
        == 4
    )
    assert any(
        row.patient_id == test_patient.id
        and row.resource == "document_pdf"
        and row.action == "download"
        for row in access
    )


@pytest.mark.asyncio
async def test_expired_link_and_clinic_isolation(client, auth_headers, test_patient, db_session):
    doc = await new_consent(client, auth_headers, test_patient)
    token = await make_link(client, auth_headers, doc)
    link = (await db_session.execute(select(ConsentSigningLink))).scalar_one()
    link.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    assert (
        await client.get(
            "/api/v1/documents/public/consents/current",
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 404
    assert (
        await client.post(
            "/api/v1/documents/public/consents/current/sign",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "signer_name": "Synthetic",
                "relationship_to_patient": "patient",
                "signature": signature(),
            },
        )
    ).status_code == 404
    foreign = Clinic(id=uuid4(), name="Other synthetic clinic", tax_id="B87654321")
    db_session.add(foreign)
    await db_session.flush()
    patient = Patient(id=uuid4(), clinic_id=foreign.id, first_name="Foreign", last_name="Synthetic")
    db_session.add(patient)
    foreign_template = ConsentTemplate(
        id=uuid4(), clinic_id=foreign.id, title="Foreign", body="Foreign text"
    )
    db_session.add(foreign_template)
    await db_session.flush()
    foreign_doc = GeneratedDocument(
        id=uuid4(),
        clinic_id=foreign.id,
        patient_id=patient.id,
        document_type="informed_consent",
        title="Foreign",
        status="draft",
        content={"text": "Synthetic"},
    )
    db_session.add(foreign_doc)
    await db_session.commit()
    assert (
        await client.get(
            f"/api/v1/documents/consents/{foreign_doc.id}/evidence", headers=auth_headers
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/documents/consents/{foreign_doc.id}/evidence/sign/download",
            headers=auth_headers,
        )
    ).status_code == 404
    foreign_access = (
        (
            await db_session.execute(
                select(PatientAccessLog).where(PatientAccessLog.patient_id == patient.id)
            )
        )
        .scalars()
        .all()
    )
    assert not foreign_access
    template = await client.post(
        "/api/v1/documents/consent-templates",
        headers=auth_headers,
        json={"title": "Synthetic", "body": "Synthetic"},
    )
    response = await client.post(
        "/api/v1/documents/consents",
        headers=auth_headers,
        json={"template_id": template.json()["data"]["id"], "patient_id": str(patient.id)},
    )
    assert response.status_code == 404
    response = await client.post(
        "/api/v1/documents/consents",
        headers=auth_headers,
        json={"template_id": str(foreign_template.id), "patient_id": str(test_patient.id)},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_blank_signature_is_rejected_without_consuming_link(
    client, auth_headers, test_patient
):
    doc = await new_consent(client, auth_headers, test_patient)
    token = await make_link(client, auth_headers, doc)
    image = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    blank = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    payload = {"signer_name": "Synthetic", "relationship_to_patient": "patient", "signature": blank}
    assert (
        await client.post(
            "/api/v1/documents/public/consents/current/sign",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
    ).status_code == 422
    assert (
        await client.get(
            "/api/v1/documents/public/consents/current",
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_competing_links_can_sign_only_once(client, auth_headers, test_patient, db_session):
    import asyncio

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import settings
    from app.database import get_db
    from app.main import app

    doc = await new_consent(client, auth_headers, test_patient)
    first = await make_link(client, auth_headers, doc)
    second = await make_link(client, auth_headers, doc)
    await db_session.commit()
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    old_override = app.dependency_overrides[get_db]

    async def per_request_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = per_request_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "signer_name": "Synthetic patient",
                "relationship_to_patient": "patient",
                "signature": signature(),
            }
            responses = await asyncio.gather(
                *[
                    ac.post(
                        "/api/v1/documents/public/consents/current/sign",
                        headers={"Authorization": f"Bearer {token}"},
                        json=payload,
                    )
                    for token in (first, second)
                ]
            )
        assert sorted(r.status_code for r in responses) == [200, 409]
    finally:
        app.dependency_overrides[get_db] = old_override
        await engine.dispose()


@pytest.mark.asyncio
async def test_changed_pdf_is_not_served(client, auth_headers, test_patient, db_session):
    from app.modules.documents.service import _documents_root

    doc = await new_consent(client, auth_headers, test_patient)
    token = await make_link(client, auth_headers, doc)
    response = await client.post(
        "/api/v1/documents/public/consents/current/sign",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "signer_name": "Synthetic",
            "relationship_to_patient": "patient",
            "signature": signature(),
        },
    )
    assert response.status_code == 200
    evidence = (await db_session.execute(select(ConsentEvidence))).scalar_one()
    target = _documents_root() / str(evidence.clinic_id) / f"consent-{evidence.id}.pdf"
    target.write_bytes(b"%PDF-synthetic-changed")
    assert (
        await client.get(f"/api/v1/documents/{doc}/download", headers=auth_headers)
    ).status_code == 409
    assert (
        await client.get(
            f"/api/v1/documents/consents/{doc}/evidence/sign/download", headers=auth_headers
        )
    ).status_code == 409
