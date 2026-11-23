"""The recalls KPI "Due this week" counts one week, not a month (#1004).

The window was ``due_month`` in ``[month_start, today + 7]``. ``due_month``
is always the 1st, so it matched every recall of the current month, plus
every recall of next month once ``today + 7`` crossed the month end.

"This week" is now the clinic's Monday-to-Sunday week, read on
``due_date``. A month-only recall (``due_date`` NULL) has no week and
stays under "this month".
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.patients.models import Patient
from app.modules.recalls.models import Recall
from app.modules.recalls.service import RecallService


def _recall(
    clinic: Clinic,
    patient: Patient,
    due_month: date,
    due_date: date | None,
    status: str = "pending",
) -> Recall:
    return Recall(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        due_month=due_month,
        due_date=due_date,
        reason="checkup",
        status=status,
    )


@pytest.mark.asyncio
async def test_due_this_week_is_the_monday_to_sunday_week_near_month_end(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
) -> None:
    nov, dec = date(2026, 11, 1), date(2026, 12, 1)
    db_session.add_all(
        [
            # Counted: dated inside Mon 23 .. Sun 29 November.
            _recall(test_clinic, test_patient, nov, date(2026, 11, 23)),
            _recall(test_clinic, test_patient, nov, date(2026, 11, 29)),
            # Not counted: month-only, the Sunday before, the Monday after,
            # next month, and a closed recall dated this week.
            _recall(test_clinic, test_patient, nov, None),
            _recall(test_clinic, test_patient, nov, None),
            _recall(test_clinic, test_patient, nov, date(2026, 11, 22)),
            _recall(test_clinic, test_patient, nov, date(2026, 11, 30)),
            _recall(test_clinic, test_patient, dec, None),
            _recall(test_clinic, test_patient, dec, date(2026, 12, 2)),
            _recall(test_clinic, test_patient, nov, date(2026, 11, 25), status="done"),
        ]
    )
    await db_session.commit()

    # Thursday 26 November: today + 7 used to reach into December.
    stats = await RecallService.dashboard_stats(
        db_session, test_clinic.id, today=date(2026, 11, 26)
    )

    assert stats["due_this_week"] == 2
    assert stats["due_this_month"] == 6


@pytest.mark.asyncio
async def test_due_this_week_spans_the_month_boundary(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
) -> None:
    dec, jan = date(2026, 12, 1), date(2027, 1, 1)
    db_session.add_all(
        [
            # Week of Wed 30 December: Mon 28 December .. Sun 3 January.
            _recall(test_clinic, test_patient, dec, date(2026, 12, 28)),
            _recall(test_clinic, test_patient, jan, date(2027, 1, 3)),
            _recall(test_clinic, test_patient, jan, date(2027, 1, 4)),
            _recall(test_clinic, test_patient, dec, None),
        ]
    )
    await db_session.commit()

    stats = await RecallService.dashboard_stats(
        db_session, test_clinic.id, today=date(2026, 12, 30)
    )

    assert stats["due_this_week"] == 2
