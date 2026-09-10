"""FatturaPA ``FPR12`` XML (schema v1.2, Specifiche tecniche v1.9) from a
billing invoice — the subset an Italian dental practice's **B2B** invoices
need (ADR 0025 §2):

* ``TipoDocumento`` ``TD01`` (fattura) or ``TD04`` (nota di credito, with
  ``DatiFattureCollegate`` to the original number).
* Exempt healthcare lines: ``AliquotaIVA`` 0.00 + ``Natura`` ``N4`` and a
  riepilogo carrying ``RiferimentoNormativo`` (art. 10 n. 18 DPR 633/72).
  Taxable lines (e.g. cosmetic work at 22 %) carry their rate, no Natura.
* ``DatiBollo`` (virtual €2 stamp) when the exempt total exceeds €77.47
  (art. 13 tariffa DPR 642/1972) and the clinic opted in.
* ``CodiceDestinatario`` from the recipient's ``billing_address`` keys
  ``sdi_code`` / ``pec``; otherwise ``0000000`` (the SDI leaves the
  invoice in the recipient's area riservata).
* ``DatiPagamento``: ``TP02`` (single payment) with ``MP05`` (bonifico)
  as the neutral method and the invoice due date.

Unsigned (the SDI accepts unsigned FPR12 files, spec §1.2.1). File name
per spec §1.2.2: ``IT<IdCodice>_<progressivo>.xml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import escape

from .tax_ids import CodiceFiscale, PartitaIva

if TYPE_CHECKING:
    from app.modules.billing.models import Invoice

NS_FATTURA = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
FORMATO = "FPR12"
NATURA_ESENTE = "N4"
DEFAULT_RIFERIMENTO_NORMATIVO = "Esente IVA art. 10 n. 18 DPR 633/72"
BOLLO_THRESHOLD = Decimal("77.47")
BOLLO_AMOUNT = Decimal("2.00")
DEFAULT_CODICE_DESTINATARIO = "0000000"

_Q2 = Decimal("0.01")
_ALNUM36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class SdiBuildError(ValueError):
    """The invoice or clinic lacks something the FPR12 schema requires."""


def _d(value: Decimal | float | int | str | None) -> Decimal:
    return Decimal(str(value or 0))


def _money(value: Decimal | float | int | str | None) -> str:
    return str(abs(_d(value)).quantize(_Q2, rounding=ROUND_HALF_UP))


def _rate(value: float | Decimal | None) -> str:
    return str(_d(value).quantize(_Q2, rounding=ROUND_HALF_UP))


def _text(value: Any, limit: int) -> str:
    s = " ".join(str(value or "").split())
    return escape(s[:limit])


def progressivo_invio(counter: int) -> str:
    """5-char base-36 progressivo (spec: alphanumeric, ≤ 10 chars, unique per transmitter)."""
    n = max(int(counter), 0)
    out = ""
    while True:
        n, rem = divmod(n, 36)
        out = _ALNUM36[rem] + out
        if n == 0:
            break
    return out.rjust(5, "0")


def file_name(id_codice: str, progressivo: str) -> str:
    return f"IT{id_codice}_{progressivo}.xml"


@dataclass(frozen=True)
class Party:
    """Cedente or cessionario as the schema wants it."""

    denominazione: str
    partita_iva: str | None
    codice_fiscale: str | None
    indirizzo: str
    cap: str
    comune: str
    provincia: str | None
    nazione: str = "IT"

    @classmethod
    def from_clinic(cls, *, tax_id: str | None, name: str, address: dict[str, Any] | None) -> Party:
        piva = PartitaIva.parse(tax_id)
        cf = CodiceFiscale.parse(tax_id)
        if piva is None:
            raise SdiBuildError("La partita IVA della clinica non è valida (11 cifre).")
        return cls(
            denominazione=name,
            partita_iva=piva.value,
            codice_fiscale=cf.value if cf and cf.is_natural_person else None,
            **_address_fields(address),
        )

    @classmethod
    def from_recipient(
        cls, *, tax_id: str | None, name: str | None, address: dict[str, Any] | None
    ) -> Party:
        piva = PartitaIva.parse(tax_id)
        cf = CodiceFiscale.parse(tax_id)
        if piva is None and cf is None:
            raise SdiBuildError(
                "Il destinatario non ha una partita IVA o un codice fiscale valido."
            )
        return cls(
            denominazione=name or "",
            partita_iva=piva.value if piva else None,
            codice_fiscale=cf.value if cf and (piva is None or cf.is_natural_person) else None,
            **_address_fields(address),
        )


def _address_fields(address: dict[str, Any] | None) -> dict[str, str | None]:
    a = address or {}
    cap = "".join(c for c in str(a.get("postal_code") or a.get("cap") or "") if c.isdigit())
    prov = str(a.get("province") or a.get("provincia") or "").strip().upper()[:2]
    nazione = str(a.get("country_code") or a.get("country") or "IT").strip().upper()[:2]
    return {
        "indirizzo": str(a.get("street") or a.get("address") or a.get("line1") or "").strip(),
        "cap": cap.zfill(5)[:5] if cap else "00000",
        "comune": str(a.get("city") or a.get("comune") or "").strip(),
        "provincia": prov if len(prov) == 2 and prov.isalpha() else None,
        "nazione": nazione if len(nazione) == 2 and nazione.isalpha() else "IT",
    }


def _party_xml(tag: str, p: Party, *, regime_fiscale: str | None) -> str:
    fiscal = ""
    if p.partita_iva:
        fiscal += f"<IdFiscaleIVA><IdPaese>{p.nazione}</IdPaese><IdCodice>{p.partita_iva}</IdCodice></IdFiscaleIVA>"
    if p.codice_fiscale:
        fiscal += f"<CodiceFiscale>{p.codice_fiscale}</CodiceFiscale>"
    anagrafica = f"<Anagrafica><Denominazione>{_text(p.denominazione or '-', 80)}</Denominazione></Anagrafica>"
    regime = f"<RegimeFiscale>{regime_fiscale}</RegimeFiscale>" if regime_fiscale else ""
    sede = (
        f"<Sede><Indirizzo>{_text(p.indirizzo or '-', 60)}</Indirizzo><CAP>{p.cap}</CAP>"
        f"<Comune>{_text(p.comune or '-', 60)}</Comune>"
        + (f"<Provincia>{p.provincia}</Provincia>" if p.provincia else "")
        + f"<Nazione>{p.nazione}</Nazione></Sede>"
    )
    return f"<{tag}><DatiAnagrafici>{fiscal}{anagrafica}{regime}</DatiAnagrafici>{sede}</{tag}>"


@dataclass
class Line:
    descrizione: str
    quantita: Decimal
    prezzo_unitario: Decimal
    sconto: Decimal
    prezzo_totale: Decimal
    aliquota: Decimal
    natura: str | None


@dataclass
class BuildResult:
    xml: str
    file_name: str
    tipo_documento: str
    invoice_number: str
    gross_amount: Decimal
    codice_destinatario: str
    bollo: bool = False
    lines: list[Line] = field(default_factory=list)


def _lines(invoice: Invoice) -> list[Line]:
    out: list[Line] = []
    for item in sorted(invoice.items, key=lambda i: (i.display_order, i.description)):
        rate = _d(item.vat_rate).quantize(_Q2)
        qty = _d(item.quantity or 1)
        unit = _d(item.unit_price)
        discount = _d(item.line_discount)
        total = (
            _d(item.line_subtotal) - discount
            if item.line_subtotal is not None
            else unit * qty - discount
        )
        out.append(
            Line(
                descrizione=item.description or "-",
                quantita=qty,
                prezzo_unitario=unit,
                sconto=discount,
                prezzo_totale=total,
                aliquota=rate,
                natura=NATURA_ESENTE if rate == 0 else None,
            )
        )
    if not out:
        raise SdiBuildError("La fattura non ha righe.")
    return out


def build_fattura(
    invoice: Invoice,
    *,
    cedente: Party,
    cessionario: Party,
    progressivo: str,
    regime_fiscale: str = "RF01",
    riferimento_normativo: str = DEFAULT_RIFERIMENTO_NORMATIVO,
    bollo_virtuale: bool = True,
    original_invoice_number: str | None = None,
    original_invoice_date: str | None = None,
) -> BuildResult:
    """Render the FPR12 file for ``invoice``.

    ``original_invoice_number`` set ⇒ ``TD04`` nota di credito referencing
    it. Amounts are rendered positive in both cases (the schema carries
    the sign in ``TipoDocumento``).
    """
    tipo = "TD04" if original_invoice_number else "TD01"
    if not invoice.invoice_number:
        raise SdiBuildError("La fattura non ha ancora un numero.")
    if not invoice.issue_date:
        raise SdiBuildError("La fattura non ha una data di emissione.")
    lines = _lines(invoice)

    # Riepilogo per (aliquota, natura). ``Imposta`` is the group's base × rate
    # rounded once: the SDI check (code 00421) compares it with
    # ImponibileImporto × AliquotaIVA within one cent, which a sum of
    # per-line roundings can miss on many small lines.
    bases: dict[tuple[Decimal, str | None], Decimal] = {}
    for ln in lines:
        key = (ln.aliquota, ln.natura)
        bases[key] = bases.get(key, Decimal(0)) + ln.prezzo_totale
    groups: dict[tuple[Decimal, str | None], tuple[Decimal, Decimal]] = {
        (rate, natura): (base, (base * rate / 100).quantize(_Q2, rounding=ROUND_HALF_UP))
        for (rate, natura), base in bases.items()
    }
    exempt_total = sum((b for (_, n), (b, _) in groups.items() if n), Decimal(0))
    bollo = bool(bollo_virtuale and exempt_total > BOLLO_THRESHOLD)
    # The stamp is the issuer's cost: billing has no bollo line, so the
    # document total stays what the client owes (re-charging it would need
    # an explicit N1 line in the invoice).
    total = sum((b + t for b, t in groups.values()), Decimal(0))

    address = invoice.billing_address or {}
    codice_dest = str(address.get("sdi_code") or "").strip().upper()
    if not (len(codice_dest) == 7 and codice_dest.isalnum()):
        codice_dest = DEFAULT_CODICE_DESTINATARIO
    pec = str(address.get("pec") or "").strip()
    pec_xml = (
        f"<PECDestinatario>{escape(pec)}</PECDestinatario>"
        if pec and codice_dest == DEFAULT_CODICE_DESTINATARIO
        else ""
    )

    header = (
        "<FatturaElettronicaHeader>"
        "<DatiTrasmissione>"
        f"<IdTrasmittente><IdPaese>{cedente.nazione}</IdPaese><IdCodice>{cedente.partita_iva}</IdCodice></IdTrasmittente>"
        f"<ProgressivoInvio>{escape(progressivo)}</ProgressivoInvio>"
        f"<FormatoTrasmissione>{FORMATO}</FormatoTrasmissione>"
        f"<CodiceDestinatario>{codice_dest}</CodiceDestinatario>{pec_xml}"
        "</DatiTrasmissione>"
        + _party_xml("CedentePrestatore", cedente, regime_fiscale=regime_fiscale)
        + _party_xml("CessionarioCommittente", cessionario, regime_fiscale=None)
        + "</FatturaElettronicaHeader>"
    )

    bollo_xml = (
        f"<DatiBollo><BolloVirtuale>SI</BolloVirtuale><ImportoBollo>{_money(BOLLO_AMOUNT)}</ImportoBollo></DatiBollo>"
        if bollo
        else ""
    )
    causale = (
        f"<Causale>{_text(invoice.public_notes, 200)}</Causale>" if invoice.public_notes else ""
    )
    collegate = ""
    if original_invoice_number:
        collegate = (
            f"<DatiFattureCollegate><IdDocumento>{_text(original_invoice_number, 20)}</IdDocumento>"
            + (f"<Data>{original_invoice_date}</Data>" if original_invoice_date else "")
            + "</DatiFattureCollegate>"
        )
    dati_generali = (
        "<DatiGenerali><DatiGeneraliDocumento>"
        f"<TipoDocumento>{tipo}</TipoDocumento><Divisa>EUR</Divisa>"
        f"<Data>{invoice.issue_date.isoformat()}</Data><Numero>{_text(invoice.invoice_number, 20)}</Numero>"
        f"{bollo_xml}<ImportoTotaleDocumento>{_money(total)}</ImportoTotaleDocumento>{causale}"
        f"</DatiGeneraliDocumento>{collegate}</DatiGenerali>"
    )

    dettaglio = ""
    for n, ln in enumerate(lines, start=1):
        sconto = (
            f"<ScontoMaggiorazione><Tipo>SC</Tipo><Importo>{_money(ln.sconto)}</Importo></ScontoMaggiorazione>"
            if ln.sconto > 0
            else ""
        )
        dettaglio += (
            f"<DettaglioLinee><NumeroLinea>{n}</NumeroLinea><Descrizione>{_text(ln.descrizione, 1000)}</Descrizione>"
            f"<Quantita>{_money(ln.quantita)}</Quantita><PrezzoUnitario>{_money(ln.prezzo_unitario)}</PrezzoUnitario>"
            f"{sconto}<PrezzoTotale>{_money(ln.prezzo_totale)}</PrezzoTotale><AliquotaIVA>{_rate(ln.aliquota)}</AliquotaIVA>"
            + (f"<Natura>{ln.natura}</Natura>" if ln.natura else "")
            + "</DettaglioLinee>"
        )
    riepilogo = ""
    for (aliquota, natura), (base, tax) in sorted(
        groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")
    ):
        riepilogo += (
            f"<DatiRiepilogo><AliquotaIVA>{_rate(aliquota)}</AliquotaIVA>"
            + (f"<Natura>{natura}</Natura>" if natura else "")
            + f"<ImponibileImporto>{_money(base)}</ImponibileImporto><Imposta>{_money(tax)}</Imposta>"
            "<EsigibilitaIVA>I</EsigibilitaIVA>"
            + (
                f"<RiferimentoNormativo>{_text(riferimento_normativo, 100)}</RiferimentoNormativo>"
                if natura
                else ""
            )
            + "</DatiRiepilogo>"
        )
    beni = f"<DatiBeniServizi>{dettaglio}{riepilogo}</DatiBeniServizi>"

    scadenza = (
        f"<DataScadenzaPagamento>{invoice.due_date.isoformat()}</DataScadenzaPagamento>"
        if invoice.due_date
        else ""
    )
    pagamento = (
        "<DatiPagamento><CondizioniPagamento>TP02</CondizioniPagamento><DettaglioPagamento>"
        f"<ModalitaPagamento>MP05</ModalitaPagamento>{scadenza}<ImportoPagamento>{_money(total)}</ImportoPagamento>"
        "</DettaglioPagamento></DatiPagamento>"
    )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<p:FatturaElettronica versione="{FORMATO}" xmlns:p="{NS_FATTURA}" '
        'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"{header}<FatturaElettronicaBody>{dati_generali}{beni}{pagamento}</FatturaElettronicaBody>"
        "</p:FatturaElettronica>"
    )
    return BuildResult(
        xml=xml,
        file_name=file_name(cedente.partita_iva or "", progressivo),
        tipo_documento=tipo,
        invoice_number=invoice.invoice_number,
        gross_amount=total.quantize(_Q2, rounding=ROUND_HALF_UP),
        codice_destinatario=codice_dest,
        bollo=bollo,
        lines=lines,
    )
