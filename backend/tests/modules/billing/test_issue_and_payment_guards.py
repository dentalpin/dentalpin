"""Money-path guards on the invoice issue + payment endpoints (audit
S3/C2 + C4, #97).

These assert the *sequential* rejection behaviour that the row locks in
`issue_invoice` / `record_payment_for_invoice` protect under concurrency:
a draft can't be issued twice, and an invoice can't be over-collected.
(True concurrent races aren't reproducible in the single-session test
harness; the locks serialize them so the checks below hold.)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.billing.models import Invoice, InvoiceItem, InvoiceSeries
from app.modules.patients.models import Patient


async def _draft_invoice(db: AsyncSession, clinic: Clinic, patient: Patient, user_id) -> Invoice:
    db.add(
        InvoiceSeries(
            id=uuid4(),
            clinic_id=clinic.id,
            prefix="FAC",
            series_type="invoice",
            is_default=True,
        )
    )
    inv = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        status="draft",
        # Pre-set billing data so issue() skips the patient snapshot.
        billing_name="Cliente Test",
        billing_tax_id="B12345678",
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
        created_by=user_id,
    )
    db.add(inv)
    await db.flush()
    db.add(
        InvoiceItem(
            id=uuid4(),
            clinic_id=clinic.id,
            invoice_id=inv.id,
            description="Servicio",
            unit_price=Decimal("100.00"),
            quantity=1,
            vat_rate=0.0,
            line_subtotal=Decimal("100.00"),
            line_tax=Decimal("0.00"),
            line_total=Decimal("100.00"),
            display_order=0,
        )
    )
    await db.commit()
    return inv


async def _user_id(db: AsyncSession):
    return (await db.execute(select(User))).scalars().first().id


@pytest.mark.asyncio
async def test_draft_cannot_be_issued_twice(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    inv = await _draft_invoice(db_session, test_clinic, test_patient, await _user_id(db_session))

    first = await client.post(
        f"/api/v1/billing/invoices/{inv.id}/issue", json={}, headers=auth_headers
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["status"] == "issued"

    second = await client.post(
        f"/api/v1/billing/invoices/{inv.id}/issue", json={}, headers=auth_headers
    )
    assert second.status_code == 400, second.text


@pytest.mark.asyncio
async def test_invoice_cannot_be_overpaid(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    inv = await _draft_invoice(db_session, test_clinic, test_patient, await _user_id(db_session))
    issued = await client.post(
        f"/api/v1/billing/invoices/{inv.id}/issue", json={}, headers=auth_headers
    )
    assert issued.status_code == 200, issued.text

    pay = {"amount": "100.00", "method": "cash", "payment_date": date.today().isoformat()}
    r1 = await client.post(
        f"/api/v1/billing/invoices/{inv.id}/payments", json=pay, headers=auth_headers
    )
    assert r1.status_code == 201, r1.text

    # Balance is now 0 — any further payment must be rejected.
    r2 = await client.post(
        f"/api/v1/billing/invoices/{inv.id}/payments",
        json={"amount": "1.00", "method": "cash", "payment_date": date.today().isoformat()},
        headers=auth_headers,
    )
    assert r2.status_code == 400, r2.text


@pytest.mark.asyncio
async def test_invoice_payment_is_cents_only(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    """Invoice + collect has its own schema, with the same rule (#989)."""
    inv = await _draft_invoice(db_session, test_clinic, test_patient, await _user_id(db_session))
    issued = await client.post(
        f"/api/v1/billing/invoices/{inv.id}/issue", json={}, headers=auth_headers
    )
    assert issued.status_code == 200, issued.text

    res = await client.post(
        f"/api/v1/billing/invoices/{inv.id}/payments",
        json={"amount": "10.005", "method": "cash", "payment_date": date.today().isoformat()},
        headers=auth_headers,
    )
    assert res.status_code == 422, res.text
