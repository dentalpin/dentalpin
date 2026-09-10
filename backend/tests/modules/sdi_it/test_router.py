"""sdi_it settings + records API: manual transport lifecycle."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.billing.models import Invoice, InvoiceItem
from app.modules.sdi_it.hook import SdiItHook
from app.modules.sdi_it.models import SdiItRecord, SdiItSettings

SETTINGS = "/api/v1/sdi_it/settings"
NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/messaggi/v1.0"


async def _queued_record(db, clinic, patient) -> SdiItRecord:
    clinic.tax_id = "01234567897"
    clinic.legal_name = "Studio Dentistico Rossi S.r.l."
    clinic.address = {
        "street": "Via Roma 1",
        "postal_code": "20121",
        "city": "Milano",
        "province": "MI",
    }
    db.add(SdiItSettings(clinic_id=clinic.id, enabled=True))
    user_id = (await db.execute(select(Invoice.created_by).limit(1))).scalar() or None
    from app.core.auth.models import User

    if user_id is None:
        user_id = (await db.execute(select(User.id).limit(1))).scalar()
    invoice = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        invoice_number="E/2026/0001",
        sequential_number=1,
        status="issued",
        issue_date=date(2026, 9, 7),
        billing_name="Assicurazioni Alfa S.p.A.",
        billing_tax_id="00000000000",
        billing_address={"street": "Corso Italia 10", "postal_code": "00100", "city": "Roma"},
        subtotal=Decimal("50.00"),
        total=Decimal("50.00"),
        created_by=user_id,
        issued_by=user_id,
    )
    db.add(invoice)
    await db.flush()
    db.add(
        InvoiceItem(
            id=uuid4(),
            clinic_id=clinic.id,
            invoice_id=invoice.id,
            description="Visita",
            unit_price=Decimal("50.00"),
            quantity=1,
            vat_rate=0.0,
            line_subtotal=Decimal("50.00"),
            line_total=Decimal("50.00"),
        )
    )
    await db.flush()
    await db.refresh(invoice, attribute_names=["items"])
    out = await SdiItHook().on_invoice_issued(invoice, db)
    await db.commit()
    return (
        await db.execute(select(SdiItRecord).where(SdiItRecord.id == out["IT"]["record_id"]))
    ).scalar_one()


@pytest.mark.asyncio
async def test_settings_roundtrip(client: AsyncClient, auth_headers, test_clinic):
    res = await client.get(SETTINGS, headers=auth_headers)
    assert res.status_code == 200 and res.json()["data"]["enabled"] is False
    res = await client.put(
        SETTINGS,
        json={"regime_fiscale": "RF19", "bollo_virtuale": False, "enabled": True},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["enabled"] and body["regime_fiscale"] == "RF19" and body["bollo_virtuale"] is False
    res = await client.put(SETTINGS, json={"transport": "sdicoop"}, headers=auth_headers)
    assert res.status_code == 422  # only manual | pec


@pytest.mark.asyncio
async def test_manual_lifecycle_download_export_receipt(
    client: AsyncClient, auth_headers, test_clinic, test_patient, db_session
):
    rec = await _queued_record(db_session, test_clinic, test_patient)
    res = await client.get("/api/v1/sdi_it/records", headers=auth_headers)
    assert res.status_code == 200 and res.json()["total"] == 1
    assert res.json()["data"][0]["state"] == "pending"

    res = await client.get(f"/api/v1/sdi_it/records/{rec.id}/xml", headers=auth_headers)
    assert res.status_code == 200 and res.headers["content-disposition"].endswith(
        f'"{rec.file_name}"'
    )
    assert b"<FormatoTrasmissione>FPR12</FormatoTrasmissione>" in res.content

    res = await client.post(f"/api/v1/sdi_it/records/{rec.id}/exported", headers=auth_headers)
    assert res.status_code == 200 and res.json()["data"]["state"] == "exported"

    rc = (
        f'<ns3:RicevutaConsegna xmlns:ns3="{NS}"><IdentificativoSdI>555</IdentificativoSdI>'
        f"<NomeFile>{rec.file_name}</NomeFile><DataOraRicezione>2026-09-07T10:00:00</DataOraRicezione>"
        "</ns3:RicevutaConsegna>"
    )
    res = await client.post("/api/v1/sdi_it/receipts", json={"xml": rc}, headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["data"]["state"] == "delivered" and res.json()["data"]["receipt_type"] == "RC"
    res = await client.post("/api/v1/sdi_it/receipts", json={"xml": rc}, headers=auth_headers)
    assert res.status_code == 409  # already applied
    res = await client.post(f"/api/v1/sdi_it/records/{rec.id}/requeue", headers=auth_headers)
    assert res.status_code == 409  # only rejected records


@pytest.mark.asyncio
async def test_scarto_then_requeue_keeps_number_and_date(
    client: AsyncClient, auth_headers, test_clinic, test_patient, db_session
):
    rec = await _queued_record(db_session, test_clinic, test_patient)
    ns = (
        f'<ns3:NotificaScarto xmlns:ns3="{NS}"><IdentificativoSdI>556</IdentificativoSdI>'
        f"<NomeFile>{rec.file_name}</NomeFile><ListaErrori><Errore><Codice>00423</Codice>"
        "<Descrizione>Prezzo totale</Descrizione></Errore></ListaErrori></ns3:NotificaScarto>"
    )
    res = await client.post("/api/v1/sdi_it/receipts", json={"xml": ns}, headers=auth_headers)
    assert res.status_code == 200 and res.json()["data"]["state"] == "rejected"
    assert res.json()["data"]["errors"][0]["code"] == "00423"
    res = await client.post(f"/api/v1/sdi_it/records/{rec.id}/requeue", headers=auth_headers)
    assert res.status_code == 200, res.text
    new = res.json()["data"]
    assert new["id"] != str(rec.id) and new["state"] == "pending"
    assert new["invoice_number"] == "E/2026/0001" and new["issue_date"] == "2026-09-07"
    assert new["progressivo"] != rec.progressivo and new["file_name"] != rec.file_name
    res = await client.post(
        "/api/v1/sdi_it/receipts",
        json={"xml": ns.replace(rec.file_name, "IT01234567897_ZZZZZ.xml")},
        headers=auth_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_receipt_rejects_garbage(client: AsyncClient, auth_headers, test_clinic):
    res = await client.post(
        "/api/v1/sdi_it/receipts",
        json={"xml": "<Boh><NomeFile>x.xml</NomeFile></Boh>"},
        headers=auth_headers,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_pec_settings_enable_requires_credentials_and_test_endpoint(
    client: AsyncClient, auth_headers, test_clinic, monkeypatch
):
    res = await client.put(
        SETTINGS, json={"transport": "pec", "enabled": True}, headers=auth_headers
    )
    assert res.status_code == 400  # incomplete credentials
    creds = {
        "transport": "pec",
        "pec_address": "studio@pec.example.it",
        "smtp_host": "smtps.example.it",
        "imap_host": "imaps.example.it",
        "smtp_username": "studio@pec.example.it",
        "smtp_password": "secret",
    }
    res = await client.put(SETTINGS, json=creds, headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["has_smtp_password"] is True and "smtp_password" not in body
    assert body["sdi_pec_address"] == "sdi01@pec.fatturapa.it" and body["smtp_port"] == 465
    res = await client.put(SETTINGS, json={"enabled": True}, headers=auth_headers)
    assert res.status_code == 200 and res.json()["data"]["enabled"] is True
    res = await client.put(
        SETTINGS, json={"sdi_pec_address": "evil@example.com"}, headers=auth_headers
    )
    assert res.status_code == 422  # only *.pec.fatturapa.it

    import importlib

    sdi_router_mod = importlib.import_module("app.modules.sdi_it.router")

    async def fake_test(creds):
        return {"smtp": "ok", "imap": "ok"}

    monkeypatch.setattr(sdi_router_mod, "test_connection", fake_test)
    res = await client.post("/api/v1/sdi_it/pec/test", headers=auth_headers)
    assert res.status_code == 200 and res.json()["data"] == {"smtp": "ok", "imap": "ok"}


@pytest.mark.asyncio
async def test_process_now_runs_one_tick(
    client: AsyncClient, auth_headers, test_clinic, test_patient, db_session, monkeypatch
):
    await _queued_record(db_session, test_clinic, test_patient)
    settings = (await db_session.execute(select(SdiItSettings))).scalar_one()
    settings.transport = "pec"
    settings.pec_address = "studio@pec.example.it"
    settings.smtp_host = "smtps.example.it"
    settings.imap_host = "imaps.example.it"
    settings.smtp_username = "studio@pec.example.it"
    from app.core.email.encryption import encrypt_password

    settings.smtp_password_encrypted = encrypt_password("pw")
    await db_session.commit()
    from app.modules.sdi_it.services import pec_transport as pt

    async def fake_send(creds, to, name, xml):
        return "<m@pec>"

    async def fake_poll(creds, limit=50):
        return pt.PollResult()

    monkeypatch.setattr(pt, "send_file", fake_send)
    monkeypatch.setattr(pt, "poll_receipts", fake_poll)
    res = await client.post("/api/v1/sdi_it/queue/process-now", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["data"]["sent"] == 1
    res = await client.get("/api/v1/sdi_it/records", headers=auth_headers)
    row = res.json()["data"][0]
    assert (
        row["state"] == "exported" and row["transport"] == "pec" and row["message_id"] == "<m@pec>"
    )
