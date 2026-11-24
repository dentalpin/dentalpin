"""Draft invoice PDF billing block (#1103, pure HTML — no DB).

Drafts store no billing snapshot; issuing freezes it from the patient.
The draft PDF printed the empty columns as is ("None" for the name, a
blank address). It now renders what issuing will snapshot, while an
issued document keeps printing its frozen snapshot.
"""

from __future__ import annotations

import re
from decimal import Decimal
from uuid import uuid4

from app.core.auth.models import Clinic
from app.modules.billing.models import Invoice
from app.modules.billing.pdf import InvoicePDFService
from app.modules.patients.models import Patient

ADDRESS = {"street": "Calle Mayor 1", "postal_code": "28013", "city": "Madrid"}


def _clinic() -> Clinic:
    return Clinic(
        id=uuid4(),
        name="Test Clinic",
        tax_id="B1",
        address={},
        settings={},
        currency="EUR",
        timezone="Europe/Madrid",
    )


def _patient(**billing) -> Patient:
    return Patient(
        id=uuid4(),
        first_name="Ana",
        last_name="García",
        national_id="12345678Z",
        national_id_type="dni",
        **billing,
    )


def _invoice(patient: Patient, status: str = "draft", **snapshot) -> Invoice:
    invoice = Invoice(
        id=uuid4(),
        clinic_id=uuid4(),
        patient_id=patient.id,
        status=status,
        subtotal=Decimal("60.00"),
        total_discount=Decimal("0.00"),
        total_tax=Decimal("0.00"),
        total=Decimal("60.00"),
        **snapshot,
    )
    invoice.patient = patient
    return invoice


def _billing_block(invoice: Invoice) -> str:
    html = InvoicePDFService._generate_html(invoice, _clinic(), is_preview=True, locale="en")
    return html.split('<div class="billing-info">', 1)[1].split('<div class="section">', 1)[0]


def _values(block: str) -> list[str]:
    return [v.strip() for v in re.findall(r'<div class="info-value">(.*?)</div>', block, re.S)]


def test_draft_prints_the_patient_billing_data_issue_will_snapshot() -> None:
    patient = _patient(billing_name="Acme SL", billing_tax_id="B99", billing_address=ADDRESS)
    block = _billing_block(_invoice(patient))

    values = _values(block)
    assert "None" not in values
    assert values[0] == "Acme SL"
    assert "B99" in values
    assert "Calle Mayor 1, 28013 Madrid" in values
    # The patient differs from the billing name, so the patient row stays.
    assert "Ana García" in values


def test_draft_without_billing_name_falls_back_to_patient_name() -> None:
    block = _billing_block(_invoice(_patient()))

    values = _values(block)
    assert values[0] == "Ana García"
    assert "12345678Z" in values  # DNI doubles as tax id, as at issue
    # Billing name equals the patient name: no duplicate "Patient" row.
    assert values.count("Ana García") == 1
    assert "None" not in block


def test_issued_invoice_keeps_its_frozen_snapshot() -> None:
    patient = _patient(billing_name="New Name SL", billing_tax_id="B2", billing_address=ADDRESS)
    invoice = _invoice(
        patient,
        status="issued",
        invoice_number="FAC-2026-0001",
        billing_name="Old Name SL",
        billing_tax_id="B1",
        billing_address={"street": "Old Street 9", "city": "Sevilla"},
    )
    values = _values(_billing_block(invoice))

    assert values[0] == "Old Name SL"
    assert "B1" in values
    assert "Old Street 9, Sevilla" in values
    assert "New Name SL" not in values
    assert "B2" not in values
