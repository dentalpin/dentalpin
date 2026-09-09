"""FPR12 rendering validated against the official XSD (vendored in ./schemas)."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from lxml import etree

from app.modules.sdi_it.services.xml_builder import (
    Party,
    SdiBuildError,
    build_fattura,
    file_name,
    progressivo_invio,
)

SCHEMA = etree.XMLSchema(
    etree.parse(str(Path(__file__).parent / "schemas" / "Schema_del_file_xml_FatturaPA_v1.2.2.xsd"))
)

CEDENTE = Party.from_clinic(
    tax_id="01234567897",
    name="Studio Dentistico Rossi S.r.l.",
    address={"street": "Via Roma 1", "postal_code": "20121", "city": "Milano", "province": "MI"},
)
INSURER = Party.from_recipient(
    tax_id="IT 00000000000",
    name="Assicurazioni Alfa S.p.A.",
    address={"street": "Corso Italia 10", "postal_code": "00100", "city": "Roma", "province": "RM"},
)


def _item(desc, price, qty=1, rate=0.0, discount="0.00", order=0):
    price = Decimal(price)
    return SimpleNamespace(
        description=desc,
        unit_price=price,
        quantity=qty,
        vat_rate=rate,
        line_discount=Decimal(discount),
        line_subtotal=price * qty,
        display_order=order,
    )


def _invoice(items, *, number="E/2026/0007", notes=None, tax_id="00000000000", address=None):
    return SimpleNamespace(
        invoice_number=number,
        issue_date=date(2026, 9, 7),
        due_date=date(2026, 10, 7),
        billing_tax_id=tax_id,
        billing_name="Assicurazioni Alfa S.p.A.",
        billing_address=address or {},
        public_notes=notes,
        items=items,
    )


def _validate(xml: str) -> etree._Element:
    doc = etree.fromstring(xml.encode("utf-8"))
    SCHEMA.assertValid(doc)
    return doc


def _text(doc, path):
    ns = {"p": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"}
    el = doc.find(path, ns)
    return el.text if el is not None else None


def test_exempt_invoice_validates_with_natura_n4_and_bollo():
    inv = _invoice(
        [_item("Visita specialistica", "60.00"), _item("Otturazione", "120.00", order=1)]
    )
    res = build_fattura(inv, cedente=CEDENTE, cessionario=INSURER, progressivo="00001")
    doc = _validate(res.xml)
    body = "FatturaElettronicaBody/"
    assert _text(doc, body + "DatiGenerali/DatiGeneraliDocumento/TipoDocumento") == "TD01"
    assert _text(doc, body + "DatiBeniServizi/DettaglioLinee/Natura") == "N4"
    assert _text(doc, body + "DatiBeniServizi/DettaglioLinee/AliquotaIVA") == "0.00"
    riepilogo = doc.find(body + "DatiBeniServizi/DatiRiepilogo")
    assert riepilogo.find("Natura").text == "N4"
    assert "art. 10 n. 18" in riepilogo.find("RiferimentoNormativo").text
    # 180.00 exempt > 77.47 → virtual €2 stamp; the issuer bears it, the
    # document total stays the invoice total
    assert _text(doc, body + "DatiGenerali/DatiGeneraliDocumento/DatiBollo/ImportoBollo") == "2.00"
    assert res.gross_amount == Decimal("180.00")
    assert (
        _text(doc, body + "DatiGenerali/DatiGeneraliDocumento/ImportoTotaleDocumento") == "180.00"
    )
    assert _text(doc, body + "DatiPagamento/DettaglioPagamento/ImportoPagamento") == "180.00"
    assert res.file_name == "IT01234567897_00001.xml"
    assert res.codice_destinatario == "0000000"
    header = "FatturaElettronicaHeader/"
    assert _text(doc, header + "DatiTrasmissione/FormatoTrasmissione") == "FPR12"
    assert _text(doc, header + "CedentePrestatore/DatiAnagrafici/RegimeFiscale") == "RF01"
    assert (
        _text(doc, header + "CessionarioCommittente/DatiAnagrafici/IdFiscaleIVA/IdCodice")
        == "00000000000"
    )


def test_taxable_and_exempt_lines_get_separate_riepilogo_and_no_bollo_under_threshold():
    inv = _invoice([_item("Sbiancamento", "50.00", rate=22.0), _item("Visita", "30.00")])
    res = build_fattura(inv, cedente=CEDENTE, cessionario=INSURER, progressivo="0000A")
    doc = _validate(res.xml)
    riepiloghi = doc.findall("FatturaElettronicaBody/DatiBeniServizi/DatiRiepilogo")
    assert [(r.find("AliquotaIVA").text, r.find("Imposta").text) for r in riepiloghi] == [
        ("0.00", "0.00"),
        ("22.00", "11.00"),
    ]
    assert not res.bollo and res.gross_amount == Decimal("91.00")
    assert doc.find("FatturaElettronicaBody/DatiGenerali/DatiGeneraliDocumento/DatiBollo") is None


def test_credit_note_td04_references_original_and_discount_line():
    inv = _invoice([_item("Storno visita", "60.00", discount="10.00")], number="NC/2026/0001")
    res = build_fattura(
        inv,
        cedente=CEDENTE,
        cessionario=INSURER,
        progressivo="00002",
        original_invoice_number="E/2026/0007",
        original_invoice_date="2026-09-07",
    )
    doc = _validate(res.xml)
    assert res.tipo_documento == "TD04"
    assert (
        _text(doc, "FatturaElettronicaBody/DatiGenerali/DatiFattureCollegate/IdDocumento")
        == "E/2026/0007"
    )
    line = doc.find("FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee")
    assert line.find("ScontoMaggiorazione/Importo").text == "10.00"
    assert line.find("PrezzoTotale").text == "50.00"


def test_recipient_routing_from_billing_address():
    inv = _invoice([_item("Visita", "10.00")], address={"sdi_code": "abc1234"})
    res = build_fattura(inv, cedente=CEDENTE, cessionario=INSURER, progressivo="00003")
    _validate(res.xml)
    assert res.codice_destinatario == "ABC1234"
    inv = _invoice([_item("Visita", "10.00")], address={"pec": "fatture@alfa.legalmail.it"})
    res = build_fattura(inv, cedente=CEDENTE, cessionario=INSURER, progressivo="00004")
    doc = _validate(res.xml)
    assert (
        _text(doc, "FatturaElettronicaHeader/DatiTrasmissione/PECDestinatario")
        == "fatture@alfa.legalmail.it"
    )


def test_escaping_and_length_limits_keep_the_file_valid():
    inv = _invoice(
        [_item("Visita <urgente> & controllo " * 60, "10.00")], notes="Rif. polizza <A&B>"
    )
    res = build_fattura(inv, cedente=CEDENTE, cessionario=INSURER, progressivo="00005")
    _validate(res.xml)


def test_build_errors():
    with pytest.raises(SdiBuildError):
        Party.from_clinic(tax_id="B12345678", name="x", address={})
    with pytest.raises(SdiBuildError):
        Party.from_recipient(tax_id="nope", name="x", address={})
    with pytest.raises(SdiBuildError):
        build_fattura(_invoice([]), cedente=CEDENTE, cessionario=INSURER, progressivo="00001")
    inv = _invoice([_item("Visita", "10.00")], number=None)
    with pytest.raises(SdiBuildError):
        build_fattura(inv, cedente=CEDENTE, cessionario=INSURER, progressivo="00001")


def test_progressivo_and_file_name():
    assert progressivo_invio(1) == "00001"
    assert progressivo_invio(36) == "00010"
    assert progressivo_invio(36**5 - 1) == "ZZZZZ"
    assert file_name("01234567897", "0000Z") == "IT01234567897_0000Z.xml"
