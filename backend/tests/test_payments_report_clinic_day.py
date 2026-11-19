"""Payments reports cut refunds and earned revenue on the clinic's days.

``Payment.payment_date`` is the clinic's calendar day, but ``Refund.refunded_at``
and ``PatientEarnedEntry.performed_at`` are UTC instants, and the reports
windowed them with UTC midnights. In a Mexico City clinic (UTC-6) a refund
issued at 20:00 on the 14th is 02:00 UTC on the 15th: it was missing from
the 14th's report, landed in the 15th's (or the next month's) instead, and
the day's net collected was wrong.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.patients.models import Patient
from app.modules.payments.models import PatientEarnedEntry, Payment, Refund
from app.modules.payments.service import PaymentReportsService

DAY = date(2026, 1, 14)
NEXT_DAY = date(2026, 1, 15)
# 20:00 on the 14th in Mexico City is 02:00 UTC on the 15th.
EVENING_UTC = datetime(2026, 1, 15, 2, 0, tzinfo=UTC)


async def _seed(db: AsyncSession, clinic: Clinic, patient: Patient) -> User:
    clinic.timezone = "America/Mexico_City"
    user = User(
        email=f"staff-{uuid4().hex[:8]}@test.com",
        password_hash="x",
        first_name="Dra",
        last_name="Tarde",
    )
    db.add(user)
    await db.flush()
    payment = Payment(
        clinic_id=clinic.id,
        patient_id=patient.id,
        amount=Decimal("100.00"),
        currency="MXN",
        method="cash",
        payment_date=DAY,
        recorded_by=user.id,
    )
    db.add(payment)
    await db.flush()
    db.add(
        Refund(
            clinic_id=clinic.id,
            payment_id=payment.id,
            amount=Decimal("40.00"),
            method="cash",
            reason_code="error",
            refunded_at=EVENING_UTC,
            refunded_by=user.id,
        )
    )
    db.add(
        PatientEarnedEntry(
            clinic_id=clinic.id,
            patient_id=patient.id,
            treatment_id=uuid4(),
            amount=Decimal("250.00"),
            performed_at=EVENING_UTC,
            professional_id=user.id,
            source_event="odontogram.treatment.performed",
        )
    )
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_summary_counts_an_evening_refund_on_its_local_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    await _seed(db_session, test_clinic, test_patient)
    day = await PaymentReportsService.summary(db_session, test_clinic.id, "MXN", DAY, DAY)
    assert (day.total_refunded, day.net_collected) == (Decimal("40.00"), Decimal("60.00"))
    next_day = await PaymentReportsService.summary(
        db_session, test_clinic.id, "MXN", NEXT_DAY, NEXT_DAY
    )
    assert next_day.total_refunded == Decimal("0")


@pytest.mark.asyncio
async def test_refunds_report_uses_the_local_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    await _seed(db_session, test_clinic, test_patient)
    report = await PaymentReportsService.refunds_report(db_session, test_clinic.id, "MXN", DAY, DAY)
    assert report.total_refunded == Decimal("40.00")


@pytest.mark.asyncio
async def test_trends_bucket_an_evening_refund_on_its_local_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    await _seed(db_session, test_clinic, test_patient)
    trends = await PaymentReportsService.trends(
        db_session, test_clinic.id, "MXN", DAY, NEXT_DAY, "day"
    )
    assert [(p.bucket_start, p.collected, p.refunded) for p in trends.points] == [
        (DAY, Decimal("100.00"), Decimal("40.00"))
    ]


@pytest.mark.asyncio
async def test_by_professional_counts_evening_work_on_its_local_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    user = await _seed(db_session, test_clinic, test_patient)
    rows = await PaymentReportsService.by_professional(db_session, test_clinic.id, DAY, DAY)
    assert [(r.professional_id, r.total_earned) for r in rows] == [(user.id, Decimal("250.00"))]
