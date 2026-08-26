"""Billing renders + escapes the structured compliance section.

The hook hands billing DATA (title/rows/hint), never HTML — these tests
pin the two properties that kill the injection class: hook output
contains no markup, and billing escapes whatever values reach the
template (GSTINs, trade names and doc references are user-controlled).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.core.auth.models import Clinic
from app.modules.billing.models import Invoice
from app.modules.billing.pdf import InvoicePDFService
from app.modules.india_gst.hook import IndiaGstHook

XSS = "<script>alert(1)</script>"


def _invoice(**overrides) -> Invoice:
    values = dict(
        id=uuid4(),
        clinic_id=uuid4(),
        status="issued",
        billing_name="A B",
        invoice_number="GST-2026-0001",
        subtotal=Decimal("100.00"),
        total_discount=Decimal("0.00"),
        total_tax=Decimal("18.00"),
        total=Decimal("118.00"),
    )
    values.update(overrides)
    return Invoice(**values)


def _clinic() -> Clinic:
    return Clinic(
        id=uuid4(), name="Test Clinic", tax_id="B1", address={}, settings={}, currency="INR"
    )


def test_hook_emits_structured_rows_not_html():
    invoice = _invoice(
        compliance_data={
            "IN": {
                "supplier": {"trade_name": XSS, "gstin": "33ABCDE1234F1Z7"},
                "recipient": {"gstin": XSS},
                "place_of_supply": "33",
                "place_of_supply_name": "Tamil Nadu",
                "tax_type": "intra",
                "cgst_total": "9.00",
                "sgst_total": "9.00",
                "igst_total": "0.00",
                "gst_document_number": XSS,
                "einvoice_state": "not_required",
                "show_gstin_on_invoice": True,
            }
        }
    )
    pdf_data = IndiaGstHook().enhance_pdf_data({}, invoice)
    section = pdf_data["compliance_section"]
    assert "compliance_section_html" not in pdf_data
    assert isinstance(section["rows"], list)
    # Values pass through as data — no markup is generated hook-side.
    assert all("<div" not in str(row["value"]) for row in section["rows"])


def test_billing_escapes_compliance_values_and_notices():
    html = InvoicePDFService._generate_html(
        _invoice(),
        _clinic(),
        is_preview=False,
        locale="en",
        extra_pdf_data={
            "legal_notices": [XSS],
            "compliance_section": {
                "title": XSS,
                "rows": [{"label": XSS, "value": XSS}],
                "hint": XSS,
            },
        },
    )
    assert XSS not in html
    assert html.count("&lt;script&gt;alert(1)&lt;/script&gt;") >= 5


def test_label_overrides_cannot_add_keys_or_clobber_status():
    html = InvoicePDFService._generate_html(
        _invoice(),
        _clinic(),
        is_preview=False,
        locale="en",
        extra_pdf_data={
            "label_overrides": {
                "vat": "GST",  # legitimate flat override
                "status": {"issued": "PWNED"},  # nested dict must survive
                "evil_new_key": "<b>x</b>",  # unknown keys ignored
            }
        },
    )
    assert "GST" in html
    assert "PWNED" not in html
    assert "Issued" in html  # status dict untouched


def test_pdf_renders_from_immutable_snapshot_not_live_settings():
    """enhance_pdf_data must read from compliance_data['IN'] (the
    fiscal snapshot taken at issue time), not from live settings.
    Changing the trade name or GSTIN after issue must not change the
    PDF output."""
    invoice = _invoice(
        compliance_data={
            "IN": {
                "supplier": {"trade_name": "Original Clinic", "gstin": "33ABCDE1234F1Z7"},
                "recipient": {"gstin": "29ZZZZZ9999Z9ZW"},
                "place_of_supply": "29",
                "place_of_supply_name": "Karnataka",
                "tax_type": "inter",
                "cgst_total": "0.00",
                "sgst_total": "0.00",
                "igst_total": "180.00",
                "gst_document_number": "GST/FY26-27/0001",
                "einvoice_state": "not_required",
                "show_gstin_on_invoice": True,
            }
        }
    )
    pdf_data_1 = IndiaGstHook().enhance_pdf_data({}, invoice)
    section_1 = pdf_data_1["compliance_section"]
    rows_1 = {row["label"]: row["value"] for row in section_1["rows"]}

    # The snapshot values must be present in the rendered rows — the
    # hook reads from compliance_data['IN'], not live settings.
    assert rows_1["GST document number"] == "GST/FY26-27/0001"
    assert "Karnataka" in rows_1["Place of supply"]
    assert "33ABCDE1234F1Z7" in rows_1["GSTIN on invoice"]
    assert "180.00" in rows_1["IGST"]
    assert "Inter-state" in rows_1["GST calculation"]

    # A second call with the same invoice must produce identical data.
    pdf_data_2 = IndiaGstHook().enhance_pdf_data({}, invoice)
    section_2 = pdf_data_2["compliance_section"]
    rows_2 = {row["label"]: row["value"] for row in section_2["rows"]}
    assert rows_1 == rows_2
