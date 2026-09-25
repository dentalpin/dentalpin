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
from uuid import uuid4

import pytest

from app.core.auth.models import Clinic
from app.core.pdf_locales import PDF_LOCALES
from app.modules.budget.models import Budget, BudgetItem
from app.modules.budget.pdf import BudgetPDFService
from app.modules.catalog.models import TreatmentCatalogItem
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
