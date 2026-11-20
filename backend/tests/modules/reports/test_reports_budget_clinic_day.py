"""The budget report cuts its period on the clinic's days.

``Budget.created_at`` is an instant, and the four report queries compared it
with bare dates, which Postgres reads as UTC midnights. In a Mexico City
clinic (UTC-6) a budget created at 19:00 on the 14th (01:00 UTC on the 15th)
was missing from the 14th's summary, professional, status and treatment
breakdowns, and counted on the 15th instead.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.budget.models import Budget, BudgetItem
from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory
from app.modules.patients.models import Patient
from app.modules.reports.services.budget import BudgetReportService

DAY = date(2026, 1, 14)
NEXT_DAY = date(2026, 1, 15)
EVENING_UTC = datetime(2026, 1, 15, 1, 0, tzinfo=UTC)  # 19:00 local on the 14th


@pytest.mark.asyncio
async def test_budget_report_counts_an_evening_budget_on_its_local_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    test_clinic.timezone = "America/Mexico_City"
    user = User(
        email=f"u-{uuid4().hex[:8]}@test.com", password_hash="x", first_name="A", last_name="B"
    )
    db_session.add(user)
    await db_session.flush()
    category = TreatmentCategory(
        clinic_id=test_clinic.id, key=f"c-{uuid4().hex[:6]}", names={"es": "Restauradora"}
    )
    db_session.add(category)
    await db_session.flush()
    item = TreatmentCatalogItem(
        clinic_id=test_clinic.id,
        category_id=category.id,
        internal_code=f"T-{uuid4().hex[:6]}",
        names={"es": "Empaste"},
        default_price=Decimal("50.00"),
    )
    budget = Budget(
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        budget_number="PRES-2026-0001",
        status="draft",
        valid_from=DAY,
        created_by=user.id,
        created_at=EVENING_UTC,
    )
    db_session.add_all([item, budget])
    await db_session.flush()
    db_session.add(
        BudgetItem(
            clinic_id=test_clinic.id,
            budget_id=budget.id,
            catalog_item_id=item.id,
            unit_price=Decimal("50.00"),
            line_total=Decimal("50.00"),
        )
    )
    await db_session.commit()

    async def counts(day: date) -> tuple[int, int, int, int]:
        summary = await BudgetReportService.get_summary(db_session, test_clinic.id, day, day)
        pros = await BudgetReportService.get_by_professional(db_session, test_clinic.id, day, day)
        statuses = await BudgetReportService.get_by_status(db_session, test_clinic.id, day, day)
        treatments = await BudgetReportService.get_by_treatment(
            db_session, test_clinic.id, day, day
        )
        return (summary["total_created"], len(pros), len(statuses), len(treatments))

    assert await counts(DAY) == (1, 1, 1, 1)
    assert await counts(NEXT_DAY) == (0, 0, 0, 0)
