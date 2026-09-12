"""SOAP requests of the Sistema TS synchronous service
(``DocumentoSpesa730pWeb/DocumentoSpesa730pPort``), element for element as
the kit's SoapUI project for the *Medico* subject (kit730P_ver_20240214):
``inserimentoDocumentoSpesaRequest``, ``variazioneDocumentoSpesaRequest``,
``cancellazioneDocumentoSpesaRequest``, ``rimborsoDocumentoSpesaRequest`` in
the ``http://documentospesap730.sanita.finanze.it`` namespace.

``pincode`` and ``cfCittadino`` are RSA-encrypted (``services/crypto``);
``cfProprietario`` is sent encrypted too (the kit's sample and spec
table 1: "codice fiscale cifrato"). Amounts use a dot and two decimals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from xml.sax.saxutils import escape

NS = "http://documentospesap730.sanita.finanze.it"
_Q2 = Decimal("0.01")


@dataclass(frozen=True)
class Voce:
    tipo_spesa: str  # TK FC FV AD AS SR CT PI IC AA SV SP
    importo: Decimal
    flag_tipo_spesa: str | None = None  # "1" (TK pronto soccorso) | "2" (SR intramoenia)
    aliquota_iva: Decimal | None = None  # exclusive with natura_iva
    natura_iva: str | None = None  # N1..N7 (+ sub-codes for F)


@dataclass(frozen=True)
class DocumentoSpesa:
    p_iva: str
    data_emissione: date
    dispositivo: str
    num_documento: str
    data_pagamento: date
    cf_cittadino_encrypted: str | None  # None ⇒ flagOpposizione=1
    voci: tuple[Voce, ...]
    pagamento_tracciato: str = "SI"
    tipo_documento: str = "F"
    flag_pagamento_anticipato: bool = False


@dataclass(frozen=True)
class Proprietario:
    cf_proprietario_encrypted: str
    codice_regione: str | None = None
    codice_asl: str | None = None
    codice_ssa: str | None = None


@dataclass
class Built:
    operation: str
    xml: str
    soap_action: str = ""
    extra: dict = field(default_factory=dict)


def _money(v: Decimal) -> str:
    return str(v.quantize(_Q2, rounding=ROUND_HALF_UP))


def _el(name: str, value: str | None) -> str:
    return f"<doc:{name}>{escape(value)}</doc:{name}>" if value is not None else ""


def _head(pincode_encrypted: str, prop: Proprietario) -> str:
    parts = [
        "<doc:opzionale1></doc:opzionale1><doc:opzionale2></doc:opzionale2><doc:opzionale3></doc:opzionale3>",
        _el("pincode", pincode_encrypted),
        "<doc:Proprietario>",
        _el("codiceRegione", prop.codice_regione),
        _el("codiceAsl", prop.codice_asl),
        _el("codiceSSA", prop.codice_ssa),
        _el("cfProprietario", prop.cf_proprietario_encrypted),
        "</doc:Proprietario>",
    ]
    return "".join(parts)


def _id_spesa(d: DocumentoSpesa | tuple[str, date, str, str]) -> str:
    if isinstance(d, DocumentoSpesa):
        p_iva, data_emissione, dispositivo, num = (
            d.p_iva,
            d.data_emissione,
            d.dispositivo,
            d.num_documento,
        )
    else:
        p_iva, data_emissione, dispositivo, num = d
    return (
        f"{_el('pIva', p_iva)}{_el('dataEmissione', data_emissione.isoformat())}"
        f"<doc:numDocumentoFiscale>{_el('dispositivo', dispositivo)}{_el('numDocumento', num)}</doc:numDocumentoFiscale>"
    )


def _voce(v: Voce) -> str:
    return (
        "<doc:voceSpesa>"
        + _el("tipoSpesa", v.tipo_spesa)
        + _el("flagTipoSpesa", v.flag_tipo_spesa)
        + _el("importo", _money(v.importo))
        + (_el("aliquotaIVA", _money(v.aliquota_iva)) if v.aliquota_iva is not None else "")
        + (_el("naturaIVA", v.natura_iva) if v.natura_iva else "")
        + "</doc:voceSpesa>"
    )


def _documento(d: DocumentoSpesa, *, with_flags: bool = True) -> str:
    """The ``idSpesa … flagOpposizione`` sequence shared by inserimento,
    variazione and the rimborso body (kit sample order)."""
    out = [
        "<doc:idSpesa>",
        _id_spesa(d),
        "</doc:idSpesa>",
        _el("dataPagamento", d.data_pagamento.isoformat()),
        _el("flagPagamentoAnticipato", "1") if d.flag_pagamento_anticipato else "",
        _el("cfCittadino", d.cf_cittadino_encrypted) if d.cf_cittadino_encrypted else "",
        "".join(_voce(v) for v in d.voci),
    ]
    if with_flags:
        out += [
            _el("pagamentoTracciato", d.pagamento_tracciato),
            _el("tipoDocumento", d.tipo_documento),
            _el("flagOpposizione", "0" if d.cf_cittadino_encrypted else "1"),
        ]
    return "".join(out)


def _envelope(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        f'xmlns:doc="{NS}"><soapenv:Header/><soapenv:Body>{body}</soapenv:Body></soapenv:Envelope>'
    )


def build_inserimento(pincode_encrypted: str, prop: Proprietario, d: DocumentoSpesa) -> Built:
    body = (
        "<doc:inserimentoDocumentoSpesaRequest>"
        + _head(pincode_encrypted, prop)
        + "<doc:idInserimentoDocumentoFiscale>"
        + _documento(d)
        + "</doc:idInserimentoDocumentoFiscale></doc:inserimentoDocumentoSpesaRequest>"
    )
    return Built("inserimento", _envelope(body))


def build_variazione(pincode_encrypted: str, prop: Proprietario, d: DocumentoSpesa) -> Built:
    body = (
        "<doc:variazioneDocumentoSpesaRequest>"
        + _head(pincode_encrypted, prop)
        + "<doc:idVariazioneDocumentoFiscale>"
        + _documento(d)
        + "</doc:idVariazioneDocumentoFiscale></doc:variazioneDocumentoSpesaRequest>"
    )
    return Built("variazione", _envelope(body))


def build_cancellazione(
    pincode_encrypted: str,
    prop: Proprietario,
    p_iva: str,
    data_emissione: date,
    dispositivo: str,
    num: str,
) -> Built:
    body = (
        "<doc:cancellazioneDocumentoSpesaRequest>"
        + _head(pincode_encrypted, prop)
        + "<doc:idCancellazioneDocumentoFiscale>"
        + _id_spesa((p_iva, data_emissione, dispositivo, num))
        + "</doc:idCancellazioneDocumentoFiscale></doc:cancellazioneDocumentoSpesaRequest>"
    )
    return Built("cancellazione", _envelope(body))


def build_rimborso(
    pincode_encrypted: str,
    prop: Proprietario,
    original: tuple[str, date, str, str],
    refund: DocumentoSpesa,
) -> Built:
    """``idRimborsoDocumentoFiscale`` = the refunded (original) document;
    ``DocumentoSpesa`` = the refund document itself (positive amounts)."""
    body = (
        "<doc:rimborsoDocumentoSpesaRequest>"
        + _head(pincode_encrypted, prop)
        + "<doc:idRimborsoDocumentoFiscale>"
        + _id_spesa(original)
        + "</doc:idRimborsoDocumentoFiscale><doc:DocumentoSpesa>"
        + _documento(refund, with_flags=False)
        + "</doc:DocumentoSpesa></doc:rimborsoDocumentoSpesaRequest>"
    )
    return Built("rimborso", _envelope(body))
