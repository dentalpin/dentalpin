"""NavOnlineHook: gating and the queued record on issue / credit note."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.core.email.encryption import encrypt_password
from app.modules.billing.models import Invoice, InvoiceItem
from app.modules.nav_online.hook import NavOnlineHook
from app.modules.nav_online.models import NavOnlineRecord, NavOnlineSettings
from app.modules.patients.models import Patient


async def _setup(db: AsyncSession, *, enabled=True, currency="HUF", tax_id="12345678-2-41"):
    clinic = Clinic(
        id=uuid4(),
        name="Mosoly",
        legal_name="Mosoly Dental Kft.",
        tax_id=tax_id,
        currency=currency,
        settings={"country": "HU"},
    )
    db.add(clinic)
    user = User(
        id=uuid4(), email=f"u-{uuid4()}@x.test", password_hash="x", first_name="A", last_name="B"
    )
    db.add(user)
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Anna", last_name="Kovács")
    db.add(patient)
    db.add(
        NavOnlineSettings(
            clinic_id=clinic.id,
            enabled=enabled,
            environment="test",
            tax_number="12345678",
            technical_user_login="techuser",
            technical_user_password_encrypted=encrypt_password("pw"),
            signature_key_encrypted=encrypt_password("sig-key"),
            exchange_key_encrypted=encrypt_password("0123456789abcdef"),
        )
    )
    invoice = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        invoice_number="HU-2026-0007",
        sequential_number=7,
        status="issued",
        issue_date=date(2026, 9, 6),
        billing_name="Kovács Anna",
        subtotal=Decimal("15000"),
        total=Decimal("15000"),
        created_by=user.id,
        issued_by=user.id,
    )
    db.add(invoice)
    db.add(
        InvoiceItem(
            id=uuid4(),
            clinic_id=clinic.id,
            invoice_id=invoice.id,
            description="Szűrővizsgálat",
            unit_price=Decimal("15000"),
            quantity=1,
            vat_rate=0.0,
            line_subtotal=Decimal("15000"),
            line_total=Decimal("15000"),
        )
    )
    await db.commit()
    inv = (await db.execute(select(Invoice).where(Invoice.id == invoice.id))).scalar_one()
    await db.refresh(inv, ["items"])
    return clinic, inv


@pytest.mark.asyncio
async def test_disabled_settings_is_a_noop(db_session, test_clinic):
    _, inv = await _setup(db_session, enabled=False)
    assert await NavOnlineHook().validate_before_issue(inv, db_session) == (True, None)
    assert await NavOnlineHook().on_invoice_issued(inv, db_session) == {}


@pytest.mark.asyncio
async def test_validate_blocks_non_huf_and_bad_tax_number(db_session, test_clinic):
    _, inv = await _setup(db_session, currency="EUR")
    ok, reason = await NavOnlineHook().validate_before_issue(inv, db_session)
    assert not ok and "HUF" in reason
    _, inv2 = await _setup(db_session, tax_id="not-a-number")
    ok, reason = await NavOnlineHook().validate_before_issue(inv2, db_session)
    assert not ok and "adószám" in reason


@pytest.mark.asyncio
async def test_issue_queues_create_record_with_xml(db_session, test_clinic):
    clinic, inv = await _setup(db_session)
    data = await NavOnlineHook().on_invoice_issued(inv, db_session)
    await db_session.commit()
    assert data["HU"]["operation"] == "CREATE" and data["HU"]["state"] == "pending"
    row = (
        await db_session.execute(
            select(NavOnlineRecord).where(NavOnlineRecord.invoice_id == inv.id)
        )
    ).scalar_one()
    assert row.state == "pending" and row.gross_amount == Decimal("15000.00")
    assert "<invoiceNumber>HU-2026-0007</invoiceNumber>" in row.xml_payload
    assert "<case>TAM</case>" in row.xml_payload


@pytest.mark.asyncio
async def test_credit_note_queues_storno(db_session, test_clinic):
    clinic, inv = await _setup(db_session)
    data = await NavOnlineHook().on_credit_note_issued(inv, inv, db_session)
    await db_session.commit()
    assert data["HU"]["operation"] == "STORNO"
    row = (
        await db_session.execute(
            select(NavOnlineRecord).where(NavOnlineRecord.invoice_id == inv.id)
        )
    ).scalar_one()
    assert (
        row.operation == "STORNO"
        and "<originalInvoiceNumber>HU-2026-0007</originalInvoiceNumber>" in row.xml_payload
    )
    assert row.gross_amount == Decimal("-15000.00")
