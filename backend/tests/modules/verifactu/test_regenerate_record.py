"""regenerate_record + validate_before_issue (rejected block).

Direct DB integration: builds the minimal Clinic + Invoice + Settings
state needed to exercise the regenerate path without going through the
real /issue endpoint or the AEAT submission queue.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.modules.billing.models import Invoice, InvoiceItem
from app.modules.patients.models import Patient
from app.modules.verifactu.hook import (
    VerifactuHook,
    regenerate_record,
)
from app.modules.verifactu.models import (
    VerifactuRecord,
    VerifactuRecordAttempt,
    VerifactuSettings,
)


async def _seed_clinic(db: AsyncSession, *, tax_id: str = "B12345678") -> Clinic:
    clinic = Clinic(
        id=uuid4(),
        name="Clinic Demo",
        legal_name="Clínica Demo S.L.",
        tax_id=tax_id,
        address={"street": "x", "city": "Madrid"},
        settings={"country": "ES"},
    )
    db.add(clinic)
    await db.flush()
    return clinic


async def _seed_user(db: AsyncSession, clinic: Clinic) -> User:
    user = User(
        id=uuid4(),
        email=f"u-{uuid4()}@x.test",
        password_hash="x",
        first_name="A",
        last_name="B",
        is_active=True,
    )
    db.add(user)
    db.add(ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic.id, role="admin"))
    await db.flush()
    return user


async def _seed_patient(db: AsyncSession, clinic: Clinic) -> Patient:
    p = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="P",
        last_name="X",
    )
    db.add(p)
    await db.flush()
    return p


async def _seed_settings(db: AsyncSession, clinic: Clinic) -> VerifactuSettings:
    s = VerifactuSettings(
        id=uuid4(),
        clinic_id=clinic.id,
        enabled=True,
        environment="test",
        numero_instalacion=str(uuid4()),
        producer_nif="B98765431",
        producer_name="DentalPin Producer",
        producer_id_sistema="DP",
        producer_version="0.1.0",
        declaracion_responsable_signed_at=datetime.now(UTC),
        declaracion_responsable_signed_by=uuid4(),
    )
    db.add(s)
    await db.flush()
    return s


async def _seed_invoice(
    db: AsyncSession,
    clinic: Clinic,
    user: User,
    patient: Patient,
    *,
    total: Decimal = Decimal("100.00"),
    billing_tax_id: str | None = None,
    invoice_number: str = "FAC-2026-0001",
) -> Invoice:
    inv = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        invoice_number=invoice_number,
        sequential_number=1,
        status="issued",
        issue_date=date.today(),
        billing_name="Cliente Test",
        billing_tax_id=billing_tax_id,
        subtotal=total,
        total_tax=Decimal("0.00"),
        total=total,
        created_by=user.id,
        issued_by=user.id,
    )
    db.add(inv)
    await db.flush()
    item = InvoiceItem(
        id=uuid4(),
        clinic_id=clinic.id,
        invoice_id=inv.id,
        description="Servicio dental",
        unit_price=total,
        quantity=1,
        vat_rate=0.0,
        line_subtotal=total,
        line_tax=Decimal("0.00"),
        line_total=total,
        display_order=0,
    )
    db.add(item)
    await db.flush()
    await db.refresh(inv, attribute_names=["items"])
    return inv


async def _issue_record(db: AsyncSession, hook: VerifactuHook, invoice: Invoice) -> VerifactuRecord:
    payload = await hook.on_invoice_issued(invoice, db)
    assert payload, "hook returned empty payload — settings not enabled?"
    record_id = payload["ES"]["record_id"]
    rec_q = await db.get(VerifactuRecord, record_id)
    assert rec_q is not None
    return rec_q


@pytest.mark.asyncio
async def test_regenerate_after_clinic_nif_fix(db_session: AsyncSession) -> None:
    clinic = await _seed_clinic(db_session, tax_id="B98765431")
    user = await _seed_user(db_session, clinic)
    patient = await _seed_patient(db_session, clinic)
    await _seed_settings(db_session, clinic)
    invoice = await _seed_invoice(db_session, clinic, user, patient)

    hook = VerifactuHook()
    record = await _issue_record(db_session, hook, invoice)
    original_huella = record.huella
    original_xml = record.xml_payload

    # Simulate AEAT rejection.
    record.state = "rejected"
    record.aeat_estado_registro = "Incorrecto"
    record.aeat_codigo_error = 4116
    record.aeat_descripcion_error = "NIF emisor formato incorrecto"
    record.aeat_response_xml = "<faultstring>...</faultstring>"
    await db_session.flush()

    # Admin fixes clinic NIF.
    clinic.tax_id = "A28000000"
    await db_session.flush()

    regenerated = await regenerate_record(db_session, record)

    assert regenerated.state == "pending"
    assert regenerated.subsanacion is True
    assert regenerated.rechazo_previo is True
    assert regenerated.huella != original_huella
    assert regenerated.xml_payload != original_xml
    assert "A28000000" in regenerated.xml_payload
    # AEAT response fields cleared so the queue UI shows fresh state.
    assert regenerated.aeat_codigo_error is None
    assert regenerated.aeat_descripcion_error is None

    # Audit row written (RD 1007/2023 art. 8 trazabilidad).
    attempt_q = await db_session.execute(
        VerifactuRecordAttempt.__table__.select().where(
            VerifactuRecordAttempt.record_id == record.id
        )
    )
    rows = list(attempt_q.fetchall())
    assert len(rows) == 1
    assert rows[0].huella == original_huella
    assert rows[0].xml_payload == original_xml

    # Invoice marked as pdf_stale + compliance_data refreshed.
    await db_session.refresh(invoice)
    assert invoice.pdf_stale is True
    assert invoice.compliance_data["ES"]["state"] == "pending"
    assert invoice.compliance_data["ES"]["huella"] == regenerated.huella


@pytest.mark.asyncio
async def test_regenerate_rejects_when_record_is_accepted(
    db_session: AsyncSession,
) -> None:
    clinic = await _seed_clinic(db_session, tax_id="A28000000")
    user = await _seed_user(db_session, clinic)
    patient = await _seed_patient(db_session, clinic)
    await _seed_settings(db_session, clinic)
    invoice = await _seed_invoice(db_session, clinic, user, patient)
    hook = VerifactuHook()
    record = await _issue_record(db_session, hook, invoice)
    record.state = "accepted"
    await db_session.flush()

    with pytest.raises(ValueError):
        await regenerate_record(db_session, record)


@pytest.mark.asyncio
async def test_validate_before_issue_blocks_when_rejected_pending(
    db_session: AsyncSession,
) -> None:
    clinic = await _seed_clinic(db_session, tax_id="A28000000")
    user = await _seed_user(db_session, clinic)
    patient = await _seed_patient(db_session, clinic)
    await _seed_settings(db_session, clinic)
    invoice_one = await _seed_invoice(
        db_session, clinic, user, patient, invoice_number="FAC-2026-0001"
    )
    hook = VerifactuHook()
    record = await _issue_record(db_session, hook, invoice_one)
    record.state = "rejected"
    record.aeat_estado_registro = "Incorrecto"
    await db_session.flush()

    invoice_two = await _seed_invoice(
        db_session, clinic, user, patient, invoice_number="FAC-2026-0002"
    )

    ok, err = await hook.validate_before_issue(invoice_two, db_session)
    assert ok is False
    assert err and "rechazados" in err.lower()


@pytest.mark.asyncio
async def test_validate_before_issue_passes_when_only_failed_transient(
    db_session: AsyncSession,
) -> None:
    clinic = await _seed_clinic(db_session, tax_id="A28000000")
    user = await _seed_user(db_session, clinic)
    patient = await _seed_patient(db_session, clinic)
    await _seed_settings(db_session, clinic)
    invoice_one = await _seed_invoice(
        db_session, clinic, user, patient, invoice_number="FAC-2026-0001"
    )
    hook = VerifactuHook()
    record = await _issue_record(db_session, hook, invoice_one)
    record.state = "failed_transient"  # network problem, not AEAT rejection
    await db_session.flush()

    invoice_two = await _seed_invoice(
        db_session, clinic, user, patient, invoice_number="FAC-2026-0002"
    )
    ok, err = await hook.validate_before_issue(invoice_two, db_session)
    assert ok is True
    assert err is None


@pytest.mark.asyncio
async def test_simplified_credit_note_is_r5_and_keeps_its_reference(
    db_session: AsyncSession,
) -> None:
    """No NIF: R5, and regenerating still names the rectified invoice (#1049)."""
    clinic = await _seed_clinic(db_session, tax_id="A28000000")
    user = await _seed_user(db_session, clinic)
    patient = await _seed_patient(db_session, clinic)
    await _seed_settings(db_session, clinic)
    original = await _seed_invoice(db_session, clinic, user, patient)
    note = await _seed_invoice(
        db_session, clinic, user, patient, total=Decimal("-100.00"), invoice_number="RECT-0001"
    )
    note.credit_note_for_id = original.id
    note.sequential_number = 2
    await db_session.flush()

    payload = await VerifactuHook().on_credit_note_issued(note, original, db_session)
    record = await db_session.get(VerifactuRecord, payload["ES"]["record_id"])
    assert record.tipo_factura == "R5"
    assert "<TipoFactura>R5</TipoFactura>" in record.xml_payload
    assert "FAC-2026-0001" in record.xml_payload

    record.state = "rejected"
    record.aeat_codigo_error = 1189
    await db_session.flush()
    regenerated = await regenerate_record(db_session, record)
    assert "<TipoFactura>R5</TipoFactura>" in regenerated.xml_payload
    assert "<FacturasRectificadas>" in regenerated.xml_payload
    assert "FAC-2026-0001" in regenerated.xml_payload
