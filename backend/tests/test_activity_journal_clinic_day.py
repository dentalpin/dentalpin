"""The activity journal's date filter selects entries by the clinic's day.

``occurred_at`` is an instant; the filter used UTC midnights. In a Mexico
City clinic (UTC-6) something done at 19:00 on the 14th (01:00 UTC on the
15th) was missing when an admin filtered the log to the 14th, and showed up
under the 15th.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.activity_journal.models import ActivityJournalEntry
from app.modules.activity_journal.service import ActivityJournalService


@pytest.mark.asyncio
async def test_date_filter_uses_the_clinic_day(db_session: AsyncSession, test_clinic: Clinic):
    test_clinic.timezone = "America/Mexico_City"
    entry = ActivityJournalEntry(
        clinic_id=test_clinic.id,
        event_type="patient.updated",
        source_table="patients",
        payload={},
        occurred_at=datetime(2026, 1, 15, 1, 0, tzinfo=UTC),
    )
    db_session.add(entry)
    await db_session.commit()

    async def ids(day: date) -> list:
        rows, _ = await ActivityJournalService.list_entries(
            db_session, test_clinic.id, date_from=day, date_to=day
        )
        return [e.id for e in rows]

    assert await ids(date(2026, 1, 14)) == [entry.id]
    assert await ids(date(2026, 1, 15)) == []
