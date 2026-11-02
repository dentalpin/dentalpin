"""Budget numbers are allocated one transaction at a time per clinic (#770)."""

import asyncio
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import User
from app.database import async_session_maker
from app.modules.budget.service import BudgetService


@pytest.mark.asyncio
async def test_concurrent_creates_get_distinct_numbers(
    db_session: AsyncSession, test_clinic, test_patient
):
    """The second create used to read the same max(budget_number) while the
    first was uncommitted, and its insert answered 500 on
    uq_budget_clinic_number_version."""
    user_id = (await db_session.execute(select(User.id))).scalars().first()
    await db_session.commit()

    def data() -> dict:
        return {"patient_id": test_patient.id, "valid_from": date.today(), "items": []}

    async with async_session_maker() as first, async_session_maker() as second:
        one = await BudgetService.create_budget(first, test_clinic.id, user_id, data())
        other = asyncio.create_task(
            BudgetService.create_budget(second, test_clinic.id, user_id, data())
        )
        await asyncio.sleep(0.3)  # the second create reaches the allocation
        await first.commit()
        two = await other
        await second.commit()

    assert one.budget_number != two.budget_number
