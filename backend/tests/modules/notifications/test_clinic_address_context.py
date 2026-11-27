"""Patient messages carry the clinic address for the email footer (#1154).

``base.html`` prints ``clinic_address`` in every footer, but the cancelled
appointment and the three budget handlers sent only name and phone.
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

ADDRESS = {"street": "Test St", "city": "Madrid"}


async def _user_id(db: AsyncSession, clinic: Clinic) -> UUID:
    return (
        await db.execute(
            select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == clinic.id)
        )
    ).scalar_one()


async def _appointment(db: AsyncSession, clinic: Clinic, patient: Patient) -> UUID:
    start = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    appointment = Appointment(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        professional_id=await _user_id(db, clinic),
        start_time=start,
        end_time=start + timedelta(hours=1),
    )
    db.add(appointment)
    await db.commit()
    return appointment.id


async def _budget(db: AsyncSession, clinic: Clinic, patient: Patient) -> UUID:
    budget = Budget(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        budget_number=f"PRES-{uuid4().hex[:8]}",
        status="accepted",
        valid_from=date(2026, 10, 1),
        created_by=await _user_id(db, clinic),
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
async def test_appointment_cancelled_context_has_clinic_address(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appointment_id = await _appointment(db_session, test_clinic, test_patient)
    calls = _record_enqueues(monkeypatch)
    await NotificationHandlers.on_appointment_cancelled(
        {"clinic_id": str(test_clinic.id), "appointment_id": str(appointment_id)}, db=db_session
    )
    assert calls[0]["context"]["clinic_address"] == ADDRESS


@pytest.mark.asyncio
async def test_budget_sent_context_has_clinic_address(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budget_id = await _budget(db_session, test_clinic, test_patient)
    calls = _record_enqueues(monkeypatch)
    await NotificationHandlers.on_budget_sent(
        {"clinic_id": str(test_clinic.id), "budget_id": str(budget_id), "send_method": "email"},
        db=db_session,
    )
    assert calls[0]["context"]["clinic_address"] == ADDRESS


@pytest.mark.asyncio
async def test_budget_accepted_context_has_clinic_address(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budget_id = await _budget(db_session, test_clinic, test_patient)
    calls = _record_enqueues(monkeypatch)
    await NotificationHandlers.on_budget_accepted(
        {"clinic_id": str(test_clinic.id), "budget_id": str(budget_id)}, db=db_session
    )
    assert calls[0]["context"]["clinic_address"] == ADDRESS


@pytest.mark.asyncio
async def test_budget_reminder_context_has_clinic_address(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budget_id = await _budget(db_session, test_clinic, test_patient)
    calls = _record_enqueues(monkeypatch)
    await NotificationHandlers.on_budget_reminder_sent(
        {"clinic_id": str(test_clinic.id), "budget_id": str(budget_id), "milestone_days": 30},
        db=db_session,
    )
    assert calls[0]["context"]["clinic_address"] == ADDRESS
