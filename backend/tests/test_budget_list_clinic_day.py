"""The budget list's date filter selects budgets by the clinic's day.

``Budget.created_at`` is an instant; the filter compared it with naive
midnights, which Postgres reads in the session zone (UTC). In a Mexico City
clinic (UTC-6) a budget created at 19:00 on the 14th (01:00 UTC on the 15th)
was missing from a 14th-only filter and showed up under the 15th.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.budget.models import Budget
from app.modules.budget.service import BudgetService
from app.modules.patients.models import Patient


@pytest.mark.asyncio
async def test_date_filter_uses_the_clinic_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    test_clinic.timezone = "America/Mexico_City"
    user = User(
        email=f"u-{uuid4().hex[:8]}@test.com", password_hash="x", first_name="A", last_name="B"
    )
    db_session.add(user)
    await db_session.flush()
    budget = Budget(
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        budget_number="PRES-2026-0001",
        status="draft",
        valid_from=date(2026, 1, 14),
        created_by=user.id,
        created_at=datetime(2026, 1, 15, 1, 0, tzinfo=UTC),
    )
    db_session.add(budget)
    await db_session.commit()

    async def ids(day: date) -> list:
        rows, _ = await BudgetService.list_budgets(
            db_session, test_clinic.id, date_from=day, date_to=day
        )
        return [b.id for b in rows]

    assert await ids(date(2026, 1, 14)) == [budget.id]
    assert await ids(date(2026, 1, 15)) == []
