"""Plan conversion arithmetic and SQL construction without a live database."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.modules.reports.services import PlanConversionReportService


class _Rows:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    def all(self):
        return self.rows


@pytest.mark.asyncio
async def test_conversion_rates_are_cohort_based_and_zero_safe():
    result = _Rows(
        [
            SimpleNamespace(id="completed", status="completed", items=2, done=2, booked=True),
            SimpleNamespace(id="active", status="active", items=2, done=1, booked=False),
        ]
    )
    db = SimpleNamespace(
        scalar=AsyncMock(return_value="Europe/Madrid"),
        execute=AsyncMock(return_value=result),
    )

    data = await PlanConversionReportService.get(
        db, "clinic-id", date(2026, 2, 1), date(2026, 2, 28)
    )

    statement = db.execute.await_args.args[0]
    assert "EXISTS" in str(statement.compile(dialect=postgresql.dialect())).upper()
    assert data["confirmed_plans"] == 2
    assert data["booked_plans"] == 1
    assert data["completed_plans"] == 1
    assert data["items_total"] == 4
    assert data["items_completed"] == 3
    assert data["booking_conversion_rate"] == 0.5
    assert data["plan_completion_rate"] == 0.5
    assert data["item_completion_rate"] == 0.75


@pytest.mark.asyncio
async def test_conversion_empty_cohort_has_no_nan_or_division_by_zero():
    db = SimpleNamespace(
        scalar=AsyncMock(return_value="UTC"),
        execute=AsyncMock(return_value=_Rows([])),
    )
    data = await PlanConversionReportService.get(
        db, "clinic-id", date(2026, 1, 1), date(2026, 1, 31)
    )
    assert data["booking_conversion_rate"] == 0.0
    assert data["plan_completion_rate"] == 0.0
    assert data["item_completion_rate"] == 0.0
