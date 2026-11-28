"""NavOnlineHook: gating and the queued record on issue / credit note."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from lxml import etree
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.core.email.encryption import encrypt_password
from app.modules.billing.models import Invoice, InvoiceItem
from app.modules.nav_online.hook import NavOnlineHook
from app.modules.nav_online.models import NavOnlineRecord, NavOnlineSettings
from app.modules.nav_online.services.xml_builder import NS_DATA
from app.modules.patients.models import Patient


async def _setup(
    db: AsyncSession, *, enabled=True, currency="HUF", tax_id="12345678-2-41", quantity=1
):
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
        subtotal=Decimal("15000") * quantity,
        total=Decimal("15000") * quantity,
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
            quantity=quantity,
            vat_rate=0.0,
            line_subtotal=Decimal("15000") * quantity,
            line_total=Decimal("15000") * quantity,
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


def _xp(xml: str, path: str) -> list[str]:
    return etree.fromstring(xml.encode()).xpath(path, namespaces={"d": NS_DATA})


async def _credit_note(db: AsyncSession, original: Invoice, number: str, quantity: int) -> Invoice:
    """A credit note as billing issues it: negative unit price and lines (#1046)."""
    src = original.items[0]
    net = -(src.unit_price * quantity)
    note = Invoice(
        id=uuid4(),
        clinic_id=original.clinic_id,
        patient_id=original.patient_id,
        invoice_number=number,
        credit_note_for_id=original.id,
        status="issued",
        issue_date=date(2026, 9, 7),
        billing_name=original.billing_name,
        subtotal=net,
        total=net,
        created_by=original.created_by,
        issued_by=original.created_by,
    )
    db.add(note)
    db.add(
        InvoiceItem(
            id=uuid4(),
            clinic_id=original.clinic_id,
            invoice_id=note.id,
            description=src.description,
            unit_price=-src.unit_price,
            quantity=quantity,
            vat_rate=0.0,
            line_subtotal=net,
            line_total=net,
        )
    )
    await db.flush()
    await db.refresh(note, ["items"])
    return note


async def _record(db: AsyncSession, invoice_id) -> NavOnlineRecord:
    return (
        await db.execute(select(NavOnlineRecord).where(NavOnlineRecord.invoice_id == invoice_id))
    ).scalar_one()


@pytest.mark.asyncio
async def test_credit_note_cancelling_the_whole_invoice_queues_storno(db_session, test_clinic):
    clinic, inv = await _setup(db_session, quantity=3)
    await NavOnlineHook().on_invoice_issued(inv, db_session)
    note = await _credit_note(db_session, inv, "HU-NC-2026-0001", quantity=3)
    data = await NavOnlineHook().on_credit_note_issued(note, inv, db_session)
    await db_session.commit()
    assert data["HU"]["operation"] == "STORNO"
    row = await _record(db_session, note.id)
    assert row.operation == "STORNO"
    assert _xp(row.xml_payload, "//d:originalInvoiceNumber/text()") == ["HU-2026-0007"]
    assert _xp(row.xml_payload, "//d:modificationIndex/text()") == ["1"]
    # The original has one line; the storno's line continues at 2 (#1069).
    assert _xp(
        row.xml_payload, "//d:line/d:lineModificationReference/d:lineNumberReference/text()"
    ) == ["2"]
    assert _xp(row.xml_payload, "//d:line/d:lineModificationReference/d:lineOperation/text()") == [
        "CREATE"
    ]
    assert row.gross_amount == Decimal("-45000.00")
    # #1046: negative quantity, positive unit price.
    assert _xp(row.xml_payload, "//d:quantity/text()") == ["-3"]
    assert _xp(row.xml_payload, "//d:unitPrice/text()") == ["15000.00"]


@pytest.mark.asyncio
async def test_partial_then_final_credit_note_chain(db_session, test_clinic):
    """First a partial note (MODIFY, index 1), then one crediting the rest
    (STORNO, index 2), line references continuing the chain (#1069)."""
    clinic, inv = await _setup(db_session, quantity=3)
    await NavOnlineHook().on_invoice_issued(inv, db_session)

    first = await _credit_note(db_session, inv, "HU-NC-2026-0001", quantity=1)
    data = await NavOnlineHook().on_credit_note_issued(first, inv, db_session)
    assert data["HU"]["operation"] == "MODIFY"
    row1 = await _record(db_session, first.id)
    assert row1.operation == "MODIFY"
    assert _xp(row1.xml_payload, "//d:modificationIndex/text()") == ["1"]
    assert _xp(row1.xml_payload, "//d:lineNumberReference/text()") == ["2"]

    second = await _credit_note(db_session, inv, "HU-NC-2026-0002", quantity=2)
    data = await NavOnlineHook().on_credit_note_issued(second, inv, db_session)
    await db_session.commit()
    assert data["HU"]["operation"] == "STORNO"
    row2 = await _record(db_session, second.id)
    assert row2.operation == "STORNO"
    assert _xp(row2.xml_payload, "//d:modificationIndex/text()") == ["2"]
    assert _xp(row2.xml_payload, "//d:lineNumberReference/text()") == ["3"]


@pytest.mark.asyncio
async def test_chain_ignores_other_clinics_records(db_session, test_clinic):
    """The index counts only this original's notes in this clinic."""
    _, other = await _setup(db_session, quantity=3)
    await NavOnlineHook().on_invoice_issued(other, db_session)
    other_note = await _credit_note(db_session, other, "HU-NC-OTHER-1", quantity=1)
    await NavOnlineHook().on_credit_note_issued(other_note, other, db_session)

    _, inv = await _setup(db_session, quantity=3)
    # No CREATE row (issued before NAV reporting): billing's items/total are used.
    note = await _credit_note(db_session, inv, "HU-NC-2026-0001", quantity=1)
    data = await NavOnlineHook().on_credit_note_issued(note, inv, db_session)
    await db_session.commit()
    assert data["HU"]["operation"] == "MODIFY"
    row = await _record(db_session, note.id)
    assert _xp(row.xml_payload, "//d:modificationIndex/text()") == ["1"]
    assert _xp(row.xml_payload, "//d:lineNumberReference/text()") == ["2"]
