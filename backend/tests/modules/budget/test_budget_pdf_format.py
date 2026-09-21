"""Budget PDF per-locale headings + RTL (pure HTML, no DB). Mirrors
billing's test_invoice_pdf_format.py for the #485 label sets."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.core.auth.models import Clinic
from app.modules.budget.models import Budget
from app.modules.budget.pdf import BudgetPDFService


def _budget() -> Budget:
    return Budget(
        id=uuid4(),
        clinic_id=uuid4(),
        patient_id=uuid4(),
        budget_number="PRE-2026-0001",
        version=1,
        status="sent",
        subtotal=Decimal("100.00"),
        total_discount=Decimal("0.00"),
        total_tax=Decimal("0.00"),
        total=Decimal("100.00"),
        global_discount_type="percentage",
        global_discount_value=Decimal("0"),
        valid_from=datetime(2026, 5, 4, tzinfo=UTC),
        valid_until=datetime(2026, 6, 4, tzinfo=UTC),
        created_at=datetime(2026, 5, 4, tzinfo=UTC),
    )


def _clinic() -> Clinic:
    return Clinic(
        id=uuid4(),
        name="Test Clinic",
        tax_id="B1",
        address={},
        settings={},
        currency="EUR",
        timezone="Europe/Madrid",
    )


def _html(locale: str) -> str:
    return BudgetPDFService._generate_html(_budget(), _clinic(), is_preview=False, locale=locale)


def test_each_locale_renders_own_budget_heading() -> None:
    headings = {
        "es": "Presupuesto",
        "en": "Quote",
        "fr": "Devis",
        "pt": "Orçamento",
        "de": "Kostenvoranschlag",
        "hu": "Árajánlat",
        "pl": "Kosztorys",
        "it": "Preventivo",
        "ar": "عرض السعر",
        "ta": "மதிப்பீடு",
    }
    for locale, heading in headings.items():
        assert heading in _html(locale)


def test_arabic_budget_pdf_is_rtl() -> None:
    html = _html("ar")
    assert 'dir="rtl"' in html
    html = _html("es")
    assert 'dir="rtl"' not in html
