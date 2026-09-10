"""PEC worker: send pending rows, back off on failure, apply polled receipts."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.auth.models import Clinic
from app.core.email.encryption import encrypt_password
from app.modules.sdi_it.models import SdiItRecord, SdiItSettings
from app.modules.sdi_it.services import pec_transport as pt
from app.modules.sdi_it.services import submission_queue as q

NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/messaggi/v1.0"


async def _setup(db, *, transport="pec", enabled=True):
    clinic = Clinic(
        id=uuid4(), name="Rossi", tax_id="01234567897", currency="EUR", settings={"country": "IT"}
    )
    db.add(clinic)
    settings = SdiItSettings(
        clinic_id=clinic.id,
        enabled=enabled,
        transport=transport,
        pec_address="studio@pec.example.it",
        smtp_host="smtps.example.it",
        imap_host="imaps.example.it",
        smtp_username="studio@pec.example.it",
        smtp_password_encrypted=encrypt_password("pw"),
    )
    db.add(settings)
    from app.core.auth.models import User
    from app.modules.billing.models import Invoice
    from app.modules.patients.models import Patient

    user = User(
        id=uuid4(), email=f"u-{uuid4()}@x.test", password_hash="x", first_name="A", last_name="B"
    )
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="M", last_name="R")
    db.add_all([user, patient])
    invoice = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        invoice_number="E/1",
        sequential_number=1,
        status="issued",
        issue_date=datetime.now(UTC).date(),
        billing_name="Alfa",
        billing_tax_id="00000000000",
        subtotal=Decimal("10"),
        total=Decimal("10"),
        created_by=user.id,
        issued_by=user.id,
    )
    db.add(invoice)
    await db.flush()
    rec = SdiItRecord(
        clinic_id=clinic.id,
        invoice_id=invoice.id,
        tipo_documento="TD01",
        invoice_number="E/1",
        issue_date=invoice.issue_date,
        gross_amount=Decimal("10"),
        codice_destinatario="0000000",
        progressivo="00001",
        file_name="IT01234567897_00001.xml",
        xml_payload="<x/>",
        state="pending",
        created_at=datetime.now(UTC),
    )
    db.add(rec)
    await db.commit()
    return clinic, settings, rec


@pytest.mark.asyncio
async def test_tick_sends_pending_and_applies_receipts(db_session, monkeypatch):
    clinic, settings, rec = await _setup(db_session)
    sent = []

    async def fake_send(creds, to, name, xml):
        sent.append((to, name))
        return "<mid@pec>"

    async def fake_poll(creds, limit=50):
        rc = (
            f'<ns3:RicevutaConsegna xmlns:ns3="{NS}"><IdentificativoSdI>9</IdentificativoSdI>'
            "<NomeFile>IT01234567897_00001.xml</NomeFile></ns3:RicevutaConsegna>"
        )
        return pt.PollResult(
            receipts=[
                pt.InboundReceipt(
                    uid=b"1",
                    file_name="IT01234567897_00001_RC_001.xml",
                    xml=rc,
                    sender="sdi07@pec.fatturapa.it",
                )
            ],
            sdi_reply_address="sdi07@pec.fatturapa.it",
        )

    monkeypatch.setattr(pt, "send_file", fake_send)
    monkeypatch.setattr(pt, "poll_receipts", fake_poll)
    counters = await q.process_clinic(db_session, clinic.id)
    assert counters == {"sent": 1, "failed": 0, "receipts": 1, "unmatched": 0}
    assert sent == [("sdi01@pec.fatturapa.it", "IT01234567897_00001.xml")]
    await db_session.refresh(rec)
    await db_session.refresh(settings)
    assert rec.state == "delivered" and rec.transport == "pec" and rec.message_id == "<mid@pec>"
    assert rec.sdi_identifier == "9" and rec.receipt_type == "RC"
    assert settings.sdi_pec_address == "sdi07@pec.fatturapa.it"  # learned from the reply
    assert settings.last_pec_poll_at is not None and settings.last_error is None


@pytest.mark.asyncio
async def test_smtp_failure_backs_off_and_pauses_the_clinic(db_session, monkeypatch):
    clinic, settings, rec = await _setup(db_session)

    async def boom(*a, **k):
        raise pt.PecError("SMTP: 535 bad login")

    monkeypatch.setattr(pt, "send_file", boom)
    counters = await q.process_clinic(db_session, clinic.id)
    assert counters["failed"] == 1 and counters["sent"] == 0
    await db_session.refresh(rec)
    await db_session.refresh(settings)
    assert rec.state == "pending" and rec.attempts == 1 and rec.next_attempt_at is not None
    assert "535" in rec.error_message and settings.next_send_after is not None
    # Paused: the next tick does nothing until next_send_after passes.
    assert await q.process_clinic(db_session, clinic.id) == {
        "sent": 0,
        "failed": 0,
        "receipts": 0,
        "unmatched": 0,
    }


@pytest.mark.asyncio
async def test_manual_transport_and_disabled_are_inert(db_session, monkeypatch):
    clinic, settings, rec = await _setup(db_session, transport="manual")

    async def never(*a, **k):
        raise AssertionError("must not be called")

    monkeypatch.setattr(pt, "send_file", never)
    monkeypatch.setattr(pt, "poll_receipts", never)
    assert (await q.process_clinic(db_session, clinic.id))["sent"] == 0
    settings.transport = "pec"
    settings.enabled = False
    await db_session.commit()
    assert (await q.process_clinic(db_session, clinic.id))["sent"] == 0
    assert (await db_session.execute(select(SdiItRecord.state))).scalar_one() == "pending"


@pytest.mark.asyncio
async def test_unmatched_receipt_is_counted_not_fatal(db_session, monkeypatch):
    clinic, settings, rec = await _setup(db_session)
    rec.state = "exported"
    await db_session.commit()

    async def fake_poll(creds, limit=50):
        rc = f'<ns3:RicevutaConsegna xmlns:ns3="{NS}"><NomeFile>IT99999999999_00009.xml</NomeFile></ns3:RicevutaConsegna>'
        return pt.PollResult(
            receipts=[
                pt.InboundReceipt(
                    uid=b"2",
                    file_name="IT99999999999_00009_RC_001.xml",
                    xml=rc,
                    sender="sdi07@pec.fatturapa.it",
                )
            ]
        )

    monkeypatch.setattr(pt, "poll_receipts", fake_poll)
    counters = await q.process_clinic(db_session, clinic.id)
    assert counters["unmatched"] == 1 and counters["receipts"] == 0
