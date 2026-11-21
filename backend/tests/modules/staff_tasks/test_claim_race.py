"""Two people claiming the same task at once: one claim, one owner.

``update_task`` checked the transition on an unlocked copy of the task. Two
staff members clicking "Claim" on the same open task both saw ``open`` and
both passed ``open -> claimed``: each request wrote its own caller as the
assignee (the second overwrote the first) and ``staff_task.status_changed``
fired twice, so the activity journal shows the task claimed by two people.
Production hands each request its own session, so this test does too.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.core.events import EventType, event_bus
from app.database import async_session_maker
from app.modules.staff_tasks.models import StaffTask
from app.modules.staff_tasks.schemas import StaffTaskCreate, StaffTaskUpdate
from app.modules.staff_tasks.service import StaffTaskService


async def _claim(clinic_id: UUID, task_id: UUID, actor_id: UUID) -> UUID | None:
    async with async_session_maker() as session:
        task = await StaffTaskService.update_task(
            session, clinic_id, task_id, StaffTaskUpdate(status="claimed"), actor_id=actor_id
        )
        return task.assignee_id


@pytest.mark.asyncio
async def test_a_simultaneous_claim_has_one_owner(db_session: AsyncSession, test_clinic: Clinic):
    users = [
        User(email=f"claim-{n}@staff-tasks.test", password_hash="x", first_name="S", last_name=n)
        for n in ("a", "b")
    ]
    db_session.add_all(users)
    await db_session.commit()
    task = await StaffTaskService.create_task(
        db_session, test_clinic.id, StaffTaskCreate(title="Prepare implant kit"), created_by=None
    )

    changes: list[dict] = []

    async def record(data: dict, *, db) -> None:
        changes.append(data)

    event_bus.subscribe(EventType.STAFF_TASK_STATUS_CHANGED, record)
    try:
        reported = await asyncio.gather(*(_claim(test_clinic.id, task.id, u.id) for u in users))
    finally:
        event_bus.unsubscribe(EventType.STAFF_TASK_STATUS_CHANGED, record)

    async with async_session_maker() as fresh:
        owner = await fresh.scalar(select(StaffTask.assignee_id).where(StaffTask.id == task.id))
    assert owner in {u.id for u in users}
    assert reported == [owner, owner]
    assert len(changes) == 1
