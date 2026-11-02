"""The recalls KPI's "this month" is the clinic's month (#684).

The month bounds were naive datetimes compared with ``timestamptz``
columns, so they were read in the app process's zone: the same rows gave
1 completed recall on a UTC host and 3 on a Europe/Madrid one.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.patients.models import Patient
from app.modules.recalls.models import Recall
from app.modules.recalls.service import RecallService


@pytest.fixture
def host_tz(monkeypatch):
    """Switch the process zone, restoring it afterwards."""

    def switch(zone: str) -> None:
        monkeypatch.setenv("TZ", zone)
        time.tzset()

    yield switch
    monkeypatch.undo()
    time.tzset()


def _recall(clinic: Clinic, patient: Patient, status: str, at: datetime) -> Recall:
    return Recall(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        due_month=date(2026, 6, 1),
        reason="checkup",
        status=status,
        completed_at=at if status == "done" else None,
        updated_at=at,
    )


@pytest.mark.asyncio
async def test_completed_this_month_follows_the_clinic_month_on_any_host(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient, host_tz
) -> None:
    test_clinic.timezone = "Europe/Madrid"  # UTC+2 in summer
    db_session.add_all(
        [
            # 01:00 on 1 June in Madrid, still May in UTC: June.
            _recall(test_clinic, test_patient, "done", datetime(2026, 5, 31, 23, 0, tzinfo=UTC)),
            _recall(test_clinic, test_patient, "done", datetime(2026, 6, 15, 12, 0, tzinfo=UTC)),
            # 00:30 / 01:30 on 1 July in Madrid, still June in UTC: July.
            _recall(test_clinic, test_patient, "done", datetime(2026, 6, 30, 22, 30, tzinfo=UTC)),
            _recall(test_clinic, test_patient, "done", datetime(2026, 6, 30, 23, 30, tzinfo=UTC)),
            # 23:00 on 31 May in Madrid: May.
            _recall(
                test_clinic, test_patient, "cancelled", datetime(2026, 5, 31, 21, 0, tzinfo=UTC)
            ),
            _recall(
                test_clinic, test_patient, "cancelled", datetime(2026, 6, 10, 9, 0, tzinfo=UTC)
            ),
        ]
    )
    await db_session.commit()

    answers = []
    for zone in ("UTC", "Europe/Madrid", "America/New_York", "Asia/Tokyo"):
        host_tz(zone)
        stats = await RecallService.dashboard_stats(
            db_session, test_clinic.id, today=date(2026, 6, 15)
        )
        answers.append((zone, stats["completed_this_month"], stats["conversion_rate"]))

    # Two June completions and one June cancellation, whatever the host zone.
    assert answers == [
        ("UTC", 2, 0.6667),
        ("Europe/Madrid", 2, 0.6667),
        ("America/New_York", 2, 0.6667),
        ("Asia/Tokyo", 2, 0.6667),
    ]
