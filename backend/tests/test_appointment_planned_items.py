"""Which planned treatment items may be linked to an appointment (#108).

``AppointmentService.validate_planned_items`` is the only gate between the
appointment treatment selector and the plan: it decides whether a given
``PlannedTreatmentItem`` can be attached to a booking. It had no coverage,
which is how the frontend selector and this gate drifted apart — the
selector stopped offering ``pending`` plans while the gate still accepted
``draft``, and nothing failed until a user hit it.

The rule under test: a plan is bookable while it is still live
(``draft`` / ``pending`` / ``active``) and closed to booking once terminal
(``completed`` / ``closed``). Completion is gated separately and more
strictly — ``complete_session`` still requires ``active``, so money is only
ever booked after the quote is accepted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.agenda.service import AppointmentService
from app.modules.odontogram.models import Treatment
from app.modules.patients.models import Patient
from app.modules.treatment_plan.models import PlannedTreatmentItem, TreatmentPlan

# Plan statuses that must keep their items bookable, and the terminal ones
# that must not. Kept explicit rather than derived so a new status added to
# the workflow shows up here as a deliberate decision.
BOOKABLE = ["draft", "pending", "active"]
NOT_BOOKABLE = ["completed", "closed"]


async def _mkclinic(db: AsyncSession, *, name: str, tax_id: str) -> tuple[UUID, UUID, UUID]:
    """Insert a clinic + creator user + patient. Returns their ids."""
    clinic = Clinic(
        id=uuid4(),
        name=name,
        tax_id=tax_id,
        address={"city": "Madrid"},
        settings={},
    )
    user = User(
        id=uuid4(),
        email=f"dentist-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Dentist",
        last_name="User",
        is_active=True,
    )
    db.add_all([clinic, user])
    await db.flush()
    db.add(ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic.id, role="dentist"))
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Ana", last_name="Paciente")
    db.add(patient)
    await db.flush()
    return clinic.id, user.id, patient.id


async def _mkitem(
    db: AsyncSession,
    clinic_id: UUID,
    user_id: UUID,
    patient_id: UUID,
    *,
    plan_status: str,
    item_status: str = "pending",
) -> PlannedTreatmentItem:
    """A one-item plan in ``plan_status`` with its backing Treatment."""
    plan = TreatmentPlan(
        id=uuid4(),
        clinic_id=clinic_id,
        patient_id=patient_id,
        plan_number=f"PLAN-{uuid4().hex[:8]}",
        title="Plan",
        status=plan_status,
        created_by=user_id,
    )
    treatment = Treatment(
        id=uuid4(),
        clinic_id=clinic_id,
        patient_id=patient_id,
        clinical_type="filling_composite",
        scope="global_mouth",
        status="planned",
        recorded_at=datetime.now(UTC) - timedelta(days=1),
    )
    db.add_all([plan, treatment])
    await db.flush()
    item = PlannedTreatmentItem(
        id=uuid4(),
        clinic_id=clinic_id,
        treatment_plan_id=plan.id,
        treatment_id=treatment.id,
        sequence_order=0,
        status=item_status,
    )
    db.add(item)
    await db.flush()
    return item


@pytest.mark.asyncio
@pytest.mark.parametrize("plan_status", BOOKABLE)
async def test_bookable_plan_statuses_are_accepted(
    db_session: AsyncSession, plan_status: str
) -> None:
    clinic_id, user_id, patient_id = await _mkclinic(
        db_session, name="Book Clinic", tax_id=f"B{uuid4().int % 10**8:08d}"
    )
    item = await _mkitem(db_session, clinic_id, user_id, patient_id, plan_status=plan_status)

    # No raise == accepted.
    await AppointmentService.validate_planned_items(db_session, clinic_id, patient_id, [item.id])


@pytest.mark.asyncio
@pytest.mark.parametrize("plan_status", NOT_BOOKABLE)
async def test_terminal_plan_statuses_are_rejected(
    db_session: AsyncSession, plan_status: str
) -> None:
    clinic_id, user_id, patient_id = await _mkclinic(
        db_session, name="Term Clinic", tax_id=f"B{uuid4().int % 10**8:08d}"
    )
    item = await _mkitem(db_session, clinic_id, user_id, patient_id, plan_status=plan_status)

    with pytest.raises(ValueError, match=f"belongs to {plan_status} plan"):
        await AppointmentService.validate_planned_items(
            db_session, clinic_id, patient_id, [item.id]
        )


@pytest.mark.asyncio
async def test_already_completed_item_is_rejected(db_session: AsyncSession) -> None:
    clinic_id, user_id, patient_id = await _mkclinic(
        db_session, name="Done Clinic", tax_id=f"B{uuid4().int % 10**8:08d}"
    )
    item = await _mkitem(
        db_session,
        clinic_id,
        user_id,
        patient_id,
        plan_status="active",
        item_status="completed",
    )

    with pytest.raises(ValueError, match="is already completed"):
        await AppointmentService.validate_planned_items(
            db_session, clinic_id, patient_id, [item.id]
        )


@pytest.mark.asyncio
async def test_item_from_another_patient_is_rejected(db_session: AsyncSession) -> None:
    clinic_id, user_id, patient_id = await _mkclinic(
        db_session, name="Mix Clinic", tax_id=f"B{uuid4().int % 10**8:08d}"
    )
    other = Patient(id=uuid4(), clinic_id=clinic_id, first_name="Otro", last_name="Paciente")
    db_session.add(other)
    await db_session.flush()
    item = await _mkitem(db_session, clinic_id, user_id, patient_id, plan_status="pending")

    with pytest.raises(ValueError, match="does not belong to patient"):
        await AppointmentService.validate_planned_items(db_session, clinic_id, other.id, [item.id])


@pytest.mark.asyncio
async def test_item_from_another_clinic_is_rejected(db_session: AsyncSession) -> None:
    """Multi-tenancy: a foreign item must read as 'not found', never leak."""
    clinic_a, user_a, patient_a = await _mkclinic(
        db_session, name="Clinic A", tax_id=f"B{uuid4().int % 10**8:08d}"
    )
    clinic_b, user_b, patient_b = await _mkclinic(
        db_session, name="Clinic B", tax_id=f"B{uuid4().int % 10**8:08d}"
    )
    item_b = await _mkitem(db_session, clinic_b, user_b, patient_b, plan_status="pending")

    with pytest.raises(ValueError, match="not found"):
        await AppointmentService.validate_planned_items(
            db_session, clinic_a, patient_a, [item_b.id]
        )
