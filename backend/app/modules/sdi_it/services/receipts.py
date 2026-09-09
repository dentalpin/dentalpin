"""Parse the SDI's receipts for an FPR12 file (spec §1.5.7, file-name table
"Tipo di messaggio"):

* ``RC`` ricevuta di consegna — delivered, terminal.
* ``NS`` notifica di scarto — rejected; ``ListaErrori`` says why; the
  invoice is *not issued* and must be re-sent with the same number/date.
* ``MC`` ricevuta di impossibilità di recapito (element still named
  ``NotificaMancataConsegna`` in the messages schema) — the invoice is
  issued and parked in the recipient's area riservata; the practice must
  tell the recipient.

Only the fields the module acts on are read; the raw XML is stored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree

_ROOT_TO_TYPE = {
    "RicevutaConsegna": "RC",
    "NotificaScarto": "NS",
    "NotificaMancataConsegna": "MC",
    "RicevutaImpossibilitaRecapito": "MC",
    "MetadatiInvioFile": "MT",
    "AttestazioneTrasmissioneFattura": "AT",
    "NotificaEsito": "NE",
    "NotificaDecorrenzaTermini": "DT",
}
_NAME_RE = re.compile(
    r"^(?P<file>IT[A-Z0-9]{1,28}_[A-Za-z0-9]{1,10})_(?P<type>RC|NS|MC|MT|AT|NE|DT|EC)_[A-Za-z0-9]{1,3}\.xml$"
)


class ReceiptError(ValueError):
    pass


@dataclass
class Receipt:
    type: str  # RC | NS | MC | ...
    identificativo_sdi: str | None
    nome_file: str | None
    received_at: str | None
    delivered_at: str | None = None
    errors: list[tuple[str, str]] = field(default_factory=list)
    note: str | None = None

    @property
    def invoice_file_name(self) -> str | None:
        """``IT…_00001.xml`` the receipt refers to (``NomeFile``)."""
        return self.nome_file


def _local(el: etree._Element) -> str:
    return etree.QName(el).localname


def _first_text(root: etree._Element, name: str) -> str | None:
    for el in root.iter():
        if isinstance(el.tag, str) and _local(el) == name and (el.text or "").strip():
            return el.text.strip()
    return None


def parse_receipt(xml: str | bytes, *, receipt_file_name: str | None = None) -> Receipt:
    try:
        root = etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    except etree.XMLSyntaxError as exc:  # pragma: no cover - message text varies
        raise ReceiptError(f"XML non valido: {exc}") from exc
    rtype = _ROOT_TO_TYPE.get(_local(root))
    if rtype is None and receipt_file_name:
        m = _NAME_RE.match(receipt_file_name)
        rtype = m.group("type") if m else None
    if rtype is None:
        raise ReceiptError(f"Tipo di ricevuta SDI non riconosciuto: <{_local(root)}>")
    errors: list[tuple[str, str]] = []
    for err in root.iter():
        if isinstance(err.tag, str) and _local(err) == "Errore":
            code = _first_text(err, "Codice") or ""
            desc = _first_text(err, "Descrizione") or ""
            errors.append((code, desc))
    return Receipt(
        type=rtype,
        identificativo_sdi=_first_text(root, "IdentificativoSdI"),
        nome_file=_first_text(root, "NomeFile"),
        received_at=_first_text(root, "DataOraRicezione"),
        delivered_at=_first_text(root, "DataOraConsegna"),
        errors=errors,
        note=_first_text(root, "Note"),
    )


STATE_FOR_RECEIPT = {"RC": "delivered", "NS": "rejected", "MC": "undeliverable"}
