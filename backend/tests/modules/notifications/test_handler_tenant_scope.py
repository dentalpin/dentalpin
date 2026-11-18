"""Handlers must read their rows within the event's clinic.

Every handler receives ``clinic_id`` in the event payload but re-read the
appointment/patient/budget by id alone. A payload whose clinic did not own
the row still resolved it, and the message was enqueued for the payload's
clinic about another clinic's patient. These pin the tenant filter added to
each read, on both the wrapped and the inline multi-condition shape.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.agenda.models import Appointment
from app.modules.budget.models import Budget
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.handlers import NotificationHandlers
from app.modules.patients.models import Patient


async def _patient(db: AsyncSession, clinic: Clinic) -> Patient:
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Ana",
        last_name="Test",
        email="ana@example.com",
        status="active",
    )
    db.add(patient)
    await db.flush()
    return patient


async def _member_user_id(db: AsyncSession, clinic: Clinic) -> UUID:
    return (
        await db.execute(
            select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == clinic.id)
        )
    ).scalar_one()


async def _appointment(db: AsyncSession, clinic: Clinic) -> UUID:
    patient = await _patient(db, clinic)
    start = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    appointment = Appointment(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        professional_id=await _member_user_id(db, clinic),
        start_time=start,
        end_time=start + timedelta(hours=1),
    )
    db.add(appointment)
    await db.commit()
    return appointment.id


async def _budget(db: AsyncSession, clinic: Clinic) -> UUID:
    patient = await _patient(db, clinic)
    budget = Budget(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        budget_number=f"PRES-{uuid4().hex[:8]}",
        valid_from=date(2026, 10, 1),
        created_by=await _member_user_id(db, clinic),
    )
    db.add(budget)
    await db.commit()
    return budget.id


def _record_enqueues(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    calls: list[dict] = []

    async def fake_enqueue(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(NotificationGateway, "enqueue", staticmethod(fake_enqueue))
    return calls


@pytest.mark.asyncio
async def test_appointment_cancelled_ignores_a_foreign_clinic(
    db_session: AsyncSession, test_clinic: Clinic, monkeypatch: pytest.MonkeyPatch
) -> None:
    appointment_id = await _appointment(db_session, test_clinic)
    calls = _record_enqueues(monkeypatch)

    await NotificationHandlers.on_appointment_cancelled(
        {"clinic_id": str(uuid4()), "appointment_id": str(appointment_id)}, db=db_session
    )

    assert calls == []


@pytest.mark.asyncio
async def test_appointment_cancelled_enqueues_for_the_owning_clinic(
    db_session: AsyncSession, test_clinic: Clinic, monkeypatch: pytest.MonkeyPatch
) -> None:
    appointment_id = await _appointment(db_session, test_clinic)
    calls = _record_enqueues(monkeypatch)

    await NotificationHandlers.on_appointment_cancelled(
        {"clinic_id": str(test_clinic.id), "appointment_id": str(appointment_id)}, db=db_session
    )

    assert len(calls) == 1
    assert calls[0]["clinic_id"] == test_clinic.id
    assert calls[0]["notification_type"] == "appointment_cancelled"
    assert calls[0]["context"]["appointment_start_at"] == "2026-10-20T09:00:00+00:00"


@pytest.mark.asyncio
async def test_budget_reminder_ignores_a_foreign_clinic(
    db_session: AsyncSession, test_clinic: Clinic, monkeypatch: pytest.MonkeyPatch
) -> None:
    budget_id = await _budget(db_session, test_clinic)
    calls = _record_enqueues(monkeypatch)

    await NotificationHandlers.on_budget_reminder_sent(
        {"clinic_id": str(uuid4()), "budget_id": str(budget_id), "milestone_days": 30},
        db=db_session,
    )

    assert calls == []


@pytest.mark.asyncio
async def test_budget_reminder_enqueues_for_the_owning_clinic(
    db_session: AsyncSession, test_clinic: Clinic, monkeypatch: pytest.MonkeyPatch
) -> None:
    budget_id = await _budget(db_session, test_clinic)
    calls = _record_enqueues(monkeypatch)

    await NotificationHandlers.on_budget_reminder_sent(
        {"clinic_id": str(test_clinic.id), "budget_id": str(budget_id), "milestone_days": 30},
        db=db_session,
    )

    assert len(calls) == 1
    assert calls[0]["clinic_id"] == test_clinic.id
    assert calls[0]["notification_type"] == "budget_reminder"
