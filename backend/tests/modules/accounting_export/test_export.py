"""Tests for the accounting_export module.

Covers row building, the off-books invoice-centric boundary, clinic
isolation, and the HTTP endpoints (preview + ZIP download + RBAC).
"""

from __future__ import annotations

import io
import zipfile
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.permissions import has_permission
from app.core.auth.service import create_access_token, hash_password
from app.modules.accounting_export.service import AccountingExportService
from app.modules.billing.models import Invoice, InvoiceItem, InvoicePayment
from app.modules.billing.service import InvoiceService
from app.modules.patients.models import Patient
from app.modules.payments.models import Payment


async def _invoice(
    db: AsyncSession,
    clinic_id,
    patient_id,
    user_id,
    *,
    number: str,
    status: str = "issued",
    rates: list[float] = (21.0,),
) -> Invoice:
    inv = Invoice(
        id=uuid4(),
        clinic_id=clinic_id,
        patient_id=patient_id,
        invoice_number=number,
        sequential_number=sum(ord(c) for c in number),
        status=status,
        issue_date=date(2026, 5, 15),
        billing_name="Acme SL",
        billing_tax_id="B12345678",
        subtotal=Decimal("100.00"),
        total_discount=Decimal("0.00"),
        total_tax=Decimal("21.00"),
        total=Decimal("121.00"),
        created_by=user_id,
        issued_by=user_id,
    )
    db.add(inv)
    await db.flush()
    for i, r in enumerate(rates):
        db.add(
            InvoiceItem(
                id=uuid4(),
                clinic_id=clinic_id,
                invoice_id=inv.id,
                description=f"Item {i}",
                unit_price=Decimal("100.00"),
                quantity=1,
                vat_rate=r,
                display_order=i,
            )
        )
    await db.flush()
    return inv


async def _pay_invoice(db, clinic_id, patient_id, user_id, invoice_id, amount) -> Payment:
    pay = Payment(
        id=uuid4(),
        clinic_id=clinic_id,
        patient_id=patient_id,
        amount=amount,
        currency="EUR",
        method="card",
        payment_date=date(2026, 5, 16),
        reference="REF-1",
        recorded_by=user_id,
    )
    db.add(pay)
    await db.flush()
    db.add(
        InvoicePayment(
            id=uuid4(),
            clinic_id=clinic_id,
            invoice_id=invoice_id,
            payment_id=pay.id,
            amount=amount,
            created_by=user_id,
        )
    )
    await db.flush()
    return pay


async def _me(client: AsyncClient, headers: dict) -> str:
    res = await client.get("/api/v1/auth/me", headers=headers)
    return res.json()["data"]["user"]["id"]


# --- service / row building --------------------------------------------------


@pytest.mark.asyncio
async def test_rows_and_offbooks_boundary(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
):
    user_id = await _me(client, auth_headers)

    paid = await _invoice(db_session, test_clinic.id, test_patient.id, user_id, number="FAC-1")
    await _pay_invoice(
        db_session, test_clinic.id, test_patient.id, user_id, paid.id, Decimal("121.00")
    )
    await _invoice(db_session, test_clinic.id, test_patient.id, user_id, number="FAC-2")
    # A draft must never be exported.
    await _invoice(
        db_session, test_clinic.id, test_patient.id, user_id, number="FAC-3", status="draft"
    )
    # A payment NOT linked to any invoice — off-books cash. Must not leak.
    db_session.add(
        Payment(
            id=uuid4(),
            clinic_id=test_clinic.id,
            patient_id=test_patient.id,
            amount=Decimal("50.00"),
            currency="EUR",
            method="cash",
            payment_date=date(2026, 5, 20),
            recorded_by=user_id,
        )
    )
    await db_session.commit()

    invoices = await AccountingExportService.fetch(
        db_session, test_clinic.id, date(2026, 5, 1), date(2026, 5, 31), None
    )
    inv_rows = AccountingExportService.invoice_rows(invoices)
    pay_rows = AccountingExportService.payment_rows(invoices)

    numbers = {r["numero"] for r in inv_rows}
    assert numbers == {"FAC-1", "FAC-2"}  # draft excluded
    assert all(r["base"] == Decimal("100.00") for r in inv_rows)
    assert all(r["cuota_iva"] == Decimal("21.00") for r in inv_rows)
    # Only the invoice-linked payment is exported; the cash payment is not.
    assert len(pay_rows) == 1
    assert pay_rows[0]["factura"] == "FAC-1"
    assert pay_rows[0]["importe"] == Decimal("121.00")


@pytest.mark.asyncio
async def test_refunds_are_exported_as_negative_collections(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
):
    """A refunded collection is not money collected (#988).

    Billing never edits ``InvoicePayment`` on a refund (it nets refunds at
    read time), so ``cobros.csv`` kept listing a fully refunded payment as
    collected while ``facturas.csv`` showed the invoice unpaid again. Each
    refund is now a negative row on its own (clinic) date, for the
    invoice's share of the payment.
    """
    from datetime import UTC, datetime

    from app.modules.payments.models import Refund

    user_id = await _me(client, auth_headers)
    full = await _invoice(db_session, test_clinic.id, test_patient.id, user_id, number="FAC-R1")
    pay_full = await _pay_invoice(
        db_session, test_clinic.id, test_patient.id, user_id, full.id, Decimal("121.00")
    )
    part = await _invoice(db_session, test_clinic.id, test_patient.id, user_id, number="FAC-R2")
    pay_part = await _pay_invoice(
        db_session, test_clinic.id, test_patient.id, user_id, part.id, Decimal("121.00")
    )
    for pay, amount, at in (
        (pay_full, Decimal("121.00"), datetime(2026, 5, 20, 10, 0, tzinfo=UTC)),
        (pay_part, Decimal("21.00"), datetime(2026, 5, 21, 10, 0, tzinfo=UTC)),
    ):
        db_session.add(
            Refund(
                id=uuid4(),
                clinic_id=test_clinic.id,
                payment_id=pay.id,
                amount=amount,
                method="card",
                reason_code="other",
                refunded_at=at,
                refunded_by=user_id,
            )
        )
    await db_session.commit()

    invoices = await AccountingExportService.fetch(db_session, test_clinic.id, None, None, None)
    rows = AccountingExportService.payment_rows(invoices)
    by_invoice: dict[str, list] = {}
    for row in rows:
        by_invoice.setdefault(row["factura"], []).append((row["fecha_pago"], row["importe"]))

    assert by_invoice["FAC-R1"] == [
        ("2026-05-16", Decimal("121.00")),
        ("2026-05-20", Decimal("-121.00")),
    ]
    assert by_invoice["FAC-R2"] == [
        ("2026-05-16", Decimal("121.00")),
        ("2026-05-21", Decimal("-21.00")),
    ]
    assert sum(amount for _, amount in by_invoice["FAC-R1"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_mixed_vat_rate_is_varios(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
):
    user_id = await _me(client, auth_headers)
    await _invoice(
        db_session, test_clinic.id, test_patient.id, user_id, number="FAC-9", rates=[21.0, 10.0]
    )
    await db_session.commit()

    invoices = await AccountingExportService.fetch(db_session, test_clinic.id, None, None, None)
    rows = AccountingExportService.invoice_rows(invoices)
    assert rows[0]["tipo_iva"] == "varios"


@pytest.mark.asyncio
async def test_clinic_isolation(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
):
    user_id = await _me(client, auth_headers)
    await _invoice(db_session, test_clinic.id, test_patient.id, user_id, number="FAC-A")

    other = Clinic(id=uuid4(), name="Other", tax_id="B99999999")
    db_session.add(other)
    await db_session.flush()
    other_patient = Patient(id=uuid4(), clinic_id=other.id, first_name="O", last_name="P")
    db_session.add(other_patient)
    await db_session.flush()
    await _invoice(db_session, other.id, other_patient.id, user_id, number="FAC-B")
    await db_session.commit()

    invoices = await InvoiceService.list_for_export(db_session, test_clinic.id)
    assert {i.invoice_number for i in invoices} == {"FAC-A"}


# --- HTTP endpoints ----------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_and_download(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
):
    user_id = await _me(client, auth_headers)
    inv = await _invoice(db_session, test_clinic.id, test_patient.id, user_id, number="FAC-1")
    await _pay_invoice(
        db_session, test_clinic.id, test_patient.id, user_id, inv.id, Decimal("121.00")
    )
    await db_session.commit()

    res = await client.get(
        "/api/v1/accounting_export/preview?date_from=2026-05-01&date_to=2026-05-31",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["invoice_count"] == 1
    assert data["payment_count"] == 1

    res = await client.get(
        "/api/v1/accounting_export/run?date_from=2026-05-01&date_to=2026-05-31&separator=;",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        assert set(zf.namelist()) == {"facturas.csv", "cobros.csv"}
        facturas = zf.read("facturas.csv").decode("utf-8")
        assert facturas.startswith("﻿")  # BOM
        assert "FAC-1" in facturas
        assert "121,00" in facturas  # comma decimals for separator ";"


@pytest.mark.asyncio
async def test_requires_permission(
    db_session: AsyncSession,
    client: AsyncClient,
    test_clinic: Clinic,
):
    # Receptionist has no accounting_export permissions.
    user = User(
        id=uuid4(),
        email="recep@example.com",
        password_hash=hash_password("ReceptionPass1234"),
        first_name="Re",
        last_name="Cept",
        is_active=True,
        token_version=0,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=test_clinic.id, role="receptionist")
    )
    await db_session.commit()
    token = create_access_token(user.id, token_version=user.token_version)

    res = await client.get(
        "/api/v1/accounting_export/preview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


@pytest.mark.parametrize(
    "role,expected",
    [
        ("admin", True),
        ("dentist", False),
        ("receptionist", False),
    ],
)
def test_rbac_admin_only(role: str, expected: bool):
    assert has_permission(role, "accounting_export.export.read") is expected
    assert has_permission(role, "accounting_export.export.run") is expected
