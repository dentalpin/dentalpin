"""Odontogram and periodontogram timelines date entries on the clinic's day.

``recorded_at`` / ``changed_at`` / ``closed_at`` are UTC instants. The
timelines took their UTC date, and "the odontogram on <day>" stopped at
23:59 UTC. In a Mexico City clinic (UTC-6) a crown charted at 19:00 on the
14th (01:00 UTC on the 15th) was listed under the 15th, was missing from the
14th's chart and showed in the 15th's; a perio exam closed that evening was
dated the 15th as well.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.odontogram.models import OdontogramHistory, Treatment
from app.modules.odontogram.service import OdontogramService
from app.modules.patients.models import Patient
from app.modules.periodontogram.models import PeriodontogramSnapshot
from app.modules.periodontogram.service import PeriodontogramService

DAY = date(2026, 1, 14)
# 19:00 on the 14th in Mexico City is 01:00 UTC on the 15th.
EVENING_UTC = datetime(2026, 1, 15, 1, 0, tzinfo=UTC)


async def _user(db: AsyncSession) -> User:
    user = User(
        email=f"dr-{uuid4().hex[:8]}@test.com",
        password_hash="x",
        first_name="Dra",
        last_name="Tarde",
    )
    db.add(user)
    await db.flush()
    return user


async def _chart_evening_crown(db: AsyncSession, clinic: Clinic, patient: Patient) -> None:
    clinic.timezone = "America/Mexico_City"
    user = await _user(db)
    db.add(
        Treatment(
            clinic_id=clinic.id,
            patient_id=patient.id,
            clinical_type="crown",
            status="planned",
            recorded_at=EVENING_UTC,
        )
    )
    db.add(
        OdontogramHistory(
            clinic_id=clinic.id,
            patient_id=patient.id,
            tooth_number=16,
            change_type="general_condition",
            old_condition="healthy",
            new_condition="caries",
            changed_by=user.id,
            changed_at=EVENING_UTC,
        )
    )
    await db.commit()


@pytest.mark.asyncio
async def test_odontogram_timeline_lists_evening_work_on_its_local_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    await _chart_evening_crown(db_session, test_clinic, test_patient)
    dates = await OdontogramService.get_timeline_dates(db_session, test_clinic.id, test_patient.id)
    assert dates == [{"date": "2026-01-14", "change_count": 2}]


@pytest.mark.asyncio
async def test_odontogram_at_date_includes_evening_work_of_that_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    await _chart_evening_crown(db_session, test_clinic, test_patient)
    chart = await OdontogramService.get_odontogram_at_date(
        db_session, test_clinic.id, test_patient.id, DAY
    )
    assert [t["clinical_type"] for t in chart["treatments"]] == ["crown"]
    assert [t["tooth_number"] for t in chart["teeth"]] == [16]

    day_before = await OdontogramService.get_odontogram_at_date(
        db_session, test_clinic.id, test_patient.id, date(2026, 1, 13)
    )
    assert day_before["treatments"] == [] and day_before["teeth"] == []


@pytest.mark.asyncio
async def test_periodontogram_timeline_dates_an_evening_exam_on_its_local_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    test_clinic.timezone = "America/Mexico_City"
    user = await _user(db_session)
    db_session.add(
        PeriodontogramSnapshot(
            clinic_id=test_clinic.id,
            patient_id=test_patient.id,
            status="closed",
            recorded_at=EVENING_UTC,
            recorded_by=user.id,
            closed_at=EVENING_UTC,
            closed_by=user.id,
        )
    )
    await db_session.commit()
    timeline = await PeriodontogramService.get_timeline(db_session, test_clinic.id, test_patient.id)
    assert [row["date"] for row in timeline] == ["2026-01-14"]
