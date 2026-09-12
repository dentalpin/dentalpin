"""Shared builders: an IT clinic with Sistema TS settings, a patient with a
codice fiscale, an invoice with lines and (optionally) a payment."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.core.email.encryption import encrypt_password
from app.modules.billing.models import Invoice, InvoiceItem, InvoicePayment
from app.modules.patients.models import Patient
from app.modules.payments.models import Payment
from app.modules.sistema_ts.models import SistemaTsSettings

CF = "RSSMRA80A01H501U"
PIVA = "01234567897"


async def make_clinic(db: AsyncSession, *, enabled=True, tax_id=PIVA):
    clinic = Clinic(
        id=uuid4(),
        name="Studio Rossi",
        legal_name="Studio Dentistico Rossi",
        tax_id=tax_id,
        currency="EUR",
        settings={"country": "IT"},
    )
    db.add(clinic)
    user = User(
        id=uuid4(), email=f"u-{uuid4()}@x.test", password_hash="x", first_name="A", last_name="B"
    )
    db.add(user)
    settings = SistemaTsSettings(
        clinic_id=clinic.id,
        enabled=enabled,
        environment="test",
        username="PROVAX00X00X000Y",
        password_encrypted=encrypt_password("Salve123"),
        pincode_encrypted=encrypt_password("1234567890"),
        cf_proprietario="RSSMRA80A01H501U",
        dispositivo="1",
        default_tipo_spesa="SR",
    )
    db.add(settings)
    await db.flush()
    return clinic, user, settings


async def make_patient(db: AsyncSession, clinic, *, cf=CF):
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Mario",
        last_name="Rossi",
        national_id=cf,
        national_id_type="other",
    )
    db.add(patient)
    await db.flush()
    return patient


async def make_invoice(
    db: AsyncSession,
    clinic,
    user,
    patient,
    *,
    number="FAC/2026/0001",
    status="paid",
    tax_id=None,
    issue=date(2026, 3, 2),
    pay=date(2026, 3, 5),
    method="card",
    lines=(("Visita", "60.00", 0.0), ("Sbiancamento", "40.00", 22.0)),
    credit_note_for=None,
):
    total = sum(Decimal(p) for _, p, _ in lines)
    inv = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        invoice_number=number,
        sequential_number=1,
        status=status,
        issue_date=issue,
        billing_name="Mario Rossi",
        billing_tax_id=tax_id or CF,
        subtotal=total,
        total=total,
        created_by=user.id,
        issued_by=user.id,
        credit_note_for_id=credit_note_for,
    )
    db.add(inv)
    await db.flush()
    for i, (desc, price, rate) in enumerate(lines):
        db.add(
            InvoiceItem(
                id=uuid4(),
                clinic_id=clinic.id,
                invoice_id=inv.id,
                description=desc,
                unit_price=Decimal(price),
                quantity=1,
                vat_rate=rate,
                line_subtotal=Decimal(price),
                line_total=Decimal(price),
                display_order=i,
            )
        )
    if pay and status == "paid":
        payment = Payment(
            id=uuid4(),
            clinic_id=clinic.id,
            patient_id=patient.id,
            amount=total,
            currency="EUR",
            method=method,
            payment_date=pay,
            recorded_by=user.id,
        )
        db.add(payment)
        await db.flush()
        db.add(
            InvoicePayment(
                id=uuid4(),
                clinic_id=clinic.id,
                invoice_id=inv.id,
                payment_id=payment.id,
                amount=total,
                created_by=user.id,
            )
        )
    await db.flush()
    return inv


def now():
    return datetime.now(UTC)
