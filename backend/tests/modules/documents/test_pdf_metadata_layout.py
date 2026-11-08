"""Verify rendered document metadata is not clipped."""

import shutil
import subprocess
from types import SimpleNamespace as N

import pytest

from app.modules.documents.pdf import DocumentPDFService


@pytest.mark.parametrize("locale", ["en", "ar"])
def test_generated_document_keeps_patient_and_issuer_visible(locale):
    if not shutil.which("pdftotext"):
        pytest.skip("poppler pdftotext is not installed")
    clinic = N(
        name="Example Dental Clinic",
        address=None,
        phone="",
        email="",
        tax_id="",
        settings={},
        timezone="UTC",
    )
    patient = N(first_name="Fictional", last_name="Patient", id="TEST-123", date_of_birth=None)
    document = N(
        document_type="medical_certificate",
        content={"diagnosis": "Fictional", "description": "Sample"},
    )
    html = DocumentPDFService._generate_html(document, clinic, patient, locale, "Test Doctor")
    if locale == "ar":
        assert 'dir="rtl"' in html
    pdf = DocumentPDFService._html_to_pdf(html)
    assert pdf.startswith(b"%PDF")
    out = subprocess.run(
        ["pdftotext", "-layout", "-", "-"], input=pdf, capture_output=True, check=True
    ).stdout.decode("utf-8")
    assert "Test Doctor" in out
    assert "Fictional Patient" in out
    assert "TEST-123" in out
    if locale == "ar":
        assert any("\u0600" <= char <= "\u06ff" for char in out)
