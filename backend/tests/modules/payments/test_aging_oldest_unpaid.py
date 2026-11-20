"""Aging receivables buckets a patient by the oldest *unpaid* earned entry.

The bucket came from the oldest earned entry overall, so a patient who had
paid every old treatment and owed only last week's was reported as 90+
days overdue. The age was also taken from the UTC date of ``performed_at``.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.core.utils.dates import clinic_today_for
from app.modules.patients.models import Patient
from app.modules.payments.models import PatientEarnedEntry, Payment
from app.modules.payments.service import PaymentReportsService

MEXICO = ZoneInfo("America/Mexico_City")


async def _staff(db: AsyncSession) -> User:
    user = User(
        email=f"staff-{uuid4().hex[:8]}@test.com", password_hash="x", first_name="A", last_name="B"
    )
    db.add(user)
    await db.flush()
    return user


def _earned(clinic: Clinic, patient: Patient, amount: str, at: datetime) -> PatientEarnedEntry:
    return PatientEarnedEntry(
        clinic_id=clinic.id,
        patient_id=patient.id,
        treatment_id=uuid4(),
        amount=Decimal(amount),
        performed_at=at,
        source_event="odontogram.treatment.performed",
    )


def _buckets(result) -> dict[str, tuple[Decimal, int]]:
    return {b.label: (b.total, b.patient_count) for b in result.buckets}


@pytest.mark.asyncio
async def test_a_paid_old_treatment_does_not_age_a_new_debt(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    test_clinic.timezone = "America/Mexico_City"
    user = await _staff(db_session)
    today = await clinic_today_for(db_session, test_clinic.id)
    noon = time(12, 0)
    old = datetime.combine(today - timedelta(days=200), noon, tzinfo=MEXICO)
    recent = datetime.combine(today - timedelta(days=5), noon, tzinfo=MEXICO)
    db_session.add_all(
        [
            _earned(test_clinic, test_patient, "100.00", old),
            _earned(test_clinic, test_patient, "50.00", recent),
            Payment(
                clinic_id=test_clinic.id,
                patient_id=test_patient.id,
                amount=Decimal("100.00"),
                currency="MXN",
                method="cash",
                payment_date=today - timedelta(days=199),
                recorded_by=user.id,
            ),
        ]
    )
    await db_session.commit()

    buckets = _buckets(
        await PaymentReportsService.aging_receivables(db_session, test_clinic.id, "MXN")
    )
    assert buckets["0-30"] == (Decimal("50.00"), 1)
    assert buckets["90+"] == (Decimal("0"), 0)


@pytest.mark.asyncio
async def test_age_is_counted_in_clinic_days(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    # 19:00 in Mexico City, 31 clinic days ago, is 01:00 UTC on the next
    # date: the UTC date made it 30 days old.
    test_clinic.timezone = "America/Mexico_City"
    today = await clinic_today_for(db_session, test_clinic.id)
    evening = datetime.combine(today - timedelta(days=31), time(19, 0), tzinfo=MEXICO)
    db_session.add(_earned(test_clinic, test_patient, "80.00", evening))
    await db_session.commit()

    buckets = _buckets(
        await PaymentReportsService.aging_receivables(db_session, test_clinic.id, "MXN")
    )
    assert buckets["31-60"] == (Decimal("80.00"), 1)
    assert buckets["0-30"] == (Decimal("0"), 0)
