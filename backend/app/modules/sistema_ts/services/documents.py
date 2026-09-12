"""From billing invoices to Sistema TS documents (ADR 0026 §2–3).

``sync_clinic`` finds what the Sistema TS must hear about and adds
``pending`` rows; ``build_request`` renders a row into the SOAP request
with the encrypted fields. Reads ``billing``, ``patients`` and ``catalog``
(all declared dependencies); writes only ``sistema_ts_*``.

Which invoices:
* paid invoices to natural persons (``billing_tax_id`` not a partita IVA,
  the patient's codice fiscale known) → ``inserimento``;
* credit notes whose original was accepted → ``rimborso``;
* voided invoices whose ``inserimento`` was accepted → ``cancellazione``;
* an opposition change after acceptance → ``variazione`` (the same document
  without / with the codice fiscale).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth.models import Clinic
from app.core.email.encryption import decrypt_password
from app.modules.billing.models import Invoice, InvoicePayment
from app.modules.patients.models import Patient
from app.modules.payments.models import Payment

from ..models import (
    SistemaTsDocument,
    SistemaTsItemType,
    SistemaTsPatientOpposition,
    SistemaTsSettings,
)
from . import xml_builder
from .codice_fiscale import is_partita_iva, normalise_codice_fiscale
from .crypto import encrypt_field

UNTRACEABLE_METHODS = {"cash"}
EXEMPT_NATURA = "N4"  # esenti art. 10 n. 18 DPR 633/72


class DocumentError(ValueError):
    pass


@dataclass
class ClinicIdentity:
    p_iva: str
    cf_proprietario: str
    dispositivo: str


async def clinic_identity(db: AsyncSession, settings: SistemaTsSettings) -> ClinicIdentity:
    clinic = (await db.execute(select(Clinic).where(Clinic.id == settings.clinic_id))).scalar_one()
    tax = "".join(c for c in (clinic.tax_id or "") if c.isalnum()).upper()
    if tax.startswith("IT") and len(tax) == 13:
        tax = tax[2:]
    if not is_partita_iva(tax):
        raise DocumentError("La partita IVA della clinica non è valida (11 cifre).")
    cf = (
        normalise_codice_fiscale(settings.cf_proprietario)
        or (settings.cf_proprietario or "").upper()
    )
    if not cf:
        raise DocumentError(
            "Imposta il codice fiscale del proprietario nelle impostazioni Sistema TS."
        )
    return ClinicIdentity(p_iva=tax, cf_proprietario=cf, dispositivo=settings.dispositivo or "1")


async def is_opposed(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID, on: date | None = None
) -> bool:
    row = (
        await db.execute(
            select(SistemaTsPatientOpposition).where(
                SistemaTsPatientOpposition.clinic_id == clinic_id,
                SistemaTsPatientOpposition.patient_id == patient_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    return row.revoked_at is None


async def _item_types(db: AsyncSession, clinic_id: UUID) -> dict[UUID, tuple[str, str | None]]:
    rows = (
        await db.execute(select(SistemaTsItemType).where(SistemaTsItemType.clinic_id == clinic_id))
    ).scalars()
    return {r.catalog_item_id: (r.tipo_spesa, r.flag_tipo_spesa) for r in rows}


async def _payment_info(db: AsyncSession, invoice: Invoice) -> tuple[date | None, str]:
    """Latest payment date and SI/NO traceability across the invoice's payments."""
    rows = (
        await db.execute(
            select(Payment.payment_date, Payment.method)
            .join(InvoicePayment, InvoicePayment.payment_id == Payment.id)
            .where(
                InvoicePayment.invoice_id == invoice.id,
                InvoicePayment.clinic_id == invoice.clinic_id,
            )
        )
    ).all()
    if not rows:
        return None, "SI"
    latest = max(r[0] for r in rows)
    tracciato = "NO" if any((r[1] or "").lower() in UNTRACEABLE_METHODS for r in rows) else "SI"
    return latest, tracciato


def _voci_from_items(invoice: Invoice, item_types, default_tipo: str) -> list[dict]:
    groups: dict[tuple[str, str | None, str | None, str | None], Decimal] = {}
    for item in invoice.items:
        tipo, flag = (
            item_types.get(item.catalog_item_id, (default_tipo, None))
            if item.catalog_item_id
            else (default_tipo, None)
        )
        rate = Decimal(str(item.vat_rate or 0))
        aliquota = str(rate.quantize(Decimal("0.01"))) if rate > 0 else None
        natura = None if rate > 0 else EXEMPT_NATURA
        key = (tipo, flag, aliquota, natura)
        groups[key] = groups.get(key, Decimal(0)) + Decimal(str(item.line_total or 0))
    if not groups:
        raise DocumentError("La fattura non ha righe.")
    return [
        {
            "tipo_spesa": t,
            "flag_tipo_spesa": f,
            "importo": str(v.quantize(Decimal("0.01"))),
            "aliquota_iva": a,
            "natura_iva": n,
        }
        for (t, f, a, n), v in groups.items()
        if v > 0
    ]


async def _new_document(
    db: AsyncSession,
    settings: SistemaTsSettings,
    ident: ClinicIdentity,
    invoice: Invoice,
    operation: str,
    *,
    refers_to: SistemaTsDocument | None = None,
) -> SistemaTsDocument:
    item_types = await _item_types(db, invoice.clinic_id)
    paid_on, tracciato = await _payment_info(db, invoice)
    opposed = await is_opposed(db, invoice.clinic_id, invoice.patient_id)
    doc = SistemaTsDocument(
        clinic_id=invoice.clinic_id,
        invoice_id=invoice.id,
        patient_id=invoice.patient_id,
        operation=operation,
        p_iva=ident.p_iva,
        data_emissione=invoice.issue_date,
        dispositivo=ident.dispositivo,
        num_documento=(invoice.invoice_number or "")[:60],
        data_pagamento=paid_on or invoice.issue_date,
        tipo_documento="F",
        pagamento_tracciato=tracciato,
        flag_opposizione=opposed,
        total_amount=Decimal(str(invoice.total or 0)),
        voci=_voci_from_items(invoice, item_types, settings.default_tipo_spesa),
        refers_to_id=refers_to.id if refers_to else None,
        state="pending",
        created_at=datetime.now(UTC),
        environment=settings.environment,
    )
    db.add(doc)
    await db.flush()
    return doc


async def _latest(db: AsyncSession, invoice_id: UUID, operation: str) -> SistemaTsDocument | None:
    return (
        (
            await db.execute(
                select(SistemaTsDocument)
                .where(
                    SistemaTsDocument.invoice_id == invoice_id,
                    SistemaTsDocument.operation == operation,
                )
                .order_by(SistemaTsDocument.created_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )


def _is_patient_invoice(invoice: Invoice) -> bool:
    return not is_partita_iva(invoice.billing_tax_id)


async def sync_clinic(db: AsyncSession, settings: SistemaTsSettings) -> dict[str, int]:
    """Create pending documents for everything new. Returns counters."""
    counters = {"inserimento": 0, "rimborso": 0, "cancellazione": 0, "skipped": 0}
    ident = await clinic_identity(db, settings)
    since = settings.sync_from
    base = (
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.clinic_id == settings.clinic_id, Invoice.deleted_at.is_(None))
    )
    if since:
        base = base.where(Invoice.issue_date >= since)

    # 1. paid invoices → inserimento
    paid = (
        (
            await db.execute(
                base.where(Invoice.status == "paid", Invoice.credit_note_for_id.is_(None))
            )
        )
        .scalars()
        .all()
    )
    for inv in paid:
        if not _is_patient_invoice(inv) or not inv.issue_date or not inv.invoice_number:
            counters["skipped"] += 1
            continue
        if await _latest(db, inv.id, "inserimento") is not None:
            continue
        await _new_document(db, settings, ident, inv, "inserimento")
        counters["inserimento"] += 1

    # 2. credit notes whose original was accepted → rimborso
    notes = (
        (
            await db.execute(
                base.where(
                    Invoice.credit_note_for_id.is_not(None), Invoice.status.in_(("issued", "paid"))
                )
            )
        )
        .scalars()
        .all()
    )
    for note in notes:
        if await _latest(db, note.id, "rimborso") is not None:
            continue
        original = await _latest(db, note.credit_note_for_id, "inserimento")
        if original is None or not original.state.startswith("accepted"):
            continue
        await _new_document(db, settings, ident, note, "rimborso", refers_to=original)
        counters["rimborso"] += 1

    # 3. voided invoices with an accepted inserimento → cancellazione
    voided = (
        (
            await db.execute(
                base.where(Invoice.status == "voided", Invoice.credit_note_for_id.is_(None))
            )
        )
        .scalars()
        .all()
    )
    for inv in voided:
        original = await _latest(db, inv.id, "inserimento")
        if original is None or not original.state.startswith("accepted"):
            continue
        if await _latest(db, inv.id, "cancellazione") is not None:
            continue
        await _new_document(db, settings, ident, inv, "cancellazione", refers_to=original)
        counters["cancellazione"] += 1
    await db.flush()
    return counters


async def queue_variazioni_for_patient(
    db: AsyncSession, settings: SistemaTsSettings, patient_id: UUID
) -> int:
    """After an opposition change: resend every accepted document of the patient."""
    ident = await clinic_identity(db, settings)
    accepted = (
        (
            await db.execute(
                select(SistemaTsDocument).where(
                    SistemaTsDocument.clinic_id == settings.clinic_id,
                    SistemaTsDocument.patient_id == patient_id,
                    SistemaTsDocument.operation == "inserimento",
                    SistemaTsDocument.state.in_(("accepted", "accepted_with_warnings")),
                )
            )
        )
        .scalars()
        .all()
    )
    n = 0
    for doc in accepted:
        invoice = (
            await db.execute(
                select(Invoice)
                .options(selectinload(Invoice.items))
                .where(Invoice.id == doc.invoice_id)
            )
        ).scalar_one_or_none()
        if invoice is None or invoice.status == "voided":
            continue
        pending = await _latest(db, invoice.id, "variazione")
        if pending is not None and pending.state == "pending":
            continue
        await _new_document(db, settings, ident, invoice, "variazione", refers_to=doc)
        n += 1
    await db.flush()
    return n


def _cert_bytes(settings: SistemaTsSettings) -> bytes | None:
    if not settings.certificate_b64:
        return None
    try:
        return base64.b64decode(settings.certificate_b64)
    except ValueError:
        return None


async def build_request(
    db: AsyncSession, settings: SistemaTsSettings, doc: SistemaTsDocument
) -> str:
    """Render the SOAP request for ``doc`` (encrypting pincode and codici fiscali)."""
    if not settings.pincode_encrypted:
        raise DocumentError("Pincode Sistema TS mancante.")
    cert = _cert_bytes(settings)
    pincode = encrypt_field(decrypt_password(settings.pincode_encrypted), cert)
    prop = xml_builder.Proprietario(
        cf_proprietario_encrypted=encrypt_field(doc_cf_proprietario(settings), cert),
        codice_regione=settings.codice_regione or None,
        codice_asl=settings.codice_asl or None,
        codice_ssa=settings.codice_ssa or None,
    )
    ident = (doc.p_iva, doc.data_emissione, doc.dispositivo, doc.num_documento)
    if doc.operation == "cancellazione":
        return xml_builder.build_cancellazione(pincode, prop, *ident).xml

    cf_encrypted: str | None = None
    if not doc.flag_opposizione:
        patient = (
            await db.execute(select(Patient).where(Patient.id == doc.patient_id))
        ).scalar_one_or_none()
        cf = normalise_codice_fiscale(patient.national_id if patient else None)
        if cf is None:
            raise DocumentError("Codice fiscale del paziente mancante o non valido.")
        cf_encrypted = encrypt_field(cf, cert)
    voci = tuple(
        xml_builder.Voce(
            tipo_spesa=v["tipo_spesa"],
            importo=Decimal(v["importo"]),
            flag_tipo_spesa=v.get("flag_tipo_spesa"),
            aliquota_iva=Decimal(v["aliquota_iva"]) if v.get("aliquota_iva") else None,
            natura_iva=v.get("natura_iva"),
        )
        for v in doc.voci
    )
    documento = xml_builder.DocumentoSpesa(
        p_iva=doc.p_iva,
        data_emissione=doc.data_emissione,
        dispositivo=doc.dispositivo,
        num_documento=doc.num_documento,
        data_pagamento=doc.data_pagamento or doc.data_emissione,
        cf_cittadino_encrypted=cf_encrypted,
        voci=voci,
        pagamento_tracciato=doc.pagamento_tracciato,
        tipo_documento=doc.tipo_documento,
        flag_pagamento_anticipato=bool(
            doc.data_pagamento and doc.data_pagamento < doc.data_emissione
        ),
    )
    if doc.operation == "inserimento":
        return xml_builder.build_inserimento(pincode, prop, documento).xml
    if doc.operation == "variazione":
        return xml_builder.build_variazione(pincode, prop, documento).xml
    if doc.operation == "rimborso":
        original = (
            await db.execute(
                select(SistemaTsDocument).where(SistemaTsDocument.id == doc.refers_to_id)
            )
        ).scalar_one_or_none()
        if original is None:
            raise DocumentError("Documento originale del rimborso non trovato.")
        return xml_builder.build_rimborso(
            pincode,
            prop,
            (original.p_iva, original.data_emissione, original.dispositivo, original.num_documento),
            documento,
        ).xml
    raise DocumentError(f"Operazione sconosciuta: {doc.operation}")


def doc_cf_proprietario(settings: SistemaTsSettings) -> str:
    return (
        normalise_codice_fiscale(settings.cf_proprietario) or settings.cf_proprietario or ""
    ).upper()
