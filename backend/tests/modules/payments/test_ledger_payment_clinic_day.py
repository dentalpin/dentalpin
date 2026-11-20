"""The patient ledger dates a payment on the clinic's day.

``Payment.payment_date`` is the clinic's calendar day, but the ledger
timeline anchored it at UTC midnight. In every zone behind UTC that
instant is the evening before, so the patient's Pagos panel (which
renders ``occurred_at`` in the browser's zone) showed each payment one
day early, at any hour of the day.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.patients.models import Patient
from app.modules.payments.models import Payment
from app.modules.payments.service import LedgerService

DAY = date(2026, 1, 12)


@pytest.mark.asyncio
async def test_payment_entry_falls_on_its_payment_date_in_the_clinic_zone(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    test_clinic.timezone = "America/Mexico_City"
    user = User(
        email=f"staff-{uuid4().hex[:8]}@test.com", password_hash="x", first_name="A", last_name="B"
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Payment(
            clinic_id=test_clinic.id,
            patient_id=test_patient.id,
            amount=Decimal("100.00"),
            currency="MXN",
            method="cash",
            payment_date=DAY,
            recorded_by=user.id,
        )
    )
    await db_session.commit()

    ledger = await LedgerService.get_patient_ledger(
        db_session, test_clinic.id, test_patient.id, "MXN"
    )
    (entry,) = [e for e in ledger.timeline if e.entry_type == "payment"]
    assert entry.occurred_at.astimezone(ZoneInfo("America/Mexico_City")).date() == DAY
