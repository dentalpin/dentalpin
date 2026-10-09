"""The auto-close cron must actually run, not just be declared (#).

`auto_close_expired_plans` shipped with
`text("SELECT id, settings FROM clinics WHERE deleted_at IS NULL")`, and
`clinics` has no `deleted_at` — so it raised `UndefinedColumnError` on
its first statement every night and no plan was ever auto-closed. The
only scheduler test asserted the job's *id*, so nothing ever executed it.

These run it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.budget.models import Budget
from app.modules.patients.models import Patient
from app.modules.treatment_plan.models import TreatmentPlan
from app.modules.treatment_plan.tasks import auto_close_expired_plans


@pytest.mark.asyncio
async def test_cron_runs_against_the_real_schema(db_session: AsyncSession) -> None:
    """The regression: it died on its first statement, before any clinic.

    Asserts nothing about plans on purpose — a column that does not exist
    fails here with no fixtures at all, which is how cheap catching this
    would have been.
    """
    await auto_close_expired_plans()


@pytest.mark.asyncio
async def test_cron_closes_a_plan_whose_budget_expired_long_ago(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
) -> None:
    created_by = (
        await db_session.execute(
            select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == test_clinic.id)
        )
    ).scalar_one()
    long_ago = date.today() - timedelta(days=90)

    budget = Budget(
        id=uuid4(),
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        budget_number=f"PRES-{uuid4().hex[:8]}",
        valid_from=long_ago,
        valid_until=long_ago,
        status="expired",
        created_by=created_by,
    )
    db_session.add(budget)
    await db_session.flush()

    plan = TreatmentPlan(
        id=uuid4(),
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        plan_number=f"PLAN-{uuid4().hex[:8]}",
        created_by=created_by,
        status="pending",
        budget_id=budget.id,
        created_at=datetime.now(UTC),
    )
    db_session.add(plan)
    await db_session.commit()

    await auto_close_expired_plans()

    await db_session.refresh(plan)
    assert plan.status == "closed", f"plan still {plan.status!r} — the cron ran but closed nothing"
