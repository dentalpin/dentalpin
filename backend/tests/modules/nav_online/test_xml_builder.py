"""InvoiceData XML: structure, VAT mapping (27 % vs TAM), modification documents."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from lxml import etree

from app.modules.nav_online.services.xml_builder import (
    NS_DATA,
    HungarianTaxNumber,
    build_invoice_data,
    count_lines,
)

_NSMAP = {"d": NS_DATA, "base": "http://schemas.nav.gov.hu/OSA/3.0/base"}


def _invoice(*, tax_id=None):
    return SimpleNamespace(
        invoice_number="HU-2026-0001",
        issue_date=date(2026, 9, 6),
        billing_name="Kovács Anna",
        billing_tax_id=tax_id,
        billing_address={"street": "Fő u. 1", "city": "Budapest", "postal_code": "1011"},
        items=[
            SimpleNamespace(
                description="Fogkő-eltávolítás",
                quantity=1,
                line_subtotal=Decimal("15000"),
                line_discount=Decimal("0"),
                vat_rate=0.0,
                vat_exempt_reason=None,
            ),
            SimpleNamespace(
                description="Fogfehérítés",
                quantity=2,
                line_subtotal=Decimal("25000"),
                line_discount=Decimal("5000"),  # 20 % off → taxable base 20000
                vat_rate=27.0,
                vat_exempt_reason=None,
            ),
        ],
    )


def _credit_note(*, tax_id=None):
    """The same invoice as billing stores its credit note: negative unit price and lines."""
    inv = _invoice(tax_id=tax_id)
    inv.invoice_number = "HU-NC-2026-0001"
    for item in inv.items:
        item.line_subtotal = -item.line_subtotal
        item.line_discount = -item.line_discount
    return inv


def _xp(root, path):
    return root.xpath(path, namespaces=_NSMAP)


def test_tax_number_parse():
    assert HungarianTaxNumber.parse("12345678-2-41") == HungarianTaxNumber("12345678", "2", "41")
    assert HungarianTaxNumber.parse("12345678") == HungarianTaxNumber("12345678")
    assert HungarianTaxNumber.parse("B12345678") is None
    # Bare törzsszám: never invent vatCode/countyCode — both are optional in the XSD.
    assert "vatCode" not in HungarianTaxNumber("12345678").xml("supplierTaxNumber")


def test_private_person_invoice_lines_and_summary():
    res = build_invoice_data(
        _invoice(),
        supplier_tax_number=HungarianTaxNumber("87654321", "2", "41"),
        supplier_name="Mosoly Dental Kft.",
        supplier_address={"city": "Budapest", "postal_code": "1052", "street": "Deák tér 2"},
    )
    root = etree.fromstring(res.xml.encode())
    assert _xp(root, "/d:InvoiceData/d:invoiceNumber/text()") == ["HU-2026-0001"]
    assert _xp(root, "//d:customerInfo/d:customerVatStatus/text()") == ["PRIVATE_PERSON"]
    assert _xp(root, "//d:supplierTaxNumber/base:taxpayerId/text()") == ["87654321"]
    lines = _xp(root, "//d:invoiceLines/d:line")
    assert len(lines) == 2
    # Mandatory in the 3.0 schema and must precede lineDescription.
    assert [c.tag.split("}")[1] for c in lines[0]][:4] == [
        "lineNumber",
        "lineExpressionIndicator",
        "lineNatureIndicator",
        "lineDescription",
    ]
    assert _xp(lines[0], ".//d:vatExemption/d:case/text()") == ["TAM"]
    assert _xp(lines[1], ".//d:vatPercentage/text()") == ["0.27"]
    # Discount applied: net 25000 − 5000 = 20000, VAT 27 % of the discounted base.
    assert _xp(lines[1], ".//d:lineNetAmount/text()") == ["20000.00"]
    assert _xp(lines[1], ".//d:lineVatAmount/text()") == ["5400.00"]
    assert _xp(root, "//d:invoiceNetAmount/text()") == ["35000.00"]
    assert _xp(root, "//d:invoiceVatAmount/text()") == ["5400.00"]
    assert _xp(root, "//d:invoiceGrossAmount/text()") == ["40400.00"]
    assert res.gross_amount == Decimal("40400.00")
    assert len(_xp(root, "//d:summaryByVatRate")) == 2


def test_domestic_customer_and_storno_negation():
    res = build_invoice_data(
        _credit_note(tax_id="11111111-2-13"),
        supplier_tax_number=HungarianTaxNumber("87654321", "2", "41"),
        supplier_name="Mosoly Dental Kft.",
        supplier_address=None,
        original_invoice_number="HU-2026-0001",
    )
    root = etree.fromstring(res.xml.encode())
    assert _xp(root, "//d:customerVatStatus/text()") == ["DOMESTIC"]
    assert _xp(root, "//d:customerTaxNumber/base:taxpayerId/text()") == ["11111111"]
    assert _xp(root, "//d:originalInvoiceNumber/text()") == ["HU-2026-0001"]
    assert _xp(root, "//d:invoiceGrossAmount/text()") == ["-40400.00"]
    assert res.gross_amount == Decimal("-40400.00")
    # NAV's "Modositas es ervenytelenites" sample: negative quantity and
    # amounts, positive unit price (#1046).
    assert _xp(root, "//d:quantity/text()") == ["-1", "-2"]
    assert _xp(root, "//d:unitPrice/text()") == ["15000.00", "10000.00"]
    assert _xp(root, "//d:lineNetAmount/text()") == ["-15000.00", "-20000.00"]
    assert _xp(root, "//d:invoiceVatAmount/text()") == ["-5400.00"]


def _children(el):
    return [c.tag.split("}")[1] for c in el]


def test_modification_lines_reference_the_chain():
    """NAV's ``Modositas es ervenytelenites 2.xml``: index 2, every line a
    ``lineModificationReference`` continuing the numbering, CREATE (#1069)."""
    res = build_invoice_data(
        _credit_note(),
        supplier_tax_number=HungarianTaxNumber("87654321", "2", "41"),
        supplier_name="Mosoly Dental Kft.",
        supplier_address=None,
        original_invoice_number="HU-2026-0001",
        modification_index=2,
        line_number_offset=6,
    )
    root = etree.fromstring(res.xml.encode())
    # XSD InvoiceReferenceType sequence.
    assert _children(_xp(root, "//d:invoiceReference")[0]) == [
        "originalInvoiceNumber",
        "modifyWithoutMaster",
        "modificationIndex",
    ]
    assert _xp(root, "//d:invoiceReference/d:modificationIndex/text()") == ["2"]
    lines = _xp(root, "//d:invoiceLines/d:line")
    assert len(lines) == 2
    for n, line in enumerate(lines, start=1):
        # XSD LineType: lineNumber, lineModificationReference, …, lineExpressionIndicator.
        assert _children(line)[:3] == [
            "lineNumber",
            "lineModificationReference",
            "lineExpressionIndicator",
        ]
        assert _xp(line, "d:lineNumber/text()") == [str(n)]
        ref = _xp(line, "d:lineModificationReference")[0]
        assert _children(ref) == ["lineNumberReference", "lineOperation"]
        assert _xp(ref, "d:lineNumberReference/text()") == [str(6 + n)]
        assert _xp(ref, "d:lineOperation/text()") == ["CREATE"]
    # The #1046 sign handling is untouched.
    assert _xp(root, "//d:quantity/text()") == ["-1", "-2"]
    assert _xp(root, "//d:unitPrice/text()") == ["15000.00", "10000.00"]
    assert count_lines(res.xml) == 2


def test_create_has_no_line_modification_reference():
    res = build_invoice_data(
        _invoice(),
        supplier_tax_number=HungarianTaxNumber("87654321"),
        supplier_name="Mosoly Dental Kft.",
        supplier_address=None,
    )
    assert "lineModificationReference" not in res.xml
    assert "invoiceReference" not in res.xml
