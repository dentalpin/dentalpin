"""SdiItHook: the B2B gate, the queued record, the credit note, validation."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.billing.models import Invoice, InvoiceItem
from app.modules.patients.models import Patient
from app.modules.sdi_it.hook import NOT_APPLICABLE_REASON, SdiItHook
from app.modules.sdi_it.models import SdiItRecord, SdiItSettings

INSURER_PIVA = "00000000000"
PATIENT_CF = "RSSMRA80A01H501U"


async def _setup(
    db: AsyncSession,
    *,
    enabled=True,
    clinic_tax_id="01234567897",
    recipient_tax_id=INSURER_PIVA,
    number="E/2026/0001",
):
    clinic = Clinic(
        id=uuid4(),
        name="Studio Rossi",
        legal_name="Studio Dentistico Rossi S.r.l.",
        tax_id=clinic_tax_id,
        currency="EUR",
        address={
            "street": "Via Roma 1",
            "postal_code": "20121",
            "city": "Milano",
            "province": "MI",
        },
        settings={"country": "IT"},
    )
    db.add(clinic)
    user = User(
        id=uuid4(), email=f"u-{uuid4()}@x.test", password_hash="x", first_name="A", last_name="B"
    )
    db.add(user)
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Mario", last_name="Rossi")
    db.add(patient)
    db.add(SdiItSettings(clinic_id=clinic.id, enabled=enabled))
    invoice = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        invoice_number=number,
        sequential_number=1,
        status="issued",
        issue_date=date(2026, 9, 7),
        billing_name="Assicurazioni Alfa S.p.A."
        if recipient_tax_id == INSURER_PIVA
        else "Mario Rossi",
        billing_tax_id=recipient_tax_id,
        billing_address={"street": "Corso Italia 10", "postal_code": "00100", "city": "Roma"},
        subtotal=Decimal("150.00"),
        total=Decimal("150.00"),
        created_by=user.id,
        issued_by=user.id,
    )
    db.add(invoice)
    await db.flush()
    db.add(
        InvoiceItem(
            id=uuid4(),
            clinic_id=clinic.id,
            invoice_id=invoice.id,
            description="Visita specialistica",
            unit_price=Decimal("150.00"),
            quantity=1,
            vat_rate=0.0,
            line_subtotal=Decimal("150.00"),
            line_total=Decimal("150.00"),
        )
    )
    await db.flush()
    await db.refresh(invoice, attribute_names=["items"])
    return clinic, invoice


@pytest.mark.asyncio
async def test_b2b_invoice_is_queued_with_valid_file(db_session):
    clinic, invoice = await _setup(db_session)
    out = await SdiItHook().on_invoice_issued(invoice, db_session)
    assert out["IT"]["sdi"] == "queued" and out["IT"]["tipo_documento"] == "TD01"
    rec = (await db_session.execute(select(SdiItRecord))).scalar_one()
    assert rec.state == "pending" and rec.file_name == "IT01234567897_00001.xml"
    assert rec.codice_destinatario == "0000000" and rec.gross_amount == Decimal("150.00")
    assert (
        "<Natura>N4</Natura>" in rec.xml_payload
        and "<ImportoBollo>2.00</ImportoBollo>" in rec.xml_payload
    )
    settings = (await db_session.execute(select(SdiItSettings))).scalar_one()
    assert settings.progressivo_invio == 1


@pytest.mark.asyncio
async def test_patient_invoice_never_goes_to_the_sdi(db_session):
    clinic, invoice = await _setup(db_session, recipient_tax_id=PATIENT_CF)
    hook = SdiItHook()
    assert await hook.validate_before_issue(invoice, db_session) == (True, None)
    out = await hook.on_invoice_issued(invoice, db_session)
    assert out == {"IT": {"sdi": "not_applicable", "reason": NOT_APPLICABLE_REASON}}
    assert (await db_session.execute(select(SdiItRecord))).first() is None


@pytest.mark.asyncio
async def test_disabled_module_is_inert(db_session):
    clinic, invoice = await _setup(db_session, enabled=False)
    hook = SdiItHook()
    assert await hook.validate_before_issue(invoice, db_session) == (True, None)
    assert await hook.on_invoice_issued(invoice, db_session) == {}


@pytest.mark.asyncio
async def test_validation_requires_clinic_partita_iva_for_b2b(db_session):
    clinic, invoice = await _setup(db_session, clinic_tax_id="B12345678")
    ok, msg = await SdiItHook().validate_before_issue(invoice, db_session)
    assert not ok and "partita IVA" in msg
    out = await SdiItHook().on_invoice_issued(invoice, db_session)
    assert out["IT"]["sdi"] == "error"


@pytest.mark.asyncio
async def test_credit_note_is_td04_referencing_the_original(db_session):
    clinic, invoice = await _setup(db_session)
    note = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=invoice.patient_id,
        invoice_number="NC/2026/0001",
        sequential_number=1,
        status="issued",
        issue_date=date(2026, 9, 8),
        credit_note_for_id=invoice.id,
        billing_name=invoice.billing_name,
        billing_tax_id=invoice.billing_tax_id,
        billing_address=invoice.billing_address,
        subtotal=Decimal("150.00"),
        total=Decimal("150.00"),
        created_by=invoice.created_by,
        issued_by=invoice.issued_by,
    )
    db_session.add(note)
    await db_session.flush()
    db_session.add(
        InvoiceItem(
            id=uuid4(),
            clinic_id=clinic.id,
            invoice_id=note.id,
            description="Storno visita",
            unit_price=Decimal("150.00"),
            quantity=1,
            vat_rate=0.0,
            line_subtotal=Decimal("150.00"),
            line_total=Decimal("150.00"),
        )
    )
    await db_session.flush()
    await db_session.refresh(note, attribute_names=["items"])
    out = await SdiItHook().on_credit_note_issued(note, invoice, db_session)
    assert out["IT"]["tipo_documento"] == "TD04"
    rec = (
        await db_session.execute(select(SdiItRecord).where(SdiItRecord.invoice_id == note.id))
    ).scalar_one()
    assert "<IdDocumento>E/2026/0001</IdDocumento>" in rec.xml_payload


@pytest.mark.asyncio
async def test_recipient_edit_is_allowed_only_after_a_scarto_and_requeues(db_session):
    clinic, invoice = await _setup(db_session)
    hook = SdiItHook()
    await hook.on_invoice_issued(invoice, db_session)
    rec = (await db_session.execute(select(SdiItRecord))).scalar_one()
    assert (await hook.can_edit_billing_party(invoice, db_session))[0] is False
    assert await hook.regenerate_after_party_change(invoice, db_session) == {}

    rec.state = "rejected"
    await db_session.flush()
    assert await hook.can_edit_billing_party(invoice, db_session) == (True, None)
    invoice.billing_tax_id = "IT01234567897"  # corrected partita IVA
    out = await hook.regenerate_after_party_change(invoice, db_session)
    assert out["IT"]["sdi"] == "queued" and out["IT"]["file_name"] == "IT01234567897_00002.xml"
    records = (
        (await db_session.execute(select(SdiItRecord).order_by(SdiItRecord.created_at)))
        .scalars()
        .all()
    )
    assert [r.state for r in records] == ["rejected", "pending"]
    assert records[0].finished_at is not None
    assert "<IdCodice>01234567897</IdCodice>" in records[1].xml_payload


@pytest.mark.asyncio
async def test_progressivo_is_unique_across_builds(db_session):
    clinic, invoice = await _setup(db_session)
    hook = SdiItHook()
    first = await hook.on_invoice_issued(invoice, db_session)
    invoice.invoice_number = "E/2026/0002"
    second = await hook.on_invoice_issued(invoice, db_session)
    names = {first["IT"]["file_name"], second["IT"]["file_name"]}
    assert names == {"IT01234567897_00001.xml", "IT01234567897_00002.xml"}
    settings = (await db_session.execute(select(SdiItSettings))).scalar_one()
    assert settings.progressivo_invio == 2


@pytest.mark.asyncio
async def test_progressivo_lock_reads_the_committed_value_not_the_identity_map(db_session):
    """Two requests hold the settings row in their own sessions; the second
    must bump the value the first committed, not the copy it loaded earlier."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from sqlalchemy.orm import selectinload

    from app.modules.billing.models import Invoice
    from app.modules.sdi_it.hook import build_record

    clinic, invoice = await _setup(db_session)
    await db_session.commit()  # the other session must see the rows
    other = async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False)()
    try:
        mine = (await db_session.execute(select(SdiItSettings))).scalar_one()
        theirs = (await other.execute(select(SdiItSettings))).scalar_one()
        their_invoice = (
            await other.execute(
                select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice.id)
            )
        ).scalar_one()
        first = await build_record(other, their_invoice, theirs)
        await other.commit()
        second = await build_record(db_session, invoice, mine)
        await db_session.commit()
        assert {first.file_name, second.file_name} == {
            "IT01234567897_00001.xml",
            "IT01234567897_00002.xml",
        }
    finally:
        await other.close()
