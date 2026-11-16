"""staff_tasks: service CRUD, status transitions and tenant isolation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.modules.staff_tasks.schemas import StaffTaskCreate, StaffTaskUpdate
from app.modules.staff_tasks.service import StaffTaskService


async def _make_user(db_session: AsyncSession, email: str) -> User:
    """Real user row — assignee_id/created_by carry an FK to users.id, so
    actor ids can't be fabricated."""
    user = User(
        email=email,
        password_hash="test-hash",
        first_name="Test",
        last_name="Staff",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_create_claim_done_lifecycle(db_session: AsyncSession, test_clinic: Clinic):
    actor = await _make_user(db_session, "actor@staff-tasks.test")
    task = await StaffTaskService.create_task(
        db_session,
        test_clinic.id,
        StaffTaskCreate(title="Call patient about quote", priority="high"),
        created_by=None,
    )
    assert task.status == "open"
    assert task.assignee_id is None

    claimed = await StaffTaskService.update_task(
        db_session,
        test_clinic.id,
        task.id,
        StaffTaskUpdate(status="claimed"),
        actor_id=actor.id,
    )
    # Claiming an unassigned task assigns the claimer.
    assert claimed.status == "claimed"
    assert claimed.assignee_id == actor.id

    done = await StaffTaskService.update_task(
        db_session,
        test_clinic.id,
        task.id,
        StaffTaskUpdate(status="done"),
        actor_id=actor.id,
    )
    assert done.status == "done"
    assert done.completed_at is not None

    # done is terminal — no further transitions allowed.
    with pytest.raises(HTTPException) as exc_info:
        await StaffTaskService.update_task(
            db_session,
            test_clinic.id,
            task.id,
            StaffTaskUpdate(status="open"),
            actor_id=actor.id,
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_unclaim_clears_assignee(db_session: AsyncSession, test_clinic: Clinic):
    actor = await _make_user(db_session, "unclaim@staff-tasks.test")
    task = await StaffTaskService.create_task(
        db_session, test_clinic.id, StaffTaskCreate(title="Restock gloves"), created_by=None
    )
    claimed = await StaffTaskService.update_task(
        db_session, test_clinic.id, task.id, StaffTaskUpdate(status="claimed"), actor_id=actor.id
    )
    # assignee_name resolves through the eager-loaded relationship.
    assert claimed.assignee_name == "Test Staff"

    reopened = await StaffTaskService.update_task(
        db_session, test_clinic.id, task.id, StaffTaskUpdate(status="open"), actor_id=actor.id
    )
    # Re-opening puts the task back up for grabs.
    assert reopened.assignee_id is None
    assert reopened.assignee_name is None


@pytest.mark.asyncio
async def test_status_filter_isolation_and_delete(db_session: AsyncSession, test_clinic: Clinic):
    assignee = await _make_user(db_session, "assignee@staff-tasks.test")
    db_session.add(
        ClinicMembership(user_id=assignee.id, clinic_id=test_clinic.id, role="assistant")
    )
    await db_session.commit()
    open_task = await StaffTaskService.create_task(
        db_session,
        test_clinic.id,
        StaffTaskCreate(title="Prepare implant kit", assignee_id=assignee.id),
        created_by=None,
    )
    done_task = await StaffTaskService.create_task(
        db_session,
        test_clinic.id,
        StaffTaskCreate(title="Old chore"),
        created_by=None,
    )
    await StaffTaskService.update_task(
        db_session,
        test_clinic.id,
        done_task.id,
        StaffTaskUpdate(status="cancelled"),
        actor_id=None,
    )

    open_rows, open_total = await StaffTaskService.list_tasks(
        db_session, test_clinic.id, task_status="open"
    )
    assert open_total == 1
    assert open_rows[0].id == open_task.id

    cancelled_rows, cancelled_total = await StaffTaskService.list_tasks(
        db_session, test_clinic.id, task_status="cancelled"
    )
    assert cancelled_total == 1
    assert cancelled_rows[0].id == done_task.id

    await StaffTaskService.delete_task(db_session, test_clinic.id, open_task.id)
    with pytest.raises(HTTPException) as exc_info:
        await StaffTaskService.get_task(db_session, test_clinic.id, open_task.id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_tasks_are_clinic_scoped(db_session: AsyncSession, test_clinic: Clinic):
    other_clinic = Clinic(
        id=uuid4(), name="Other Clinic", tax_id="B99999999", address={}, settings={}
    )
    db_session.add(other_clinic)
    await db_session.commit()

    other_task = await StaffTaskService.create_task(
        db_session,
        other_clinic.id,
        StaffTaskCreate(title="Other clinic handoff"),
        created_by=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await StaffTaskService.get_task(db_session, test_clinic.id, other_task.id)
    assert exc_info.value.status_code == 404

    rows, total = await StaffTaskService.list_tasks(db_session, test_clinic.id)
    assert total == 0
    assert other_task.id not in [r.id for r in rows]

    with pytest.raises(HTTPException) as exc_info:
        await StaffTaskService.delete_task(db_session, test_clinic.id, other_task.id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_status_filter_and_transitions_over_http(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    """HTTP-level coverage for list filters and transition guards."""
    created = await client.post(
        "/api/v1/staff_tasks/",
        json={"title": "HTTP handoff", "priority": "high"},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    task = created.json()["data"]
    assert task["status"] == "open"

    # Filter finds it.
    listed = await client.get(
        "/api/v1/staff_tasks/", params={"task_status": "open"}, headers=auth_headers
    )
    assert listed.status_code == 200
    assert any(t["id"] == task["id"] for t in listed.json()["data"])

    # Claim over PATCH.
    patched = await client.patch(
        f"/api/v1/staff_tasks/{task['id']}",
        json={"status": "claimed"},
        headers=auth_headers,
    )
    assert patched.status_code == 200
    body = patched.json()["data"]
    assert body["status"] == "claimed"
    assert body["assignee_id"] is not None

    # done → open is not a legal transition (done is terminal).
    closed = await client.patch(
        f"/api/v1/staff_tasks/{task['id']}",
        json={"status": "done"},
        headers=auth_headers,
    )
    assert closed.status_code == 200

    illegal = await client.patch(
        f"/api/v1/staff_tasks/{task['id']}",
        json={"status": "open"},
        headers=auth_headers,
    )
    assert illegal.status_code == 422

    # Status filtering narrows: the done-filter now returns exactly the
    # task this test drove through claimed -> done.
    done_list = await client.get(
        "/api/v1/staff_tasks/", params={"task_status": "done"}, headers=auth_headers
    )
    assert [t["id"] for t in done_list.json()["data"]] == [task["id"]]
