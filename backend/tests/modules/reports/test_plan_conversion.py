"""Confirmed-plan cohorts must use linked appointments and completion state."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.agenda.models import Appointment
from app.modules.odontogram.models import Treatment
from app.modules.patients.models import Patient
from app.modules.reports.services import PlanConversionReportService
from app.modules.treatment_plan.models import (
    AppointmentTreatment,
    PlannedTreatmentItem,
    TreatmentPlan,
)


@pytest.mark.asyncio
async def test_conversion_counts_confirmed_cohort_linked_bookings_and_completed_items(
    db_session: AsyncSession, test_clinic: Clinic
):
    user = User(
        email=f"conversion-{uuid4().hex[:8]}@test.clinic",
        password_hash="not-a-real-hash",
        first_name="Report",
        last_name="Doctor",
    )
    patient = Patient(
        clinic_id=test_clinic.id,
        first_name="Report",
        last_name="Patient",
        phone="+34912222222",
    )
    db_session.add_all([user, patient])
    await db_session.flush()
    cohort_date = date.today()
    confirmed = datetime.combine(
        cohort_date, time(12), tzinfo=ZoneInfo(test_clinic.timezone or "UTC")
    ).astimezone(UTC)
    plan = TreatmentPlan(
        clinic_id=test_clinic.id,
        patient_id=patient.id,
        plan_number=f"PLAN-CONV-{uuid4().hex[:8]}",
        status="completed",
        confirmed_at=confirmed,
        created_by=user.id,
    )
    db_session.add(plan)
    treatment = Treatment(
        clinic_id=test_clinic.id,
        patient_id=patient.id,
        clinical_type="crown",
        scope="tooth",
        status="planned",
        recorded_at=confirmed,
        price_snapshot=Decimal("500.00"),
    )
    db_session.add(treatment)
    await db_session.flush()
    item = PlannedTreatmentItem(
        clinic_id=test_clinic.id,
        treatment_plan_id=plan.id,
        treatment_id=treatment.id,
        sequence_order=1,
        status="completed",
        completed_at=confirmed,
        completed_by=user.id,
    )
    appointment = Appointment(
        clinic_id=test_clinic.id,
        patient_id=patient.id,
        professional_id=user.id,
        start_time=confirmed + timedelta(days=2),
        end_time=confirmed + timedelta(days=2, minutes=45),
        status="completed",
    )
    db_session.add_all([item, appointment])
    await db_session.flush()
    db_session.add(
        AppointmentTreatment(
            appointment_id=appointment.id,
            planned_treatment_item_id=item.id,
            completed_in_appointment=True,
        )
    )
    draft = TreatmentPlan(
        clinic_id=test_clinic.id,
        patient_id=patient.id,
        plan_number=f"PLAN-DRAFT-{uuid4().hex[:8]}",
        status="draft",
        confirmed_at=confirmed,
        created_by=user.id,
    )
    db_session.add(draft)
    await db_session.commit()

    metrics = await PlanConversionReportService.get(
        db_session, test_clinic.id, cohort_date, cohort_date
    )
    assert metrics["confirmed_plans"] == 1
    assert metrics["booked_plans"] == 1
    assert metrics["completed_plans"] == 1
    assert metrics["items_total"] == 1
    assert metrics["items_completed"] == 1
    assert metrics["booking_conversion_rate"] == 1.0
    assert metrics["item_completion_rate"] == 1.0


@pytest.mark.asyncio
async def test_conversion_returns_zero_rates_for_empty_cohort(
    db_session: AsyncSession, test_clinic: Clinic
):
    metrics = await PlanConversionReportService.get(
        db_session, test_clinic.id, date(2020, 1, 1), date(2020, 1, 31)
    )
    assert metrics["confirmed_plans"] == 0
    assert metrics["booking_conversion_rate"] == 0.0
    assert metrics["plan_completion_rate"] == 0.0
    assert metrics["item_completion_rate"] == 0.0


@pytest.mark.asyncio
async def test_conversion_rejects_reversed_dates(db_session: AsyncSession, test_clinic: Clinic):
    with pytest.raises(ValueError, match="on or after"):
        await PlanConversionReportService.get(
            db_session, test_clinic.id, date(2026, 2, 1), date(2026, 1, 1)
        )
