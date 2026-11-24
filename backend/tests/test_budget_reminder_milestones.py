"""Budget reminders fire once at 7 and once at 14 days after sending (#1115).

The cron used to count from ``valid_from`` (the day the quote was drafted)
and only remembered a 5-day cooldown, so a quote got reminders on days
7, 13, 19, 25... and a quote drafted long before sending was reminded the
morning after it went out. These tests run ``_send_reminders_for_clinic``
once per simulated clinic day and check which days produced a reminder.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.budget.models import Budget, BudgetHistory
from app.modules.budget.tasks import _send_reminders_for_clinic
from app.modules.budget.workflow import BudgetWorkflowService
from app.modules.notifications.models import CommunicationMessage
from app.modules.patients.models import Patient

MADRID = ZoneInfo("Europe/Madrid")
DAY0 = date(2026, 3, 2)


@pytest_asyncio.fixture
async def milestone_setup(db_session: AsyncSession) -> dict:
    user = User(
        email=f"milestone-{uuid4().hex[:8]}@test.com",
        password_hash="x",
        first_name="Mile",
        last_name="Stone",
    )
    db_session.add(user)
    clinic = Clinic(
        id=uuid4(),
        name="Milestone Clinic",
        tax_id="B11223355",
        address={},
        timezone="Europe/Madrid",
        settings={"budget_reminders_enabled": True},
    )
    db_session.add(clinic)
    await db_session.flush()
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Paz",
        last_name="Iente",
        email="paz-milestone@test.com",
        phone="+34600111333",
    )
    db_session.add(patient)
    await db_session.commit()
    return {"clinic": clinic, "patient": patient, "user": user}


async def _sent_budget(
    db: AsyncSession, setup: dict, *, drafted: date, sent_at: datetime | None
) -> Budget:
    budget = Budget(
        clinic_id=setup["clinic"].id,
        patient_id=setup["patient"].id,
        budget_number=f"PRES-MS-{uuid4().hex[:6]}",
        status="sent",
        valid_from=drafted,
        valid_until=drafted + timedelta(days=60),
        created_by=setup["user"].id,
        total=Decimal("150.00"),
    )
    db.add(budget)
    await db.flush()
    if sent_at is not None:
        db.add(
            BudgetHistory(
                clinic_id=budget.clinic_id,
                budget_id=budget.id,
                action="sent",
                changed_by=setup["user"].id,
                changed_at=sent_at,
                new_state={"sent_at": sent_at.isoformat(), "send_method": "email"},
            )
        )
    await db.commit()
    return budget


async def _reminders(db: AsyncSession, clinic_id) -> list[CommunicationMessage]:
    return list(
        (
            await db.execute(
                select(CommunicationMessage).where(
                    CommunicationMessage.clinic_id == clinic_id,
                    CommunicationMessage.template_key == "budget_reminder",
                )
            )
        )
        .scalars()
        .all()
    )


async def _simulate(db: AsyncSession, clinic_id, budget: Budget, days: range) -> list[int]:
    """Run the cron once per clinic day; return the day offsets that reminded.

    ``send_reminder`` stamps the real clock, so after each reminder the stamp
    is moved to 09:00 clinic time on the simulated day.
    """
    fired: list[int] = []
    seen = len(await _reminders(db, clinic_id))
    for offset in days:
        today = DAY0 + timedelta(days=offset)
        await _send_reminders_for_clinic(clinic_id, today, asyncio.Semaphore(1))
        count = len(await _reminders(db, clinic_id))
        if count > seen:
            fired.append(offset)
            seen = count
            await db.execute(
                update(Budget)
                .where(Budget.id == budget.id)
                .values(last_reminder_sent_at=datetime.combine(today, time(9), tzinfo=MADRID))
            )
            await db.commit()
    return fired


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=MADRID)


@pytest.mark.asyncio
async def test_reminders_fire_once_at_7_and_14_days_after_sending(
    db_session: AsyncSession, milestone_setup: dict
):
    clinic_id = milestone_setup["clinic"].id
    budget = await _sent_budget(db_session, milestone_setup, drafted=DAY0, sent_at=_at(DAY0, 10))

    fired = await _simulate(db_session, clinic_id, budget, range(0, 40))

    assert fired == [7, 14]
    milestones = [r.context_data["milestone_days"] for r in await _reminders(db_session, clinic_id)]
    assert sorted(milestones) == [7, 14]


@pytest.mark.asyncio
async def test_count_starts_at_the_send_not_the_draft(
    db_session: AsyncSession, milestone_setup: dict
):
    """Drafted 10 days before it was handed over: nothing until day 7 after sending."""
    clinic_id = milestone_setup["clinic"].id
    budget = await _sent_budget(
        db_session,
        milestone_setup,
        drafted=DAY0 - timedelta(days=10),
        sent_at=_at(DAY0, 10),
    )

    fired = await _simulate(db_session, clinic_id, budget, range(0, 30))

    assert fired == [7, 14]


@pytest.mark.asyncio
async def test_send_day_is_the_clinic_calendar_day(db_session: AsyncSession, milestone_setup: dict):
    """00:30 in Madrid is still the previous UTC day: the clinic's day counts."""
    clinic_id = milestone_setup["clinic"].id
    sent_at = _at(DAY0 + timedelta(days=1), 0, 30)
    assert sent_at.astimezone(UTC).date() == DAY0
    budget = await _sent_budget(db_session, milestone_setup, drafted=DAY0, sent_at=sent_at)

    fired = await _simulate(db_session, clinic_id, budget, range(0, 30))

    assert fired == [8, 15]


@pytest.mark.asyncio
async def test_missed_cron_days_send_only_the_latest_milestone_once(
    db_session: AsyncSession, milestone_setup: dict
):
    """Cron down until day 20: one 14-day reminder, no catch-up 7-day one."""
    clinic_id = milestone_setup["clinic"].id
    budget = await _sent_budget(db_session, milestone_setup, drafted=DAY0, sent_at=_at(DAY0, 10))

    fired = await _simulate(db_session, clinic_id, budget, range(20, 40))

    assert fired == [20]
    rows = await _reminders(db_session, clinic_id)
    assert [r.context_data["milestone_days"] for r in rows] == [14]


@pytest.mark.asyncio
async def test_automatic_milestone_is_queued_once_manual_always(
    db_session: AsyncSession, milestone_setup: dict
):
    """Backstop in the notifications handler: the same automatic milestone
    published twice queues one message; manual reminders are not deduplicated."""
    clinic_id = milestone_setup["clinic"].id
    budget = await _sent_budget(db_session, milestone_setup, drafted=DAY0, sent_at=_at(DAY0, 10))

    for _ in range(2):
        await BudgetWorkflowService.send_reminder(
            db_session, budget, milestone_days=7, automatic=True
        )
    assert len(await _reminders(db_session, clinic_id)) == 1

    for _ in range(2):
        await BudgetWorkflowService.send_reminder(db_session, budget, milestone_days=7)
    assert len(await _reminders(db_session, clinic_id)) == 3
