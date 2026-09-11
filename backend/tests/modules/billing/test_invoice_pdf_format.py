"""Invoice PDF formatting fixes from #204 (pure HTML — no DB).

- footer prints the real generation datetime in the clinic timezone
  (``date.today()`` through ``%H:%M`` always read "00:00")
- the per-line VAT rate uses the same locale-aware formatting as the
  amounts ("0%" next to "0,00 €", never "0.0%")
- statutory VAT clauses arrive through the ``legal_notices`` block
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.core.auth.models import Clinic
from app.modules.billing import pdf as pdf_module
from app.modules.billing.models import Invoice, InvoiceItem
from app.modules.billing.pdf import InvoicePDFService

ES_NOTE = "Operación exenta de IVA según el art. 20.Uno.5º de la Ley 37/1992"


def _invoice(vat_rate: float = 0.0) -> Invoice:
    invoice = Invoice(
        id=uuid4(),
        clinic_id=uuid4(),
        status="issued",
        billing_name="A B",
        invoice_number="FAC-2026-0001",
        subtotal=Decimal("60.00"),
        total_discount=Decimal("0.00"),
        total_tax=Decimal("0.00"),
        total=Decimal("60.00"),
    )
    invoice.items.append(
        InvoiceItem(
            id=uuid4(),
            clinic_id=invoice.clinic_id,
            description="Limpieza dental",
            quantity=1,
            unit_price=Decimal("60.00"),
            vat_rate=vat_rate,
            line_subtotal=Decimal("60.00"),
            line_total=Decimal("60.00"),
        )
    )
    return invoice


def _clinic(timezone: str = "Europe/Madrid") -> Clinic:
    return Clinic(
        id=uuid4(),
        name="Test Clinic",
        tax_id="B1",
        address={},
        settings={},
        currency="EUR",
        timezone=timezone,
    )


def _html(invoice: Invoice, clinic: Clinic, locale: str = "es", **kwargs) -> str:
    return InvoicePDFService._generate_html(
        invoice, clinic, is_preview=False, locale=locale, **kwargs
    )


def test_footer_prints_real_time_in_clinic_timezone(monkeypatch) -> None:
    captured: dict = {}

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            captured["tz"] = tz
            return datetime(2026, 8, 18, 17, 42, tzinfo=tz or UTC)

    monkeypatch.setattr(pdf_module, "datetime", _FrozenDatetime)
    html = _html(_invoice(), _clinic("Europe/Madrid"))
    assert "18/08/2026 17:42" in html
    assert str(captured["tz"]) == "Europe/Madrid"


def test_footer_falls_back_to_utc_on_bad_timezone() -> None:
    html = _html(_invoice(), _clinic(timezone="Not/AZone"))
    assert "DentalPin" in html  # rendered without raising


def test_vat_rate_formats_like_the_amounts() -> None:
    html = _html(_invoice(vat_rate=0.0), _clinic())
    assert ">0%<" in html
    assert "0.0%" not in html

    html = _html(_invoice(vat_rate=21.0), _clinic())
    assert ">21%<" in html

    # Fractional rates keep the locale decimal separator (es → comma).
    html = _html(_invoice(vat_rate=8.5), _clinic())
    assert ">8,5%<" in html


def test_legal_notices_render_the_vat_clause() -> None:
    html = _html(_invoice(), _clinic(), extra_pdf_data={"legal_notices": [ES_NOTE]})
    assert "art. 20.Uno.5º de la Ley 37/1992" in html


def test_every_ui_locale_renders_a_pdf() -> None:
    """The download button sends the UI language; every locale the host
    ships must render (labels fall back to English where untranslated).
    That the list covers the host's languages is guarded in
    tests/test_pdf_locales.py, next to the list itself."""
    import re

    from app.core.pdf_locales import PDF_LOCALE_PATTERN, PDF_LOCALES

    for locale in PDF_LOCALES:
        assert re.match(PDF_LOCALE_PATTERN, locale)
        html = _html(_invoice(), _clinic(), locale=locale)
        assert f'lang="{locale}"' in html
    assert "Rechnung" not in _html(_invoice(), _clinic(), locale="de")  # English fallback for now
    assert "60,00" in _html(_invoice(), _clinic(), locale="de")  # but German separators
    assert not re.match(PDF_LOCALE_PATTERN, "xx")
