"""SDI receipt parsing: RC / NS / MC by root element or file name."""

import pytest

from app.modules.sdi_it.services.receipts import STATE_FOR_RECEIPT, ReceiptError, parse_receipt

NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/messaggi/v1.0"


def _rc():
    return (
        f'<ns3:RicevutaConsegna xmlns:ns3="{NS}" versione="1.0">'
        "<IdentificativoSdI>1234567</IdentificativoSdI><NomeFile>IT01234567897_00001.xml</NomeFile>"
        "<DataOraRicezione>2026-09-07T10:00:00.000+02:00</DataOraRicezione>"
        "<DataOraConsegna>2026-09-07T10:05:00.000+02:00</DataOraConsegna>"
        "<Destinatario><Codice>0000000</Codice><Descrizione>Area riservata</Descrizione></Destinatario>"
        "<MessageId>987654</MessageId></ns3:RicevutaConsegna>"
    )


def _ns():
    return (
        f'<ns3:NotificaScarto xmlns:ns3="{NS}" versione="1.0">'
        "<IdentificativoSdI>1234568</IdentificativoSdI><NomeFile>IT01234567897_00002.xml</NomeFile>"
        "<DataOraRicezione>2026-09-07T10:00:00.000+02:00</DataOraRicezione>"
        "<ListaErrori><Errore><Codice>00404</Codice><Descrizione>Fattura duplicata</Descrizione></Errore>"
        "<Errore><Codice>00423</Codice><Descrizione>Prezzo totale non calcolato correttamente</Descrizione></Errore></ListaErrori>"
        "<MessageId>987655</MessageId></ns3:NotificaScarto>"
    )


def test_rc():
    r = parse_receipt(_rc())
    assert r.type == "RC" and r.identificativo_sdi == "1234567"
    assert r.nome_file == "IT01234567897_00001.xml" and r.delivered_at.startswith("2026-09-07")
    assert STATE_FOR_RECEIPT[r.type] == "delivered"


def test_ns_errors():
    r = parse_receipt(_ns())
    assert r.type == "NS" and r.errors == [
        ("00404", "Fattura duplicata"),
        ("00423", "Prezzo totale non calcolato correttamente"),
    ]


def test_mc_by_either_root_name_or_file_name():
    xml = f'<ns3:NotificaMancataConsegna xmlns:ns3="{NS}"><NomeFile>IT01234567897_00003.xml</NomeFile></ns3:NotificaMancataConsegna>'
    assert parse_receipt(xml).type == "MC"
    xml = f'<ns3:RicevutaImpossibilitaRecapito xmlns:ns3="{NS}"><NomeFile>IT01234567897_00003.xml</NomeFile></ns3:RicevutaImpossibilitaRecapito>'
    assert parse_receipt(xml).type == "MC"
    unknown = "<Boh><NomeFile>IT01234567897_00003.xml</NomeFile></Boh>"
    assert parse_receipt(unknown, receipt_file_name="IT01234567897_00003_MC_001.xml").type == "MC"
    with pytest.raises(ReceiptError):
        parse_receipt(unknown)
    with pytest.raises(ReceiptError):
        parse_receipt("<not xml")
