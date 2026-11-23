"""The consent PDF prints the title the patient saw and signed (#1040)."""

from types import SimpleNamespace as N

import pytest

from app.modules.documents.pdf import DocumentPDFService


@pytest.mark.parametrize("purpose", ["sign", "revoke"])
def test_consent_pdf_prints_its_escaped_title(purpose):
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
        document_type="informed_consent",
        title="Implant surgery <tooth 36>",
        content={"text": "Synthetic text", "purpose": purpose},
    )
    html = DocumentPDFService._generate_html(document, clinic, patient, "en", "")
    assert "Implant surgery &lt;tooth 36&gt;" in html
