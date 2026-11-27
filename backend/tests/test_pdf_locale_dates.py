"""PDF dates follow the locale's own order and separators (#1180).

Invoice, quote, document and purchase-order PDFs printed a fixed
``dd/mm/yyyy``: a Hungarian invoice read ``26/11/2026`` instead of
``2026. 11. 26.``. Pure HTML builders, no DB and no WeasyPrint.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace as N
from uuid import uuid4

import pytest

from app.core.pdf_locales import (
    DATE_FORMAT_BY_LANG,
    PDF_LOCALES,
    format_pdf_date,
    format_pdf_datetime,
)
from app.modules.billing.pdf import InvoicePDFService
from app.modules.budget.pdf import BudgetPDFService
from app.modules.documents.pdf import DocumentPDFService
from app.modules.prescriptions.pdf import build_pdf_data
from app.modules.purchase_orders.pdf import PurchaseOrderPDFService

DAY = date(2026, 11, 26)
EXPECTED = {
    "hu": "2026. 11. 26.",
    "de": "26.11.2026",
    "pl": "26.11.2026",
    "es": "26/11/2026",
    "en": "26/11/2026",
}


def test_every_pdf_locale_has_a_date_format() -> None:
    assert set(DATE_FORMAT_BY_LANG) == set(PDF_LOCALES)


@pytest.mark.parametrize(("locale", "expected"), EXPECTED.items())
def test_helper_formats(locale: str, expected: str) -> None:
    assert format_pdf_date(DAY, locale) == expected
    assert format_pdf_datetime(datetime(2026, 11, 26, 9, 5), locale) == f"{expected} 09:05"


def _clinic() -> N:
    return N(
        id=uuid4(),
        name="Test Clinic",
        tax_id="B1",
        address={},
        settings={},
        currency="EUR",
        timezone="Europe/Budapest",
        phone="",
        email="",
    )


def _invoice() -> N:
    from app.modules.billing.models import Invoice

    return Invoice(
        id=uuid4(),
        clinic_id=uuid4(),
        status="issued",
        billing_name="A B",
        invoice_number="FAC-2026-0001",
        issue_date=DAY,
        due_date=date(2026, 12, 26),
        subtotal=Decimal("0"),
        total_discount=Decimal("0"),
        total_tax=Decimal("0"),
        total=Decimal("0"),
    )


@pytest.mark.parametrize(("locale", "expected"), EXPECTED.items())
def test_invoice_dates_follow_the_locale(locale: str, expected: str) -> None:
    html = InvoicePDFService._generate_html(_invoice(), _clinic(), is_preview=False, locale=locale)
    assert expected in html
    # The due date too: the footer prints "now", which may be the issue day.
    assert format_pdf_date(date(2026, 12, 26), locale) in html
    if locale in ("hu", "de", "pl"):
        assert "26/11/2026" not in html


def _budget() -> N:
    return N(
        budget_number="P-1",
        version=1,
        status="accepted",
        created_at=datetime(2026, 11, 26, 10, 0, tzinfo=UTC),
        valid_from=DAY,
        valid_until=date(2026, 12, 31),
        global_discount_type=None,
        global_discount_value=None,
        items=[],
        patient=N(first_name="A", last_name="B"),
        assigned_professional=None,
        subtotal=Decimal("0"),
        total=Decimal("0"),
        total_tax=Decimal("0"),
        total_discount=Decimal("0"),
        patient_notes=None,
    )


def test_hungarian_quote_dates() -> None:
    signature = N(
        signature_data=None,
        signed_at=datetime(2026, 11, 26, 13, 30, tzinfo=UTC),
        signature_method="click_accept",
        signed_by_name="A B",
        document_hash="0" * 64,
    )
    html = BudgetPDFService._generate_html(
        _budget(), _clinic(), is_preview=False, locale="hu", signature=signature
    )
    assert "2026. 11. 26." in html  # created / valid from
    assert "2026. 12. 31." in html  # valid until
    assert "2026. 11. 26. 14:30" in html  # signed at, in Europe/Budapest
    assert "26/11/2026" not in html


def test_hungarian_document_birth_date() -> None:
    patient = N(first_name="A", last_name="B", id="P-1", date_of_birth=date(1980, 3, 7))
    document = N(document_type="informed_consent", title="T", content={"text": "x"})
    html = DocumentPDFService._generate_html(document, _clinic(), patient, "hu", "Dr")
    assert "1980. 03. 07." in html
    assert "07/03/1980" not in html


def test_german_purchase_order_dates() -> None:
    response = {
        "id": uuid4(),
        "status": "sent",
        "supplier_name": "S",
        "lines": [],
        "notes": None,
        "expected_date": date(2026, 12, 1),
        "created_at": datetime(2026, 11, 26, 8, 0, tzinfo=UTC),
    }
    html = PurchaseOrderPDFService._generate_html(response, _clinic(), "de")
    assert "26.11.2026" in html
    assert "01.12.2026" in html
    assert "26/11/2026" not in html


def test_prescription_uses_the_shared_format() -> None:
    prescription = N(
        status="issued",
        issued_at=datetime(2026, 11, 26, 10, 0, tzinfo=UTC),
        prescriber_name="Dr",
        license_number="1",
        notes=None,
    )
    data = build_pdf_data(prescription, [], "A B", {"timezone": "UTC"}, locale="hu")
    assert data["date"] == "2026. 11. 26."
