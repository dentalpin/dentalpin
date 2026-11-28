"""An omitted create date is the clinic's today, not the server's.

Four create schemas defaulted a date with ``Field(default_factory=date.today)``:
the payment date (payments, and billing's invoice payment), a quote's
``valid_from`` and an orthodontic case's ``start_date``. That runs on the
server, which is on UTC, so for hours every day the default was the wrong
calendar day for the clinic. The services now fill it with
``clinic_today_for``.

The clinic gets a zone whose day differs from UTC's right now (UTC+14 from
10:00 UTC, UTC-11 before 11:00 UTC), so the old default fails at any hour.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.core.utils.dates import clinic_today
from app.modules.billing.schemas import InvoicePaymentApply
from app.modules.budget.schemas import BudgetCreate
from app.modules.budget.service import BudgetService
from app.modules.orthodontics.schemas import OrthoCaseCreate
from app.modules.orthodontics.service import OrthoCaseService


async def _clinic_off_the_utc_day(db: AsyncSession, clinic: Clinic) -> date:
    zone = "Pacific/Kiritimati" if datetime.now(UTC).hour >= 10 else "Pacific/Pago_Pago"
    clinic.timezone = zone
    await db.commit()
    today = clinic_today(zone)
    assert today != datetime.now(UTC).date()
    return today


@pytest.mark.asyncio
async def test_payment_without_a_date_is_on_the_clinic_day(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic, test_patient
) -> None:
    today = await _clinic_off_the_utc_day(db_session, test_clinic)
    response = await client.post(
        "/api/v1/payments",
        json={
            "patient_id": str(test_patient.id),
            "amount": "20.00",
            "method": "cash",
            "allocations": [{"target_type": "on_account", "amount": "20.00"}],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["payment_date"] == today.isoformat()
    # Billing's invoice payment hands the same None to record_payment.
    assert InvoicePaymentApply(amount=Decimal("1"), method="cash").payment_date is None


@pytest.mark.asyncio
async def test_quote_without_valid_from_starts_on_the_clinic_day(
    db_session: AsyncSession, test_clinic, test_patient
) -> None:
    today = await _clinic_off_the_utc_day(db_session, test_clinic)
    user_id = await db_session.scalar(
        select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == test_clinic.id)
    )
    budget = await BudgetService.create_budget(
        db_session,
        test_clinic.id,
        user_id,
        BudgetCreate(patient_id=test_patient.id).model_dump(),
    )
    assert budget.valid_from == today


@pytest.mark.asyncio
async def test_ortho_case_without_start_date_starts_on_the_clinic_day(
    db_session: AsyncSession, test_clinic, test_patient
) -> None:
    today = await _clinic_off_the_utc_day(db_session, test_clinic)
    case, _ = await OrthoCaseService.create(
        db_session,
        test_clinic.id,
        OrthoCaseCreate(patient_id=test_patient.id, appliance_type="brackets_metal"),
    )
    assert case.start_date == today
