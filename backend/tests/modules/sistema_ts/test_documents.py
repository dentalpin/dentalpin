"""sync_clinic: what becomes a document, with which contents."""

from datetime import date

import pytest
from sqlalchemy import select

from app.modules.sistema_ts.models import (
    SistemaTsDocument,
    SistemaTsPatientOpposition,
)
from app.modules.sistema_ts.services import documents as docs
from app.modules.sistema_ts.services.documents import build_request, sync_clinic

from ._fixtures import PIVA, make_clinic, make_invoice, make_patient


@pytest.mark.asyncio
async def test_paid_patient_invoice_becomes_an_inserimento_with_grouped_voci(db_session):
    clinic, user, settings = await make_clinic(db_session)
    patient = await make_patient(db_session, clinic)
    inv = await make_invoice(db_session, clinic, user, patient)
    counters = await sync_clinic(db_session, settings)
    assert counters["inserimento"] == 1
    doc = (await db_session.execute(select(SistemaTsDocument))).scalar_one()
    assert doc.operation == "inserimento" and doc.state == "pending" and doc.invoice_id == inv.id
    assert doc.p_iva == PIVA and doc.num_documento == "FAC/2026/0001" and doc.dispositivo == "1"
    assert doc.data_emissione == date(2026, 3, 2) and doc.data_pagamento == date(2026, 3, 5)
    assert doc.pagamento_tracciato == "SI" and not doc.flag_opposizione
    assert sorted(
        (v["tipo_spesa"], v["importo"], v["natura_iva"], v["aliquota_iva"]) for v in doc.voci
    ) == [
        ("SR", "40.00", None, "22.00"),
        ("SR", "60.00", "N4", None),
    ]
    # Idempotent: a second sync adds nothing.
    assert (await sync_clinic(db_session, settings))["inserimento"] == 0


@pytest.mark.asyncio
async def test_b2b_unpaid_and_cash_rules(db_session):
    clinic, user, settings = await make_clinic(db_session)
    patient = await make_patient(db_session, clinic)
    await make_invoice(
        db_session, clinic, user, patient, number="B2B/1", tax_id="00000000000"
    )  # insurer → SDI's
    await make_invoice(
        db_session, clinic, user, patient, number="OPEN/1", status="issued", pay=None
    )
    cash = await make_invoice(db_session, clinic, user, patient, number="CASH/1", method="cash")
    counters = await sync_clinic(db_session, settings)
    assert counters == {"inserimento": 1, "rimborso": 0, "cancellazione": 0, "skipped": 1}
    doc = (await db_session.execute(select(SistemaTsDocument))).scalar_one()
    assert doc.invoice_id == cash.id and doc.pagamento_tracciato == "NO"


@pytest.mark.asyncio
async def test_item_type_mapping_and_opposition(db_session):
    clinic, user, settings = await make_clinic(db_session)
    patient = await make_patient(db_session, clinic)

    await make_invoice(db_session, clinic, user, patient, lines=(("Sbiancamento", "100.00", 22.0),))
    db_session.add(
        SistemaTsPatientOpposition(
            clinic_id=clinic.id, patient_id=patient.id, opposed_since=date(2026, 1, 1)
        )
    )
    await db_session.flush()
    await sync_clinic(db_session, settings)
    doc = (await db_session.execute(select(SistemaTsDocument))).scalar_one()
    assert doc.flag_opposizione is True
    xml = await build_request(db_session, settings, doc)
    assert "cfCittadino" not in xml and "<doc:flagOpposizione>1</doc:flagOpposizione>" in xml
    assert "<doc:pincode>" in xml and "1234567890" not in xml  # encrypted, never in clear


@pytest.mark.asyncio
async def test_credit_note_and_void_follow_an_accepted_inserimento(db_session):
    clinic, user, settings = await make_clinic(db_session)
    patient = await make_patient(db_session, clinic)
    inv = await make_invoice(db_session, clinic, user, patient)
    note = await make_invoice(
        db_session,
        clinic,
        user,
        patient,
        number="NC/1",
        status="issued",
        pay=None,
        credit_note_for=inv.id,
    )
    await sync_clinic(db_session, settings)
    # Not yet: the original is still pending.
    assert (
        await db_session.execute(
            select(SistemaTsDocument).where(SistemaTsDocument.operation == "rimborso")
        )
    ).first() is None
    original = (
        await db_session.execute(
            select(SistemaTsDocument).where(SistemaTsDocument.operation == "inserimento")
        )
    ).scalar_one()
    original.state = "accepted"
    original.protocollo = "1" * 17
    await db_session.flush()
    counters = await sync_clinic(db_session, settings)
    assert counters["rimborso"] == 1
    rimborso = (
        await db_session.execute(
            select(SistemaTsDocument).where(SistemaTsDocument.operation == "rimborso")
        )
    ).scalar_one()
    assert rimborso.invoice_id == note.id and rimborso.refers_to_id == original.id
    xml = await build_request(db_session, settings, rimborso)
    assert "<doc:idRimborsoDocumentoFiscale>" in xml and "FAC/2026/0001" in xml and "NC/1" in xml
    inv.status = "voided"
    await db_session.flush()
    assert (await sync_clinic(db_session, settings))["cancellazione"] == 1
    canc = (
        await db_session.execute(
            select(SistemaTsDocument).where(SistemaTsDocument.operation == "cancellazione")
        )
    ).scalar_one()
    xml = await build_request(db_session, settings, canc)
    assert "<doc:idCancellazioneDocumentoFiscale>" in xml and "cfCittadino" not in xml


@pytest.mark.asyncio
async def test_missing_patient_cf_is_a_document_error(db_session):
    clinic, user, settings = await make_clinic(db_session)
    patient = await make_patient(db_session, clinic, cf=None)
    await make_invoice(db_session, clinic, user, patient)
    await sync_clinic(db_session, settings)
    doc = (await db_session.execute(select(SistemaTsDocument))).scalar_one()
    with pytest.raises(docs.DocumentError, match="Codice fiscale"):
        await build_request(db_session, settings, doc)


@pytest.mark.asyncio
async def test_sync_from_skips_older_invoices(db_session):
    clinic, user, settings = await make_clinic(db_session)
    settings.sync_from = date(2026, 6, 1)
    patient = await make_patient(db_session, clinic)
    await make_invoice(db_session, clinic, user, patient, issue=date(2026, 3, 2))
    assert (await sync_clinic(db_session, settings))["inserimento"] == 0
