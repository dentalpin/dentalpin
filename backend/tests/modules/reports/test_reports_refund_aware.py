"""Receivables must be net of refunds, on every surface (#690).

`billing/CLAUDE.md`: "``compute_paid_summary`` is the only paid arithmetic.
Refunds are subtracted proportionally there; any other surface must reuse it
/ ``compute_paid_summaries_for_invoices`` instead of summing
``invoice_payments.amount`` raw."

A raw sum let a refunded payment keep reducing receivables, so the manager
dashboard reported nothing outstanding on an invoice the invoice page showed
as unpaid, and the overdue list carried it with ``balance_due`` 0 — nothing
to chase. These tests pin the four surfaces to one answer.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.core.utils.dates import clinic_today_for
from app.modules.billing.models import Invoice, InvoicePayment
from app.modules.billing.service import compute_paid_summary
from app.modules.patients.models import Patient
from app.modules.payments.models import Payment, Refund
from app.modules.reports.services.billing import BillingReportService


async def _staff_id(db: AsyncSession):
    user = User(
        email=f"refund-{uuid4().hex[:8]}@test.clinic",
        password_hash="not-a-real-hash",
        first_name="Refund",
        last_name="Staff",
    )
    db.add(user)
    await db.commit()
    return user.id


async def _invoice_paid_then_refunded(
    db: AsyncSession,
    clinic_id,
    patient_id,
    user_id,
    *,
    total: str,
    paid: str,
    refunded: str | None,
) -> Invoice:
    """An issued, overdue invoice with one imputed payment and an optional refund."""
    invoice = Invoice(
        clinic_id=clinic_id,
        patient_id=patient_id,
        created_by=user_id,
        issued_by=user_id,
        status="issued",
        total=Decimal(total),
        issue_date=date.today() - timedelta(days=40),
        due_date=date.today() - timedelta(days=10),
    )
    db.add(invoice)
    payment = Payment(
        clinic_id=clinic_id,
        patient_id=patient_id,
        amount=Decimal(paid),
        currency="EUR",
        method="cash",
        payment_date=date.today(),
        recorded_by=user_id,
    )
    db.add(payment)
    await db.flush()
    db.add(
        InvoicePayment(
            clinic_id=clinic_id,
            invoice_id=invoice.id,
            payment_id=payment.id,
            amount=Decimal(paid),
            created_by=user_id,
        )
    )
    if refunded is not None:
        db.add(
            Refund(
                clinic_id=clinic_id,
                payment_id=payment.id,
                amount=Decimal(refunded),
                method="cash",
                reason_code="patient_request",
                refunded_at=datetime.now(UTC),
                refunded_by=user_id,
            )
        )
    await db.commit()
    return invoice


async def _four_surfaces(db: AsyncSession, clinic_id, patient_id, invoice_id):
    # The summary cuts payments on the clinic's days, so its window ends on
    # the clinic's today, not the server's.
    today = await clinic_today_for(db, clinic_id)
    summary = await BillingReportService.get_summary(
        db, clinic_id, today - timedelta(days=365), today
    )
    patient_tab = await BillingReportService.get_patient_summary(db, clinic_id, patient_id)
    overdue = await BillingReportService.get_overdue_invoices(db, clinic_id)
    _, balance = await compute_paid_summary(db, clinic_id, invoice_id)
    row = next(o for o in overdue if o["id"] == invoice_id)
    return {
        "invoice_page": balance,
        "patient_tab": patient_tab["balance_pending"],
        "clinic_summary": summary["total_pending"],
        "overdue_row": row["balance_due"],
    }


@pytest.mark.asyncio
async def test_a_full_refund_restores_the_balance_everywhere(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    user_id = await _staff_id(db_session)
    invoice = await _invoice_paid_then_refunded(
        db_session,
        test_clinic.id,
        test_patient.id,
        user_id,
        total="100",
        paid="100",
        refunded="100",
    )
    surfaces = await _four_surfaces(db_session, test_clinic.id, test_patient.id, invoice.id)
    assert surfaces == {
        "invoice_page": Decimal("100.00"),
        "patient_tab": Decimal("100.00"),
        "clinic_summary": Decimal("100.00"),
        "overdue_row": Decimal("100.00"),
    }


@pytest.mark.asyncio
async def test_a_partial_refund_is_subtracted_proportionally(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    user_id = await _staff_id(db_session)
    invoice = await _invoice_paid_then_refunded(
        db_session,
        test_clinic.id,
        test_patient.id,
        user_id,
        total="100",
        paid="100",
        refunded="40",
    )
    surfaces = await _four_surfaces(db_session, test_clinic.id, test_patient.id, invoice.id)
    assert set(surfaces.values()) == {Decimal("40.00")}


@pytest.mark.asyncio
async def test_without_a_refund_nothing_is_outstanding(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """The baseline the refund cases are measured against."""
    user_id = await _staff_id(db_session)
    invoice = await _invoice_paid_then_refunded(
        db_session,
        test_clinic.id,
        test_patient.id,
        user_id,
        total="100",
        paid="100",
        refunded=None,
    )
    surfaces = await _four_surfaces(db_session, test_clinic.id, test_patient.id, invoice.id)
    assert set(surfaces.values()) == {Decimal("0.00")}


@pytest.mark.asyncio
async def test_total_paid_stays_gross_on_purpose(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """``total_paid`` is the fiscal "cobrado via factura" axis, not a balance.

    It is deliberately **not** netted against refunds (the patient-centric
    collected figure lives in the payments module). Pinned so a later reader
    does not "fix" it into a second, inconsistent balance.
    """
    # The window misses today's payment when it ends on a day the clinic
    # has already left behind, i.e. when the clinic is ahead of the server.
    # UTC+14 is a day ahead of a UTC server from 10:00 to 24:00 UTC, so a
    # server-day window fails here most of the day, not only in the hour
    # around Madrid's midnight.
    test_clinic.timezone = "Pacific/Kiritimati"
    user_id = await _staff_id(db_session)
    await _invoice_paid_then_refunded(
        db_session,
        test_clinic.id,
        test_patient.id,
        user_id,
        total="100",
        paid="100",
        refunded="100",
    )
    today = await clinic_today_for(db_session, test_clinic.id)
    summary = await BillingReportService.get_summary(
        db_session, test_clinic.id, today - timedelta(days=365), today
    )
    assert summary["total_paid"] == Decimal("100.00")
    assert summary["total_pending"] == Decimal("100.00")
