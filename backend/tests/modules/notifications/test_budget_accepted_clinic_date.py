"""The "budget accepted" message dates the acceptance on the clinic's day.

``accepted_date`` was ``budget.updated_at.strftime(...)`` — the UTC day. In a
Mexico City clinic (UTC-6) a quote accepted at 19:00 on the 14th (01:00 UTC
on the 15th) was confirmed to the patient as accepted on the 15th.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.budget.models import Budget
from app.modules.notifications.handlers import NotificationHandlers
from app.modules.notifications.models import CommunicationMessage
from app.modules.patients.models import Patient


async def _accepted_budget(db: AsyncSession, clinic: Clinic, patient: Patient) -> Budget:
    clinic.timezone = "America/Mexico_City"
    user = User(
        email=f"u-{uuid4().hex[:8]}@test.com", password_hash="x", first_name="A", last_name="B"
    )
    db.add(user)
    await db.flush()
    budget = Budget(
        clinic_id=clinic.id,
        patient_id=patient.id,
        budget_number="PRES-2026-0001",
        status="accepted",
        valid_from=date(2026, 1, 14),
        created_by=user.id,
        updated_at=datetime(2026, 1, 15, 1, 0, tzinfo=UTC),
    )
    db.add(budget)
    await db.commit()
    return budget


async def _accepted_date(db: AsyncSession, clinic_id) -> str:
    row = (
        await db.execute(
            select(CommunicationMessage).where(
                CommunicationMessage.clinic_id == clinic_id,
                CommunicationMessage.template_key == "budget_accepted",
            )
        )
    ).scalar_one()
    return row.context_data["accepted_date"]


@pytest.mark.asyncio
async def test_event_message_uses_the_clinic_day(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    budget = await _accepted_budget(db_session, test_clinic, test_patient)
    await NotificationHandlers.on_budget_accepted(
        {"clinic_id": str(test_clinic.id), "budget_id": str(budget.id)}, db=db_session
    )
    assert await _accepted_date(db_session, test_clinic.id) == "14/01/2026"


@pytest.mark.asyncio
async def test_manual_send_uses_the_clinic_day(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
):
    budget = await _accepted_budget(db_session, test_clinic, test_patient)
    clinic_id, budget_id = test_clinic.id, budget.id
    response = await client.post(
        "/api/v1/notifications/send",
        json={"notification_type": "budget_accepted", "budget_id": str(budget_id)},
        headers=auth_headers,
    )
    assert response.status_code in (200, 201), response.text
    assert await _accepted_date(db_session, clinic_id) == "14/01/2026"
