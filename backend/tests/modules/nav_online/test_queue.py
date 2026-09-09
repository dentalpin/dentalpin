"""Submission worker against a scripted NAV (post_xml monkeypatched)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.auth.models import Clinic, User
from app.core.email.encryption import encrypt_password
from app.modules.billing.models import Invoice
from app.modules.nav_online.models import NavOnlineRecord, NavOnlineSettings
from app.modules.nav_online.services import crypto, nav_client, submission_queue
from app.modules.patients.models import Patient

KEY = "0123456789abcdef"
_API = 'xmlns="http://schemas.nav.gov.hu/OSA/3.0/api" xmlns:common="http://schemas.nav.gov.hu/NTCA/1.0/common"'
_OK = "<common:result><common:funcCode>OK</common:funcCode></common:result>"


def _token_ok() -> str:
    return (
        f"<TokenExchangeResponse {_API}>{_OK}"
        f"<encodedExchangeToken>{crypto.encrypt_exchange_token('tok-1', KEY)}</encodedExchangeToken>"
        "</TokenExchangeResponse>"
    )


_MANAGE_OK = f"<ManageInvoiceResponse {_API}>{_OK}<transactionId>TX123456</transactionId></ManageInvoiceResponse>"


def _status(status, err=None):
    err_xml = (
        "<businessValidationMessages><validationResultCode>ERROR</validationResultCode>"
        f"<validationErrorCode>{err}</validationErrorCode><message>bad line</message></businessValidationMessages>"
        if err
        else ""
    )
    return (
        f"<QueryTransactionStatusResponse {_API}>{_OK}"
        f"<processingResults><processingResult><index>1</index><invoiceStatus>{status}</invoiceStatus>{err_xml}</processingResult></processingResults>"
        "</QueryTransactionStatusResponse>"
    )


async def _setup(db, *, state="pending"):
    clinic = Clinic(
        id=uuid4(),
        name="Mosoly",
        tax_id="12345678-2-41",
        currency="HUF",
        settings={"country": "HU"},
    )
    db.add(clinic)
    user = User(
        id=uuid4(), email=f"u-{uuid4()}@x.test", password_hash="x", first_name="A", last_name="B"
    )
    db.add(user)
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="A", last_name="K")
    db.add(patient)
    db.add(
        NavOnlineSettings(
            clinic_id=clinic.id,
            enabled=True,
            environment="test",
            tax_number="12345678",
            technical_user_login="tech",
            technical_user_password_encrypted=encrypt_password("pw"),
            signature_key_encrypted=encrypt_password("sig"),
            exchange_key_encrypted=encrypt_password(KEY),
        )
    )
    inv = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        invoice_number="HU-1",
        sequential_number=1,
        status="issued",
        issue_date=date.today(),
        created_by=user.id,
        total=Decimal("1"),
    )
    db.add(inv)
    await db.flush()  # no ORM relationship to Invoice → order the INSERTs by hand
    rec = NavOnlineRecord(
        clinic_id=clinic.id,
        invoice_id=inv.id,
        operation="CREATE",
        invoice_number="HU-1",
        issue_date=date.today(),
        gross_amount=Decimal("1"),
        xml_payload="<InvoiceData/>",
        state=state,
        created_at=datetime.now(UTC),
        transaction_id="TX123456" if state == "sent" else None,
    )
    db.add(rec)
    await db.commit()
    return clinic, rec


@pytest.mark.asyncio
async def test_pending_is_submitted_and_marked_sent(db_session, test_clinic, monkeypatch):
    clinic, rec = await _setup(db_session)
    calls = []

    async def fake_post(env, op, body):
        calls.append(op)
        return _token_ok() if op == "tokenExchange" else _MANAGE_OK

    monkeypatch.setattr(nav_client, "post_xml", fake_post)
    counters = await submission_queue.process_clinic(db_session, clinic.id)
    assert counters["sent"] == 1
    assert calls[:2] == ["tokenExchange", "manageInvoice"]
    await db_session.refresh(rec)
    assert rec.state == "sent" and rec.transaction_id == "TX123456"


@pytest.mark.asyncio
async def test_sent_is_polled_to_done_or_rejected(db_session, test_clinic, monkeypatch):
    clinic, rec = await _setup(db_session, state="sent")

    async def done(env, op, body):
        assert op == "queryTransactionStatus"
        return _status("DONE")

    monkeypatch.setattr(nav_client, "post_xml", done)
    assert (await submission_queue.process_clinic(db_session, clinic.id))["done"] == 1
    await db_session.refresh(rec)
    assert rec.state == "done" and rec.nav_status == "DONE"

    clinic2, rec2 = await _setup(db_session, state="sent")

    async def rejected(env, op, body):
        return _status("ABORTED", err="INVALID_LINE")

    monkeypatch.setattr(nav_client, "post_xml", rejected)
    assert (await submission_queue.process_clinic(db_session, clinic2.id))["rejected"] == 1
    await db_session.refresh(rec2)
    assert rec2.state == "rejected" and rec2.error_code == "INVALID_LINE"


@pytest.mark.asyncio
async def test_transport_error_backs_off_and_token_failure_pauses_clinic(
    db_session, test_clinic, monkeypatch
):
    clinic, rec = await _setup(db_session)

    async def token_boom(env, op, body):
        raise nav_client.NavClientError("connect timeout")

    monkeypatch.setattr(nav_client, "post_xml", token_boom)
    assert await submission_queue.process_clinic(db_session, clinic.id) == {
        "sent": 0,
        "done": 0,
        "rejected": 0,
        "failed": 0,
    }
    s = (
        await db_session.execute(
            select(NavOnlineSettings).where(NavOnlineSettings.clinic_id == clinic.id)
        )
    ).scalar_one()
    assert s.next_send_after is not None and "tokenExchange" in (s.last_error or "")

    s.next_send_after = None
    await db_session.commit()

    async def manage_boom(env, op, body):
        if op == "tokenExchange":
            return _token_ok()
        raise nav_client.NavClientError("502")

    monkeypatch.setattr(nav_client, "post_xml", manage_boom)
    assert (await submission_queue.process_clinic(db_session, clinic.id))["failed"] == 1
    await db_session.refresh(rec)
    assert rec.state == "failed" and rec.attempts == 1 and rec.next_attempt_at is not None
