"""InvoiceData XML: structure, VAT mapping (27 % vs TAM), STORNO negation."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from lxml import etree

from app.modules.nav_online.services.xml_builder import (
    NS_DATA,
    HungarianTaxNumber,
    build_invoice_data,
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
        _invoice(tax_id="11111111-2-13"),
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
