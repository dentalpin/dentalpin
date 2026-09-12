from app.modules.sistema_ts.services.codice_fiscale import is_partita_iva, normalise_codice_fiscale


def test_codice_fiscale_check_character():
    assert normalise_codice_fiscale("rssmra80a01h501u") == "RSSMRA80A01H501U"
    assert normalise_codice_fiscale("RSSMRA80A01H501X") is None  # wrong check char
    assert normalise_codice_fiscale("RSSMRA80A01H501") is None
    assert normalise_codice_fiscale(None) is None


def test_partita_iva_gate():
    assert is_partita_iva("01234567897") and is_partita_iva("IT01234567897")
    assert not is_partita_iva("01234567890")
    assert not is_partita_iva("RSSMRA80A01H501U")
