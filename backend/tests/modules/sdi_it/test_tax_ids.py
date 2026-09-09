"""Partita IVA / codice fiscale parsing and the B2B gate."""

from app.modules.sdi_it.services.tax_ids import CodiceFiscale, PartitaIva, is_business_recipient


def test_partita_iva_check_digit():
    assert PartitaIva.parse("01234567897") is not None  # check digit 7
    assert PartitaIva.parse("IT 01234567897").value == "01234567897"
    assert PartitaIva.parse("01234567891") is None
    assert PartitaIva.parse("1234567890") is None


def test_codice_fiscale_natural_person():
    cf = CodiceFiscale.parse("rssmra80a01h501u")
    assert cf is not None and cf.value == "RSSMRA80A01H501U" and cf.is_natural_person
    assert CodiceFiscale.parse("RSSMRA80A01H501") is None


def test_gate_is_partita_iva_only():
    assert is_business_recipient("01234567897")
    assert not is_business_recipient("RSSMRA80A01H501U")  # patient → analogue invoice
    assert not is_business_recipient(None)
    assert not is_business_recipient("B12345678")  # a Spanish CIF is not a partita IVA
