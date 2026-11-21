"""Synthetic coverage for informed consent signing and retention."""

from __future__ import annotations

import base64
import hashlib
import io
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import delete, select

from app.config import settings
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


@pytest.fixture(autouse=True)
def synthetic_public_origin(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://clinic.example")


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
async def test_consent_access_log_distinguishes_view_and_download(
    client, auth_headers, test_patient, db_session
):
    doc = await new_consent(client, auth_headers, test_patient)
    token = await make_link(client, auth_headers, doc)
    signed = await client.post(
        "/api/v1/documents/public/consents/current/sign",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "signer_name": "Synthetic patient",
            "relationship_to_patient": "patient",
            "signature": signature(),
        },
    )
    assert signed.status_code == 200, signed.text
    before = {row.id for row in (await db_session.execute(select(PatientAccessLog))).scalars()}
    status = await client.get(
        "/api/v1/documents/consents/signature-status",
        params={"patient_id": str(test_patient.id)},
        headers=auth_headers,
    )
    assert status.status_code == 200
    status_rows = (await db_session.execute(select(PatientAccessLog))).scalars().all()
    assert any(row.resource == "documents" and row.action == "view" for row in status_rows)
    # Views of the same resource are deduplicated within a ten-minute window.
    await db_session.execute(delete(PatientAccessLog))
    await db_session.commit()
    evidence = await client.get(f"/api/v1/documents/consents/{doc}/evidence", headers=auth_headers)
    download = await client.get(
        f"/api/v1/documents/consents/{doc}/evidence/sign/download", headers=auth_headers
    )
    assert evidence.status_code == download.status_code == 200
    assert download.headers["content-disposition"].startswith("attachment;")
    rows = [
        row
        for row in (await db_session.execute(select(PatientAccessLog))).scalars()
        if row.id not in before
    ]
    assert sorted((row.resource, row.action) for row in rows) == [
        ("document_pdf", "download"),
        ("documents", "view"),
    ]
    assert all(row.patient_id == test_patient.id for row in rows)


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
    states = await client.get(
        "/api/v1/documents/consents/signature-status",
        headers=auth_headers,
        params={"patient_id": str(test_patient.id)},
    )
    assert next(item for item in states.json()["data"] if item["id"] == doc) == {
        "id": doc,
        "signed": True,
        "revoked": True,
    }
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
    status_for_foreign = await client.get(
        "/api/v1/documents/consents/signature-status",
        headers=auth_headers,
        params={"patient_id": str(patient.id)},
    )
    assert status_for_foreign.status_code == 404
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


@pytest.mark.asyncio
async def test_unsigned_consent_can_be_regenerated_and_edited_with_links_invalidated(
    client, auth_headers, test_patient
):
    doc = await new_consent(client, auth_headers, test_patient)
    first = await make_link(client, auth_headers, doc)
    second = await make_link(client, auth_headers, doc)
    statuses = await client.get(
        "/api/v1/documents/consents/signature-status",
        headers=auth_headers,
        params={"patient_id": str(test_patient.id)},
    )
    assert statuses.status_code == 200
    assert {row["id"]: row["signed"] for row in statuses.json()["data"]}[doc] is False
    # Generation without a signature is a preview and must not lock the consent.
    for _ in range(2):
        generated = await client.post(
            "/api/v1/documents/generate", headers=auth_headers, json={"document_id": doc}
        )
        assert generated.status_code == 200, generated.text
    preview = await client.get(f"/api/v1/documents/{doc}/download", headers=auth_headers)
    assert preview.status_code == 200 and preview.content.startswith(b"%PDF-")
    assert (
        await client.get(
            "/api/v1/documents/public/consents/current",
            headers={"Authorization": f"Bearer {first}"},
        )
    ).status_code == 200
    # Invalid content must not invalidate the existing link.
    invalid = await client.patch(
        f"/api/v1/documents/{doc}",
        headers=auth_headers,
        json={"content": {"text": "Synthetic", "signature": "https://invalid.example/"}},
    )
    assert invalid.status_code == 422
    assert (
        await client.get(
            "/api/v1/documents/public/consents/current",
            headers={"Authorization": f"Bearer {first}"},
        )
    ).status_code == 200
    edited = await client.patch(
        f"/api/v1/documents/{doc}",
        headers=auth_headers,
        json={"title": "Updated consent", "content": {"text": "Updated synthetic text"}},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["status"] == "draft"
    assert (
        await client.get(f"/api/v1/documents/{doc}/download", headers=auth_headers)
    ).status_code == 409
    payload = {
        "signer_name": "Synthetic patient",
        "relationship_to_patient": "patient",
        "signature": signature(),
    }
    for token in (first, second):
        headers = {"Authorization": f"Bearer {token}"}
        assert (
            await client.get("/api/v1/documents/public/consents/current", headers=headers)
        ).status_code == 404
        assert (
            await client.post(
                "/api/v1/documents/public/consents/current/sign", headers=headers, json=payload
            )
        ).status_code == 404
    fresh = await make_link(client, auth_headers, doc)
    data = await client.get(
        "/api/v1/documents/public/consents/current", headers={"Authorization": f"Bearer {fresh}"}
    )
    assert data.json()["data"]["text"] == "Updated synthetic text"
    assert (
        await client.post(
            "/api/v1/documents/public/consents/current/sign",
            headers={"Authorization": f"Bearer {fresh}"},
            json=payload,
        )
    ).status_code == 200
    statuses = await client.get(
        "/api/v1/documents/consents/signature-status",
        headers=auth_headers,
        params={"patient_id": str(test_patient.id)},
    )
    assert {row["id"]: row["signed"] for row in statuses.json()["data"]}[doc] is True
    for method, path, kwargs in [
        ("patch", f"/api/v1/documents/{doc}", {"json": {"title": "Another title"}}),
        ("delete", f"/api/v1/documents/{doc}", {}),
        ("post", "/api/v1/documents/generate", {"json": {"document_id": doc}}),
    ]:
        assert (
            await getattr(client, method)(path, headers=auth_headers, **kwargs)
        ).status_code == 409


@pytest.mark.asyncio
async def test_archiving_unsigned_consent_invalidates_links_and_disallows_new_ones(
    client, auth_headers, test_patient
):
    for archive_via_patch in (False, True):
        doc = await new_consent(client, auth_headers, test_patient)
        token = await make_link(client, auth_headers, doc)
        if archive_via_patch:
            result = await client.patch(
                f"/api/v1/documents/{doc}", headers=auth_headers, json={"status": "archived"}
            )
            assert result.status_code == 200
        else:
            assert (
                await client.delete(f"/api/v1/documents/{doc}", headers=auth_headers)
            ).status_code == 204
        assert (
            await client.get(
                "/api/v1/documents/public/consents/current",
                headers={"Authorization": f"Bearer {token}"},
            )
        ).status_code == 404
        assert (
            await client.post(
                f"/api/v1/documents/consents/{doc}/links?purpose=sign", headers=auth_headers
            )
        ).status_code == 409
        generated = await client.post(
            "/api/v1/documents/generate", headers=auth_headers, json={"document_id": doc}
        )
        assert generated.status_code == 200
        assert generated.json()["data"]["status"] == "archived"
        assert (
            await client.get(
                "/api/v1/documents/public/consents/current",
                headers={"Authorization": f"Bearer {token}"},
            )
        ).status_code == 404


@pytest.mark.asyncio
async def test_signed_evidence_blocks_changes_even_if_status_is_draft(
    client, auth_headers, test_patient, db_session
):
    doc = await new_consent(client, auth_headers, test_patient)
    token = await make_link(client, auth_headers, doc)
    result = await client.post(
        "/api/v1/documents/public/consents/current/sign",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "signer_name": "Synthetic",
            "relationship_to_patient": "patient",
            "signature": signature(),
        },
    )
    assert result.status_code == 200
    row = (
        await db_session.execute(select(GeneratedDocument).where(GeneratedDocument.id == UUID(doc)))
    ).scalar_one()
    row.status = "draft"
    await db_session.flush()
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


@pytest.mark.asyncio
async def test_edit_and_sign_are_serialized(client, auth_headers, test_patient, db_session):
    import asyncio

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import settings
    from app.database import get_db
    from app.main import app

    doc = await new_consent(client, auth_headers, test_patient)
    token = await make_link(client, auth_headers, doc)
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
            edited, signed = await asyncio.gather(
                ac.patch(
                    f"/api/v1/documents/{doc}",
                    headers=auth_headers,
                    json={"content": {"text": "Edited synthetic text"}},
                ),
                ac.post(
                    "/api/v1/documents/public/consents/current/sign",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "signer_name": "Synthetic",
                        "relationship_to_patient": "patient",
                        "signature": signature(),
                    },
                ),
            )
        if signed.status_code == 200:
            assert edited.status_code == 409
        else:
            assert edited.status_code == 200
            assert signed.status_code in (404, 409)
        assert (signed.status_code == 200) != (edited.status_code == 200)
        db_session.expire_all()
        current = (
            await db_session.execute(
                select(GeneratedDocument).where(GeneratedDocument.id == UUID(doc))
            )
        ).scalar_one()
        assert current.content["text"] == (
            "Synthetic treatment text" if signed.status_code == 200 else "Edited synthetic text"
        )
    finally:
        app.dependency_overrides[get_db] = old_override
        await engine.dispose()


@pytest.mark.asyncio
async def test_racing_public_view_does_not_show_edited_text(
    client, auth_headers, test_patient, db_session, monkeypatch
):
    import asyncio

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import settings
    from app.database import get_db
    from app.main import app
    from app.modules.documents import consent_service as consent_module
    from app.modules.documents.service import DocumentService

    doc = await new_consent(client, auth_headers, test_patient)
    token = await make_link(client, auth_headers, doc)
    clinic_id = test_patient.clinic_id
    await db_session.commit()
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    old_override = app.dependency_overrides[get_db]
    link_loaded = asyncio.Event()
    original_link = consent_module._link

    async def observed_link(db, token):
        link = await original_link(db, token)
        link_loaded.set()
        return link

    async def per_request_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    monkeypatch.setattr(consent_module, "_link", observed_link)
    app.dependency_overrides[get_db] = per_request_db
    try:
        async with (
            factory() as editing,
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac,
        ):
            await editing.execute(
                select(GeneratedDocument).where(GeneratedDocument.id == UUID(doc)).with_for_update()
            )
            view = asyncio.create_task(
                ac.get(
                    "/api/v1/documents/public/consents/current",
                    headers={"Authorization": f"Bearer {token}"},
                )
            )
            await asyncio.wait_for(link_loaded.wait(), timeout=5)
            await DocumentService.update_document(
                editing, clinic_id, UUID(doc), content={"text": "Updated synthetic text"}
            )
            await editing.commit()
            response = await asyncio.wait_for(view, timeout=10)
            assert response.status_code == 404
            assert "Updated synthetic text" not in response.text
    finally:
        app.dependency_overrides[get_db] = old_override
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("locale", "heading", "guardian", "revocation"),
    [
        (
            "es",
            "Consentimiento informado",
            "Tutor legal",
            "El firmante revoca el consentimiento anterior.",
        ),
        ("en", "Informed consent", "Legal guardian", "The signer revokes the prior consent."),
    ],
)
async def test_signed_pdf_uses_link_locale_and_clinic_time(
    client, auth_headers, test_patient, db_session, locale, heading, guardian, revocation
):
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext is required to verify rendered PDF text")
    clinic = await db_session.get(Clinic, test_patient.clinic_id)
    clinic.timezone = "America/New_York"
    clinic.settings = {**(clinic.settings or {}), "communication_language": locale}
    await db_session.commit()
    doc = await new_consent(client, auth_headers, test_patient)
    token = await make_link(client, auth_headers, doc)
    link = (await db_session.execute(select(ConsentSigningLink))).scalar_one()
    assert link.locale == locale
    clinic.settings = {
        **clinic.settings,
        "communication_language": "en" if locale == "es" else "es",
    }
    await db_session.commit()
    response = await client.post(
        "/api/v1/documents/public/consents/current/sign",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "signer_name": "Synthetic guardian",
            "relationship_to_patient": "guardian",
            "signature": signature(),
        },
    )
    assert response.status_code == 200, response.text
    evidence = (await db_session.execute(select(ConsentEvidence))).scalar_one()
    from zoneinfo import ZoneInfo

    local_time = evidence.signed_at.astimezone(ZoneInfo("America/New_York")).strftime(
        "%d/%m/%Y %H:%M %Z"
    )
    pdf = await client.get(
        f"/api/v1/documents/consents/{doc}/evidence/sign/download", headers=auth_headers
    )
    text = subprocess.run(
        ["pdftotext", "-", "-"], input=pdf.content, capture_output=True, check=True
    ).stdout.decode()
    assert heading in text and guardian in text and local_time in text
    assert "· guardian ·" not in text
    clinic.settings = {**clinic.settings, "communication_language": locale}
    await db_session.commit()
    revoke_token = await make_link(client, auth_headers, doc, "revoke")
    revoked = await client.post(
        "/api/v1/documents/public/consents/current/sign",
        headers={"Authorization": f"Bearer {revoke_token}"},
        json={
            "signer_name": "Synthetic guardian",
            "relationship_to_patient": "guardian",
            "signature": signature(),
        },
    )
    assert revoked.status_code == 200, revoked.text
    pdf = await client.get(
        f"/api/v1/documents/consents/{doc}/evidence/revoke/download", headers=auth_headers
    )
    text = subprocess.run(
        ["pdftotext", "-", "-"], input=pdf.content, capture_output=True, check=True
    ).stdout.decode()
    assert revocation in " ".join(text.split())


@pytest.mark.asyncio
async def test_signing_link_validates_explicit_locale(
    client, auth_headers, test_patient, db_session
):
    doc = await new_consent(client, auth_headers, test_patient)
    response = await client.post(
        f"/api/v1/documents/consents/{doc}/links?purpose=sign&locale=en", headers=auth_headers
    )
    assert response.status_code == 201
    link = (await db_session.execute(select(ConsentSigningLink))).scalar_one()
    assert link.locale == "en"
    public = await client.get(
        "/api/v1/documents/public/consents/current",
        headers={"Authorization": f"Bearer {response.json()['data']['token']}"},
    )
    assert public.json()["data"]["locale"] == "en"  # the tablet page renders in it
    invalid = await client.post(
        f"/api/v1/documents/consents/{doc}/links?purpose=sign&locale=xx", headers=auth_headers
    )
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_link_returns_matching_fragment_url_and_png(
    client, auth_headers, test_patient, monkeypatch
):
    from app.modules.documents import consent_service

    seen = []
    real = consent_service._signing_qr

    def capture(url):
        seen.append(url)
        return real(url)

    monkeypatch.setattr(consent_service, "_signing_qr", capture)
    doc = await new_consent(client, auth_headers, test_patient)
    response = await client.post(
        f"/api/v1/documents/consents/{doc}/links?purpose=sign", headers=auth_headers
    )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    data = response.json()["data"]
    assert data["url"] == f"https://clinic.example/p/consent#{data['token']}"
    assert seen == [data["url"]]
    prefix = "data:image/png;base64,"
    assert data["qr_data_url"].startswith(prefix)
    image = Image.open(io.BytesIO(base64.b64decode(data["qr_data_url"][len(prefix) :])))
    assert image.format == "PNG" and image.width == image.height and image.width > 100


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_origin", ["", "not-an-origin", "https://[invalid"])
async def test_link_requires_configured_public_origin(
    client, auth_headers, test_patient, monkeypatch, invalid_origin
):
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", invalid_origin)
    doc = await new_consent(client, auth_headers, test_patient)
    response = await client.post(
        f"/api/v1/documents/consents/{doc}/links?purpose=sign", headers=auth_headers
    )
    assert response.status_code == 422
