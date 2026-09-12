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


# --- applying a receipt to a record (shared by the API import and the PEC poller)

from datetime import UTC, datetime  # noqa: E402
from typing import TYPE_CHECKING  # noqa: E402

from sqlalchemy import select  # noqa: E402

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from ..models import SdiItRecord


class ReceiptUnmatchedError(ReceiptError):
    """No record of this clinic carries the ``NomeFile`` the receipt names."""


class ReceiptAlreadyAppliedError(ReceiptError):
    """The record already holds this receipt type in a terminal state."""


_TERMINAL = {"delivered", "undeliverable"}


async def apply_receipt(
    db: AsyncSession,
    clinic_id: UUID,
    xml: str,
    *,
    receipt_file_name: str | None = None,
) -> tuple[SdiItRecord, Receipt]:
    """Parse ``xml`` and move the matching record to the receipt's state.

    Matches by ``NomeFile`` (with or without the ``.p7m`` suffix), newest
    record first so a requeued invoice resolves to its latest file. Does
    not commit.
    """
    from ..models import SdiItRecord, SdiItSettings

    receipt = parse_receipt(xml, receipt_file_name=receipt_file_name)
    new_state = STATE_FOR_RECEIPT.get(receipt.type)
    if new_state is None:
        raise ReceiptError(f"Ricevuta {receipt.type} non applicabile a una fattura FPR12")
    if not receipt.nome_file:
        raise ReceiptError("La ricevuta non indica il NomeFile")
    stem = receipt.nome_file.rsplit(".", 1)[0]
    row = (
        (
            await db.execute(
                select(SdiItRecord)
                .where(
                    SdiItRecord.clinic_id == clinic_id,
                    SdiItRecord.file_name.in_(
                        (receipt.nome_file, f"{stem}.xml", f"{stem}.xml.p7m")
                    ),
                )
                .order_by(SdiItRecord.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        raise ReceiptUnmatchedError(f"Nessun record per il file {receipt.nome_file}")
    if row.state in _TERMINAL and row.receipt_type == receipt.type:
        raise ReceiptAlreadyAppliedError("Ricevuta già importata")
    now = datetime.now(UTC)
    row.state = new_state
    row.receipt_type = receipt.type
    row.receipt_xml = xml
    row.receipt_at = now
    row.sdi_identifier = receipt.identificativo_sdi or row.sdi_identifier
    row.finished_at = now
    if receipt.type == "NS":
        row.error_code = ", ".join(c for c, _ in receipt.errors)[:60] or "NS"
        row.error_message = "; ".join(f"{c}: {d}" for c, d in receipt.errors)[:2000] or receipt.note
    else:
        row.error_code = None
        row.error_message = receipt.note if receipt.type == "MC" else None
    settings = (
        await db.execute(select(SdiItSettings).where(SdiItSettings.clinic_id == clinic_id))
    ).scalar_one_or_none()
    if settings is not None:
        settings.last_receipt_at = now
    from .invoice_state import sync_invoice_state

    await sync_invoice_state(db, row)
    return row, receipt
