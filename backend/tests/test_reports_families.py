"""Patient-stats + operational families: demographics, visits, productivity."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.agenda.models import Appointment
from app.modules.patients.models import Patient
from app.modules.reports.services import OperationalReportService, PatientStatsService
from app.modules.treatment_plan.models import TreatmentPlan


async def _user_id(db: AsyncSession) -> object:
    user = User(
        email=f"ops-{uuid4().hex[:8]}@test.clinic",
        password_hash="not-a-real-hash",
        first_name="Ops",
        last_name="Staff",
    )
    db.add(user)
    await db.commit()
    return user.id


async def _patient(db, clinic_id, *, dob=None, gender=None, city=None) -> Patient:
    row = Patient(
        clinic_id=clinic_id,
        first_name="Test",
        last_name="Patient",
        date_of_birth=dob,
        gender=gender,
        address={"city": city} if city else None,
    )
    db.add(row)
    await db.commit()
    return row


async def _appointment(
    db, clinic_id, patient_id, professional_id, *, days_ago=5, status="completed", cabinet=None
):
    start = datetime.now(UTC) - timedelta(days=days_ago)
    row = Appointment(
        clinic_id=clinic_id,
        patient_id=patient_id,
        professional_id=professional_id,
        cabinet=cabinet,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        status=status,
    )
    db.add(row)
    await db.commit()
    return row


@pytest.mark.asyncio
async def test_demographics(db_session: AsyncSession, test_clinic: Clinic):
    clinic_id = test_clinic.id
    today = date.today()
    await _patient(
        db_session, clinic_id, dob=date(today.year - 30, 1, 1), gender="female", city="Madrid"
    )
    await _patient(
        db_session, clinic_id, dob=date(today.year - 70, 1, 1), gender="male", city="Madrid"
    )
    await _patient(db_session, clinic_id, dob=None, gender=None, city=None)
    archived = await _patient(db_session, clinic_id, gender="male", city="Madrid")
    archived.status = "archived"
    await db_session.commit()

    demo = await PatientStatsService.demographics(db_session, clinic_id)
    assert demo["total_patients"] == 3  # archived patients are not counted
    bands = {b["band"]: b["count"] for b in demo["age_bands"]}
    assert bands["18-34"] == 1
    assert bands["55-74"] == 1
    assert bands["unknown"] == 1
    genders = {g["gender"]: g["count"] for g in demo["genders"]}
    assert genders == {"female": 1, "male": 1, "unknown": 1}
    areas = {a["area"]: a["count"] for a in demo["areas"]}
    assert areas == {"Madrid": 2, "unknown": 1}


@pytest.mark.asyncio
async def test_visit_frequency(db_session: AsyncSession, test_clinic: Clinic):
    clinic_id = test_clinic.id
    pro = await _user_id(db_session)
    date_from = date.today() - timedelta(days=30)
    date_to = date.today()
    # Returning: one visit long ago + one in window.
    returning = await _patient(db_session, clinic_id)
    await _appointment(db_session, clinic_id, returning.id, pro, days_ago=60)
    await _appointment(db_session, clinic_id, returning.id, pro, days_ago=5)
    # New: only visit inside the window.
    new = await _patient(db_session, clinic_id)
    await _appointment(db_session, clinic_id, new.id, pro, days_ago=5)
    # Cancelled never counts.
    cancelled = await _patient(db_session, clinic_id)
    await _appointment(db_session, clinic_id, cancelled.id, pro, days_ago=5, status="cancelled")

    freq = await PatientStatsService.visit_frequency(db_session, clinic_id, date_from, date_to)
    assert freq["new_patients"] == 1
    assert freq["returning_patients"] == 1
    assert freq["total_visits"] == 2
    assert freq["visits_per_patient"] == 1.0


@pytest.mark.asyncio
async def test_productivity(db_session: AsyncSession, test_clinic: Clinic):
    clinic_id = test_clinic.id
    pro_a = await _user_id(db_session)
    pro_b = await _user_id(db_session)
    patient = await _patient(db_session, clinic_id)
    date_from = date.today() - timedelta(days=30)
    date_to = date.today()
    await _appointment(db_session, clinic_id, patient.id, pro_a, days_ago=5, cabinet="A")
    await _appointment(db_session, clinic_id, patient.id, pro_a, days_ago=6, cabinet="A")
    await _appointment(db_session, clinic_id, patient.id, pro_b, days_ago=5, cabinet="B")
    await _appointment(
        db_session, clinic_id, patient.id, pro_b, days_ago=5, status="cancelled", cabinet="B"
    )
    plan = TreatmentPlan(
        clinic_id=clinic_id,
        patient_id=patient.id,
        plan_number="PLAN-TEST-001",
        status="active",
        assigned_professional_id=pro_a,
        created_by=pro_a,
    )
    db_session.add(plan)
    await db_session.commit()

    data = await OperationalReportService.productivity(db_session, clinic_id, date_from, date_to)
    assert data["completed_total"] == 3
    by_pro = {p["professional_id"]: p["completed"] for p in data["by_professional"]}
    assert by_pro == {str(pro_a): 2, str(pro_b): 1}
    by_cab = {c["cabinet"]: c["completed"] for c in data["by_cabinet"]}
    assert by_cab == {"A": 2, "B": 1}
    pipeline = {p["status"]: p["count"] for p in data["plan_pipeline"]}
    assert pipeline.get("active") == 1
