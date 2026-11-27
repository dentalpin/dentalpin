"""The copilot's ``send_notification`` builds the same context as the REST send (#1181).

The tool filled only ``patient_name``: an ``appointment_reminder`` queued
through it carried no clinic, date or professional, and a ``budget_sent`` no
number or total, so the templates rendered those blanks (or whatever the
model put in ``context``). It now takes ``appointment_id`` / ``budget_id``,
refuses the appointment and budget types without them, and refuses ids of
another clinic or another patient.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.agenda.models import Appointment
from app.modules.budget.models import Budget
from app.modules.notifications.models import CommunicationMessage
from app.modules.notifications.tools import SendNotificationArgs, _send_notification
from app.modules.patients.models import Patient

START = datetime(2026, 12, 3, 9, 30, tzinfo=UTC)


def _ctx(db: AsyncSession, clinic_id):
    return SimpleNamespace(db=db, clinic_id=clinic_id, supervisor_id=None)


async def _appointment(db: AsyncSession, clinic_id, patient_id) -> Appointment:
    professional = User(
        email=f"pro-{uuid4().hex[:8]}@test.com",
        password_hash="x",
        first_name="Pro",
        last_name="Fesional",
    )
    db.add(professional)
    await db.flush()
    appointment = Appointment(
        clinic_id=clinic_id,
        patient_id=patient_id,
        professional_id=professional.id,
        start_time=START,
        end_time=START + timedelta(hours=1),
        status="scheduled",
    )
    db.add(appointment)
    await db.commit()
    return appointment


async def _other_clinic(db: AsyncSession) -> tuple[Clinic, Patient]:
    clinic = Clinic(id=uuid4(), name="Other Clinic", tax_id="B99887766", address={}, settings={})
    db.add(clinic)
    await db.flush()
    patient = Patient(
        id=uuid4(), clinic_id=clinic.id, first_name="Otra", last_name="Paciente", status="active"
    )
    db.add(patient)
    await db.flush()
    return clinic, patient


async def _rows(db: AsyncSession, clinic_id) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(CommunicationMessage)
            .where(CommunicationMessage.clinic_id == clinic_id)
        )
    ).scalar_one()


async def _context(db: AsyncSession, message_id) -> dict:
    return (
        await db.execute(
            select(CommunicationMessage.context_data).where(CommunicationMessage.id == message_id)
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_appointment_reminder_carries_clinic_and_appointment(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    appointment = await _appointment(db_session, test_clinic.id, test_patient.id)

    result = await _send_notification(
        _ctx(db_session, test_clinic.id),
        SendNotificationArgs(
            patient_id=test_patient.id,
            notification_type="appointment_reminder",
            appointment_id=appointment.id,
        ),
    )

    assert "message_id" in result, result
    context = await _context(db_session, result["message_id"])
    assert context["clinic_name"] == test_clinic.name
    assert context["appointment_start_at"] == START.isoformat()
    assert context["appointment_date"] and context["appointment_time"]
    assert context["professional_name"] == "Pro Fesional"
    assert context["patient_name"] == "Test Patient"


@pytest.mark.asyncio
async def test_appointment_type_without_id_is_refused(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    result = await _send_notification(
        _ctx(db_session, test_clinic.id),
        SendNotificationArgs(patient_id=test_patient.id, notification_type="appointment_reminder"),
    )

    assert result == {"error": "appointment_id_required"}
    assert await _rows(db_session, test_clinic.id) == 0


@pytest.mark.asyncio
async def test_foreign_appointment_is_refused(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    other_clinic, other_patient = await _other_clinic(db_session)
    foreign = await _appointment(db_session, other_clinic.id, other_patient.id)

    result = await _send_notification(
        _ctx(db_session, test_clinic.id),
        SendNotificationArgs(
            patient_id=test_patient.id,
            notification_type="appointment_reminder",
            appointment_id=foreign.id,
        ),
    )

    assert result == {"error": "appointment_not_found"}
    assert await _rows(db_session, test_clinic.id) == 0


@pytest.mark.asyncio
async def test_another_patients_appointment_is_refused(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    sibling = Patient(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Otro",
        last_name="Paciente",
        status="active",
    )
    db_session.add(sibling)
    await db_session.flush()
    appointment = await _appointment(db_session, test_clinic.id, sibling.id)

    result = await _send_notification(
        _ctx(db_session, test_clinic.id),
        SendNotificationArgs(
            patient_id=test_patient.id,
            notification_type="appointment_confirmation",
            appointment_id=appointment.id,
        ),
    )

    assert result == {"error": "patient_mismatch"}
    assert await _rows(db_session, test_clinic.id) == 0


@pytest.mark.asyncio
async def test_budget_sent_carries_budget_and_requires_id(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    creator = (await db_session.execute(select(User).limit(1))).scalar_one()
    budget = Budget(
        id=uuid4(),
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        budget_number=f"PRES-{uuid4().hex[:8]}",
        valid_from=date(2026, 11, 1),
        created_by=creator.id,
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
    )
    db_session.add(budget)
    await db_session.commit()
    ctx = _ctx(db_session, test_clinic.id)

    refused = await _send_notification(
        ctx, SendNotificationArgs(patient_id=test_patient.id, notification_type="budget_sent")
    )
    assert refused == {"error": "budget_id_required"}

    result = await _send_notification(
        ctx,
        SendNotificationArgs(
            patient_id=test_patient.id, notification_type="budget_sent", budget_id=budget.id
        ),
    )
    assert "message_id" in result, result
    context = await _context(db_session, result["message_id"])
    assert context["budget_number"] == budget.budget_number
    assert context["clinic_name"] == test_clinic.name
    assert context["total"]
    assert context["treatments"] == []
