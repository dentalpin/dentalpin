"""Budget 7d/14d reminders reach the notifications outbox (issue #287 bug 7).

Before this wiring existed, the cron stamped ``last_reminder_sent_at`` and
the timeline recorded a reminder, but ``notifications`` never subscribed to
``budget.reminder_sent`` — the patient got silence. These tests pin the
contract: enabling the clinic toggle and running ``send_budget_reminders``
(or dispatching a manual reminder) creates a real ``communication_messages``
row — queued, or skipped with an explicit reason, never nothing.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.budget.models import Budget
from app.modules.budget.tasks import send_budget_reminders
from app.modules.budget.workflow import BudgetWorkflowService
from app.modules.notifications.models import (
    ClinicNotificationSettings,
    CommunicationMessage,
)
from app.modules.patients.models import Patient


@pytest_asyncio.fixture
async def reminder_setup(db_session: AsyncSession) -> dict:
    """Clinic with the reminder toggle on + a sent budget 8 days old."""
    user = User(
        email=f"reminder-{uuid4().hex[:8]}@test.com",
        password_hash="x",
        first_name="Rem",
        last_name="Inder",
    )
    db_session.add(user)
    clinic = Clinic(
        id=uuid4(),
        name="Reminder Clinic",
        tax_id="B11223344",
        address={},
        settings={"budget_reminders_enabled": True},
    )
    db_session.add(clinic)
    await db_session.flush()

    patient = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Paz",
        last_name="Iente",
        email="paz@test.com",
        phone="+34600111222",
    )
    db_session.add(patient)
    await db_session.flush()

    budget = Budget(
        clinic_id=clinic.id,
        patient_id=patient.id,
        budget_number="PRES-REM-0001",
        status="sent",
        valid_from=date.today() - timedelta(days=8),
        valid_until=date.today() + timedelta(days=30),
        created_by=user.id,
        total=Decimal("150.00"),
    )
    db_session.add(budget)
    await db_session.commit()

    return {"clinic": clinic, "patient": patient, "budget": budget}


async def _reminder_rows(db: AsyncSession, clinic_id) -> list[CommunicationMessage]:
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


@pytest.mark.asyncio
async def test_send_budget_reminders_job_creates_outbox_row(
    db_session: AsyncSession, reminder_setup: dict
):
    """The cron path end-to-end: toggle on + old sent budget → outbox row."""
    clinic = reminder_setup["clinic"]
    budget = reminder_setup["budget"]

    await send_budget_reminders()

    rows = await _reminder_rows(db_session, clinic.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.patient_id == reminder_setup["patient"].id
    # Queued (email viable) or skipped with an explicit reason — never silence.
    assert row.status in ("queued", "skipped")
    assert row.triggered_by_event == "budget.reminder_sent"

    # The cron stamped the cooldown too.
    refreshed = (
        await db_session.execute(select(Budget).where(Budget.id == budget.id))
    ).scalar_one()
    assert refreshed.last_reminder_sent_at is not None


@pytest.mark.asyncio
async def test_send_reminder_enqueues_with_public_url_and_context(
    db_session: AsyncSession, reminder_setup: dict
):
    """The manual /send-reminder path goes through the same handler and the
    context carries what the templates need (quote number + public link)."""
    clinic = reminder_setup["clinic"]
    budget = reminder_setup["budget"]

    await BudgetWorkflowService.send_reminder(db_session, budget, milestone_days=7)

    rows = await _reminder_rows(db_session, clinic.id)
    assert len(rows) == 1
    ctx = rows[0].context_data
    assert ctx["budget_number"] == "PRES-REM-0001"
    assert ctx["milestone_days"] == 7
    assert ctx["public_url"].endswith(f"/p/budget/{budget.public_token}")


@pytest.mark.asyncio
async def test_budget_reminder_respects_clinic_type_toggle(
    db_session: AsyncSession, reminder_setup: dict
):
    """Disabling the budget_reminder type at clinic level yields an explicit
    skipped row (reason recorded), not a queued message and not silence."""
    clinic = reminder_setup["clinic"]
    budget = reminder_setup["budget"]

    db_session.add(
        ClinicNotificationSettings(
            clinic_id=clinic.id,
            settings={"budget_reminder": {"enabled": False, "auto_send": True}},
        )
    )
    await db_session.commit()

    await BudgetWorkflowService.send_reminder(db_session, budget, milestone_days=7)

    rows = await _reminder_rows(db_session, clinic.id)
    assert len(rows) == 1
    assert rows[0].status == "skipped"
    assert rows[0].error_message == "disabled_at_clinic_level"


@pytest.mark.asyncio
async def test_budget_reminder_skips_patient_without_contact(
    db_session: AsyncSession, reminder_setup: dict
):
    """No email and no phone → the handler bails before enqueue (no row)."""
    clinic = reminder_setup["clinic"]
    patient = reminder_setup["patient"]
    budget = reminder_setup["budget"]

    patient.email = None
    patient.phone = None
    await db_session.commit()

    await BudgetWorkflowService.send_reminder(db_session, budget, milestone_days=7)

    rows = await _reminder_rows(db_session, clinic.id)
    assert rows == []
