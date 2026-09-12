"""Request shapes vs the kit's SoapUI samples (Medico, kit730P_ver_20240214)."""

from datetime import date
from decimal import Decimal

from lxml import etree

from app.modules.sistema_ts.services import xml_builder as xb

NS = {"soapenv": "http://schemas.xmlsoap.org/soap/envelope/", "doc": xb.NS}
PROP = xb.Proprietario(cf_proprietario_encrypted="CF==")
DOC = xb.DocumentoSpesa(
    p_iva="01201200121",
    data_emissione=date(2026, 3, 2),
    dispositivo="1",
    num_documento="FAC/2026/0007",
    data_pagamento=date(2026, 3, 5),
    cf_cittadino_encrypted="CIT==",
    voci=(
        xb.Voce("SR", Decimal("25.3"), natura_iva="N4"),
        xb.Voce("IC", Decimal("30.3"), aliquota_iva=Decimal("22")),
    ),
)


def _body(xml: str) -> etree._Element:
    root = etree.fromstring(xml.encode())
    body = root.find("soapenv:Body", NS)
    assert body is not None and len(body) == 1
    return body[0]


def _path(el, path):
    found = el.find(path, NS)
    return found.text if found is not None else None


def test_inserimento_matches_the_kit_sample_order():
    req = _body(xb.build_inserimento("PIN==", PROP, DOC).xml)
    assert (
        etree.QName(req).localname == "inserimentoDocumentoSpesaRequest"
        and etree.QName(req).namespace == xb.NS
    )
    assert [etree.QName(c).localname for c in req] == [
        "opzionale1",
        "opzionale2",
        "opzionale3",
        "pincode",
        "Proprietario",
        "idInserimentoDocumentoFiscale",
    ]
    assert _path(req, "doc:pincode") == "PIN=="
    assert _path(req, "doc:Proprietario/doc:cfProprietario") == "CF=="
    d = req.find("doc:idInserimentoDocumentoFiscale", NS)
    assert [etree.QName(c).localname for c in d] == [
        "idSpesa",
        "dataPagamento",
        "cfCittadino",
        "voceSpesa",
        "voceSpesa",
        "pagamentoTracciato",
        "tipoDocumento",
        "flagOpposizione",
    ]
    assert _path(d, "doc:idSpesa/doc:pIva") == "01201200121"
    assert _path(d, "doc:idSpesa/doc:numDocumentoFiscale/doc:dispositivo") == "1"
    assert _path(d, "doc:idSpesa/doc:numDocumentoFiscale/doc:numDocumento") == "FAC/2026/0007"
    assert (
        _path(d, "doc:idSpesa/doc:dataEmissione") == "2026-03-02"
        and _path(d, "doc:dataPagamento") == "2026-03-05"
    )
    voci = d.findall("doc:voceSpesa", NS)
    assert [etree.QName(c).localname for c in voci[0]] == ["tipoSpesa", "importo", "naturaIVA"]
    assert _path(voci[0], "doc:importo") == "25.30" and _path(voci[0], "doc:naturaIVA") == "N4"
    assert [etree.QName(c).localname for c in voci[1]] == ["tipoSpesa", "importo", "aliquotaIVA"]
    assert _path(voci[1], "doc:aliquotaIVA") == "22.00"
    assert _path(d, "doc:flagOpposizione") == "0" and _path(d, "doc:tipoDocumento") == "F"


def test_opposition_drops_cf_and_sets_flag():
    anon = xb.DocumentoSpesa(**{**DOC.__dict__, "cf_cittadino_encrypted": None})
    d = _body(xb.build_inserimento("PIN==", PROP, anon).xml).find(
        "doc:idInserimentoDocumentoFiscale", NS
    )
    assert d.find("doc:cfCittadino", NS) is None and _path(d, "doc:flagOpposizione") == "1"


def test_flag_pagamento_anticipato_and_flag_tipo_spesa():
    early = xb.DocumentoSpesa(
        **{
            **DOC.__dict__,
            "data_pagamento": date(2026, 2, 1),
            "flag_pagamento_anticipato": True,
            "voci": (xb.Voce("SR", Decimal("10"), flag_tipo_spesa="2"),),
        }
    )
    d = _body(xb.build_variazione("PIN==", PROP, early).xml).find(
        "doc:idVariazioneDocumentoFiscale", NS
    )
    assert [etree.QName(c).localname for c in d][:3] == [
        "idSpesa",
        "dataPagamento",
        "flagPagamentoAnticipato",
    ]
    assert [etree.QName(c).localname for c in d.find("doc:voceSpesa", NS)] == [
        "tipoSpesa",
        "flagTipoSpesa",
        "importo",
    ]


def test_cancellazione_and_rimborso_shapes():
    c = _body(
        xb.build_cancellazione(
            "PIN==", PROP, "01201200121", date(2026, 3, 2), "1", "FAC/2026/0007"
        ).xml
    )
    assert etree.QName(c).localname == "cancellazioneDocumentoSpesaRequest"
    idc = c.find("doc:idCancellazioneDocumentoFiscale", NS)
    assert [etree.QName(x).localname for x in idc] == [
        "pIva",
        "dataEmissione",
        "numDocumentoFiscale",
    ]
    r = _body(
        xb.build_rimborso(
            "PIN==", PROP, ("01201200121", date(2026, 3, 2), "1", "FAC/2026/0007"), DOC
        ).xml
    )
    assert [etree.QName(x).localname for x in r] == [
        "opzionale1",
        "opzionale2",
        "opzionale3",
        "pincode",
        "Proprietario",
        "idRimborsoDocumentoFiscale",
        "DocumentoSpesa",
    ]
    body = r.find("doc:DocumentoSpesa", NS)
    assert [etree.QName(x).localname for x in body] == [
        "idSpesa",
        "dataPagamento",
        "cfCittadino",
        "voceSpesa",
        "voceSpesa",
    ]


def test_structure_codes_appear_only_when_set():
    prop = xb.Proprietario(
        cf_proprietario_encrypted="CF==",
        codice_regione="120",
        codice_asl="201",
        codice_ssa="000123",
    )
    p = _body(xb.build_inserimento("PIN==", prop, DOC).xml).find("doc:Proprietario", NS)
    assert [etree.QName(x).localname for x in p] == [
        "codiceRegione",
        "codiceAsl",
        "codiceSSA",
        "cfProprietario",
    ]
