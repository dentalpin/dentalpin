"""A snooze note is stamped with the clinic's day and the author's name (#1148).

The stamp used ``datetime.now(UTC)`` and the user's raw UUID. In a clinic
far from UTC the day was off by one for hours every day, and the UUID told
staff nothing while eating most of the two-line clamp in the recall list.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.patients.models import Patient
from app.modules.recalls import service as recall_service
from app.modules.recalls.models import Recall
from app.modules.recalls.service import RecallService

# 12:30 UTC on Feb 28 is already 02:30 on Mar 1 in Kiritimati (UTC+14).
FROZEN = datetime(2026, 2, 28, 12, 30, tzinfo=UTC)


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN.astimezone(tz) if tz else FROZEN.replace(tzinfo=None)


async def _recall(db: AsyncSession, clinic: Clinic, patient: Patient) -> Recall:
    clinic.timezone = "Pacific/Kiritimati"
    recall = Recall(
        clinic_id=clinic.id,
        patient_id=patient.id,
        due_month=date(2026, 3, 1),
        reason="hygiene",
        status="pending",
    )
    db.add(recall)
    await db.flush()
    return recall


@pytest.mark.asyncio
async def test_snooze_note_carries_clinic_day_and_author_name(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient, monkeypatch
):
    monkeypatch.setattr(recall_service, "datetime", _FrozenDatetime)
    author = User(
        email=f"r-{uuid4().hex[:8]}@test.clinic",
        password_hash="x",
        first_name="Ana",
        last_name="Ruiz",
    )
    db_session.add(author)
    recall = await _recall(db_session, test_clinic, test_patient)

    await RecallService.snooze(
        db_session, test_clinic.id, recall.id, 3, "on holiday", by_user=author.id
    )

    assert recall.reason_note == "2026-03-01 (Ana Ruiz): snoozed +3mo · on holiday"


@pytest.mark.asyncio
async def test_snooze_note_without_user_says_system(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient, monkeypatch
):
    monkeypatch.setattr(recall_service, "datetime", _FrozenDatetime)
    recall = await _recall(db_session, test_clinic, test_patient)

    await RecallService.snooze(db_session, test_clinic.id, recall.id, 1, "later", by_user=None)

    assert recall.reason_note == "2026-03-01 (system): snoozed +1mo · later"
