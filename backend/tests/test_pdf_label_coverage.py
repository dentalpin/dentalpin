"""Every accepted PDF locale must have its own labels (#485).

``PDF_LOCALES`` is what the endpoints accept, so a module that only
translates ``es``/``en`` answers 200 with a document in the wrong
language — worse than the 422 #422 and #441 fixed, because nothing
signals it. These guards fail when a locale is added to the host
without the PDF label sets following.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.auth.models import Clinic
from app.core.pdf_locales import PDF_LOCALES
from app.modules.billing.pdf import InvoicePDFService
from app.modules.budget.models import Budget, BudgetItem
from app.modules.budget.pdf import BudgetPDFService
from app.modules.catalog.models import TreatmentCatalogItem
from app.modules.documents.models import GeneratedDocument
from app.modules.documents.pdf import _LABELS as DOC_LABELS
from app.modules.documents.pdf import DocumentPDFService
from app.modules.patients.models import Patient
from app.modules.prescriptions.pdf import _get_labels as rx_labels
from app.modules.purchase_orders.pdf import _LABELS as PO_LABELS

BUDGET_HEADINGS = {
    "es": "Presupuesto",
    "en": "Quote",
    "fr": "Devis",
    "pt": "Orçamento",
    "de": "Kostenvoranschlag",
    "hu": "Árajánlat",
    "pl": "Kosztorys",
    "it": "Preventivo",
    "ar": "عرض أسعار",
    "ta": "மதிப்பீடு",
    "hi": "उपचार अनुमान",
}


def _budget() -> Budget:
    budget = Budget(
        id=uuid4(),
        clinic_id=uuid4(),
        patient_id=uuid4(),
        budget_number="PRES-2026-0001",
        version=1,
        status="sent",
        valid_from=date(2026, 9, 20),
        valid_until=date(2026, 10, 20),
        created_by=uuid4(),
        subtotal=Decimal("60.00"),
        total_discount=Decimal("0.00"),
        total_tax=Decimal("0.00"),
        total=Decimal("60.00"),
        created_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
    )
    item = BudgetItem(
        id=uuid4(),
        clinic_id=budget.clinic_id,
        budget_id=budget.id,
        catalog_item_id=uuid4(),
        unit_price=Decimal("60.00"),
        quantity=1,
        vat_rate=0.0,
        line_subtotal=Decimal("60.00"),
        line_discount=Decimal("0.00"),
        line_tax=Decimal("0.00"),
        line_total=Decimal("60.00"),
    )
    item.catalog_item = TreatmentCatalogItem(
        id=item.catalog_item_id,
        clinic_id=budget.clinic_id,
        category_id=uuid4(),
        internal_code="LIMP-01",
        names={"es": "Limpieza dental"},
        default_price=Decimal("60.00"),
    )
    budget.items.append(item)
    return budget


def _clinic() -> Clinic:
    return Clinic(
        id=uuid4(),
        name="Test Clinic",
        tax_id="B1",
        address={"street": "Calle 1", "city": "Madrid"},
        settings={},
        timezone="Europe/Madrid",
        currency="EUR",
    )


def _document(document_type: str = "referral") -> GeneratedDocument:
    return GeneratedDocument(
        id=uuid4(),
        clinic_id=uuid4(),
        patient_id=uuid4(),
        document_type=document_type,
        title="Test",
        status="draft",
        content={"referred_to": "Dr. Example", "reason": "Second opinion"},
        created_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
    )


def _patient() -> Patient:
    return Patient(
        id=uuid4(),
        clinic_id=uuid4(),
        first_name="Ana",
        last_name="Test",
        date_of_birth=date(1990, 5, 4),
    )


def _document_html(locale: str, document_type: str = "referral") -> str:
    return DocumentPDFService._generate_html(
        _document(document_type), _clinic(), _patient(), locale, "Dr. Test"
    )


def test_budget_labels_exist_for_every_accepted_locale() -> None:
    english = BudgetPDFService._get_labels("en")
    for locale in PDF_LOCALES:
        labels = BudgetPDFService._get_labels(locale)
        assert set(labels) == set(english), locale
        assert set(labels["status"]) == set(english["status"]), locale
        if locale != "en":
            assert labels is not english, f"{locale} still falls back to English"


def test_purchase_order_labels_exist_for_every_accepted_locale() -> None:
    english = PO_LABELS["en"]
    for locale in PDF_LOCALES:
        assert locale in PO_LABELS, locale
        assert set(PO_LABELS[locale]) == set(english), locale
        assert set(PO_LABELS[locale]["status_label"]) == set(english["status_label"]), locale


def test_prescription_labels_exist_for_every_accepted_locale() -> None:
    english = rx_labels("en")
    for locale in PDF_LOCALES:
        labels = rx_labels(locale)
        assert set(labels) == set(english), locale
        if locale != "en":
            assert labels is not english, f"{locale} still falls back to English"


@pytest.mark.parametrize("locale", sorted(BUDGET_HEADINGS))
def test_budget_pdf_renders_its_own_heading(locale: str) -> None:
    html = BudgetPDFService._generate_html(_budget(), _clinic(), False, locale, None)
    assert BUDGET_HEADINGS[locale] in html


def _html_tag(html: str) -> str:
    return html.split("<html", 1)[1].split(">", 1)[0]


def test_only_arabic_budget_is_rtl() -> None:
    """The direction belongs on the document element, not in a stylesheet."""
    arabic = BudgetPDFService._generate_html(_budget(), _clinic(), False, "ar", None)
    spanish = BudgetPDFService._generate_html(_budget(), _clinic(), False, "es", None)
    assert 'dir="rtl"' in _html_tag(arabic)
    assert "dir=" not in _html_tag(spanish)


def test_budget_amounts_follow_the_locale_not_the_labels() -> None:
    """German separators even though the labels are their own set."""
    assert "60,00" in BudgetPDFService._generate_html(_budget(), _clinic(), False, "de", None)


# --- documents (#524) -----------------------------------------------------


def test_document_labels_exist_for_every_accepted_locale() -> None:
    english = DOC_LABELS["en"]
    for locale in PDF_LOCALES:
        assert locale in DOC_LABELS, locale
        assert set(DOC_LABELS[locale]) == set(english), locale


def test_only_arabic_document_is_rtl() -> None:
    arabic = _document_html("ar")
    spanish = _document_html("es")
    assert 'dir="rtl"' in _html_tag(arabic)
    assert "dir=" not in _html_tag(spanish)


@pytest.mark.parametrize(
    ("locale", "heading"),
    [
        ("es", "Carta de derivación"),
        ("en", "Referral letter"),
        ("de", "Überweisungsschreiben"),
        ("hu", "Beutaló"),
        ("ar", "خطاب إحالة"),
    ],
)
def test_document_pdf_renders_its_own_title(locale: str, heading: str) -> None:
    """A German clinic must not hand the patient a Spanish referral."""
    assert heading in _document_html(locale, document_type="referral")


# --- billing -------------------------------------------------------------


def test_invoice_labels_exist_for_every_accepted_locale() -> None:
    """Billing was already complete; the guard just never said so (#524)."""
    english = InvoicePDFService._get_labels("en")
    for locale in PDF_LOCALES:
        labels = InvoicePDFService._get_labels(locale)
        assert set(labels) == set(english), locale
        if locale != "en":
            assert labels != english, f"{locale} still falls back to English"


# --- the guard that made this findable (#524) -----------------------------


def _modules_shipping_a_pdf() -> list[str]:
    root = Path(__file__).resolve().parents[1] / "app" / "modules"
    return sorted(d.name for d in root.iterdir() if (d / "pdf.py").is_file())


def test_every_pdf_generator_is_covered_by_this_file() -> None:
    """Discovery, not a hand-kept list.

    The #485 guard asserted over the three modules I had in hand, so
    ``documents`` — which rendered every clinic's referral letters in
    Spanish — was never checked (#524). A new ``pdf.py`` must not be able
    to slip in the same way: add it to ``COVERED`` together with a test
    above, or this fails.
    """
    covered = {"billing", "budget", "documents", "prescriptions", "purchase_orders"}
    shipped = set(_modules_shipping_a_pdf())
    assert shipped == covered, (
        "modules shipping a pdf.py but not asserted here: "
        f"{sorted(shipped - covered)}; listed but gone: {sorted(covered - shipped)}"
    )
