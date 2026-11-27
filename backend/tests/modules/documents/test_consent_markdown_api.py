"""Public payload and PDF share one rendering of the consent body (#1171)."""

from __future__ import annotations

import base64
import io
import shutil
import subprocess

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select

from app.config import settings
from app.modules.documents.models import GeneratedDocument

MARKDOWN_BODY = (
    "# Procedure\n"
    "You will receive a **local anaesthetic** and *mild* sedation.\n"
    "Second line of the paragraph.\n\n"
    "## Risks\n"
    "- Swelling\n"
    "- Bleeding\n\n"
    "1. Rest\n"
    "2. Ice\n\n"
    "<script>alert('xss')</script> [not a link](javascript:alert(1))"
)
LEGACY_BODY = "Line one of a legacy body\n· bullet-like first\n· bullet-like second\nClosing line"


@pytest.fixture(autouse=True)
def synthetic_public_origin(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://clinic.example")


async def consent_with_body(client, auth_headers, patient, body):
    template = await client.post(
        "/api/v1/documents/consent-templates",
        headers=auth_headers,
        json={"title": "Synthetic consent", "body": body},
    )
    assert template.status_code == 201, template.text
    created = await client.post(
        "/api/v1/documents/consents",
        headers=auth_headers,
        json={"template_id": template.json()["data"]["id"], "patient_id": str(patient.id)},
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]["id"]


def signature() -> str:
    image = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    ImageDraw.Draw(image).line((2, 2, 35, 16), fill="black", width=2)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


async def make_link(client, headers, doc):
    response = await client.post(
        f"/api/v1/documents/consents/{doc}/links?purpose=sign", headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["token"]


async def sign(client, token):
    response = await client.post(
        "/api/v1/documents/public/consents/current/sign",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "signer_name": "Synthetic patient",
            "relationship_to_patient": "patient",
            "signature": signature(),
        },
    )
    assert response.status_code == 200, response.text


def pdf_text(content: bytes) -> str:
    return subprocess.run(
        ["pdftotext", "-layout", "-", "-"], input=content, capture_output=True, check=True
    ).stdout.decode()


@pytest.mark.asyncio
async def test_public_payload_has_sanitised_body_html(client, auth_headers, test_patient):
    doc = await consent_with_body(client, auth_headers, test_patient, MARKDOWN_BODY)
    token = await make_link(client, auth_headers, doc)
    response = await client.get(
        "/api/v1/documents/public/consents/current", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    html = data["body_html"]
    assert "<h2>Procedure</h2>" in html and "<h3>Risks</h3>" in html
    assert "<strong>local anaesthetic</strong>" in html and "<em>mild</em>" in html
    assert "<ul><li>Swelling</li><li>Bleeding</li></ul>" in html
    assert '<ol><li value="1">Rest</li><li value="2">Ice</li></ol>' in html
    assert "<script" not in html and "<a " not in html and "href" not in html
    assert "&lt;script&gt;" in html
    # The source text is unchanged; the page must render ``body_html`` only.
    assert data["text"] == MARKDOWN_BODY


@pytest.mark.asyncio
async def test_snapshot_keeps_source_text_and_payload_follows_it(
    client, auth_headers, test_patient, db_session
):
    doc = await consent_with_body(client, auth_headers, test_patient, "Before **edit**")
    stored = await db_session.get(GeneratedDocument, doc)
    assert stored.content["text"] == "Before **edit**"
    edit = await client.patch(
        f"/api/v1/documents/{doc}", headers=auth_headers, json={"content": {"text": "After *edit*"}}
    )
    assert edit.status_code == 200, edit.text
    token = await make_link(client, auth_headers, doc)
    data = (
        await client.get(
            "/api/v1/documents/public/consents/current",
            headers={"Authorization": f"Bearer {token}"},
        )
    ).json()["data"]
    assert data["body_html"] == "<p>After <em>edit</em></p>"
    stored = (await db_session.execute(select(GeneratedDocument))).scalars().first()
    await db_session.refresh(stored)
    assert stored.content["text"] == "After *edit*"


@pytest.mark.asyncio
async def test_signed_pdf_renders_the_same_markdown(client, auth_headers, test_patient):
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext is required to verify rendered PDF text")
    doc = await consent_with_body(client, auth_headers, test_patient, MARKDOWN_BODY)
    token = await make_link(client, auth_headers, doc)
    await sign(client, token)
    pdf = await client.get(
        f"/api/v1/documents/consents/{doc}/evidence/sign/download", headers=auth_headers
    )
    assert pdf.status_code == 200
    text = pdf_text(pdf.content)
    flat = " ".join(text.split())
    # Markers are consumed; the words remain.
    assert "Procedure" in text and "Risks" in text
    assert "# Procedure" not in flat and "## Risks" not in flat
    assert "**" not in flat and "*mild*" not in flat
    assert "local anaesthetic and mild sedation." in flat
    assert "Swelling" in text and "Bleeding" in text and "Rest" in text and "Ice" in text
    assert "- Swelling" not in flat
    # Unsafe markup is printed as text, not interpreted.
    assert "<script>alert('xss')</script>" in flat
    assert "[not a link](javascript:alert(1))" in flat


@pytest.mark.asyncio
async def test_legacy_plain_text_body_renders_line_for_line(client, auth_headers, test_patient):
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext is required to verify rendered PDF text")
    doc = await consent_with_body(client, auth_headers, test_patient, LEGACY_BODY)
    token = await make_link(client, auth_headers, doc)
    public = await client.get(
        "/api/v1/documents/public/consents/current", headers={"Authorization": f"Bearer {token}"}
    )
    assert public.json()["data"]["body_html"] == (
        "<p>Line one of a legacy body<br>· bullet-like first<br>"
        "· bullet-like second<br>Closing line</p>"
    )
    await sign(client, token)
    pdf = await client.get(
        f"/api/v1/documents/consents/{doc}/evidence/sign/download", headers=auth_headers
    )
    lines = [line.strip() for line in pdf_text(pdf.content).splitlines() if line.strip()]
    start = lines.index("Line one of a legacy body")
    assert lines[start : start + 4] == LEGACY_BODY.split("\n")


@pytest.mark.asyncio
async def test_signed_pdf_keeps_typed_list_numbers(client, auth_headers, test_patient):
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext is required to verify rendered PDF text")
    body = (
        "1. Procedure\n\nWe will extract the tooth.\n\n2. Risks\n\n"
        "Some swelling.\n\n3. Alternatives\n\nNothing.\n\nClosing words\n\n"
        "- x\n  7. Seventh\n  8. Eighth"
    )
    doc = await consent_with_body(client, auth_headers, test_patient, body)
    token = await make_link(client, auth_headers, doc)
    page = await client.get(
        "/api/v1/documents/public/consents/current", headers={"Authorization": f"Bearer {token}"}
    )
    assert 'value="2"' in page.json()["data"]["body_html"]
    await sign(client, token)
    pdf = await client.get(
        f"/api/v1/documents/consents/{doc}/evidence/sign/download", headers=auth_headers
    )
    assert pdf.status_code == 200
    flat = " ".join(pdf_text(pdf.content).split())
    assert "1. Procedure" in flat and "2. Risks" in flat and "3. Alternatives" in flat
    assert "7. Seventh" in flat and "8. Eighth" in flat


@pytest.mark.asyncio
async def test_deeply_nested_body_is_not_truncated_on_page_or_pdf(
    client, auth_headers, test_patient
):
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext is required to verify rendered PDF text")
    doc = await consent_with_body(
        client, auth_headers, test_patient, "- " * 10 + "deepest\n\nAFTERDEEP"
    )
    token = await make_link(client, auth_headers, doc)
    page = await client.get(
        "/api/v1/documents/public/consents/current", headers={"Authorization": f"Bearer {token}"}
    )
    assert "AFTERDEEP" in page.json()["data"]["body_html"]
    await sign(client, token)
    pdf = await client.get(
        f"/api/v1/documents/consents/{doc}/evidence/sign/download", headers=auth_headers
    )
    assert "AFTERDEEP" in pdf_text(pdf.content)
