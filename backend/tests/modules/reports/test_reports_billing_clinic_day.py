"""The billing report's "paid in period" cuts on the clinic's days.

``InvoicePayment.created_at`` is an instant; ``get_summary`` windowed it with
UTC midnights while ``total_invoiced`` uses the invoice's local
``issue_date``. In a Mexico City clinic (UTC-6) a payment imputed at 19:00
on the 14th (01:00 UTC on the 15th) was missing from the 14th's report and
counted on the 15th.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.billing.models import Invoice, InvoicePayment
from app.modules.patients.models import Patient
from app.modules.payments.models import Payment
from app.modules.reports.services.billing import BillingReportService

DAY = date(2026, 1, 14)


@pytest.mark.asyncio
async def test_total_paid_counts_an_evening_payment_on_its_local_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    test_clinic.timezone = "America/Mexico_City"
    user = User(
        email=f"u-{uuid4().hex[:8]}@test.clinic", password_hash="x", first_name="A", last_name="B"
    )
    db_session.add(user)
    await db_session.flush()
    invoice = Invoice(
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        created_by=user.id,
        issued_by=user.id,
        status="paid",
        total=Decimal("120.00"),
        issue_date=DAY,
    )
    payment = Payment(
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        amount=Decimal("120.00"),
        currency="MXN",
        method="cash",
        payment_date=DAY,
        recorded_by=user.id,
    )
    db_session.add_all([invoice, payment])
    await db_session.flush()
    db_session.add(
        InvoicePayment(
            clinic_id=test_clinic.id,
            invoice_id=invoice.id,
            payment_id=payment.id,
            amount=Decimal("120.00"),
            created_by=user.id,
            created_at=datetime(2026, 1, 15, 1, 0, tzinfo=UTC),
        )
    )
    await db_session.commit()

    day = await BillingReportService.get_summary(db_session, test_clinic.id, DAY, DAY)
    assert Decimal(str(day["total_paid"])) == Decimal("120.00")
    next_day = await BillingReportService.get_summary(
        db_session, test_clinic.id, date(2026, 1, 15), date(2026, 1, 15)
    )
    assert Decimal(str(next_day["total_paid"])) == Decimal("0")
