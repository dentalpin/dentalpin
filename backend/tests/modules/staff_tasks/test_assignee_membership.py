"""A task can only be assigned to a member of its clinic.

``assignee_id`` is an FK to ``users`` and was stored as given. An unknown id
was a 500 (ForeignKeyViolation). Another clinic's user was stored, and the
board then showed that person's name in ``assignee_name``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User

BASE = "/api/v1/staff_tasks"


async def _member(db: AsyncSession, clinic_id) -> str:
    user = User(
        email=f"staff-{uuid4().hex[:8]}@test.clinic",
        password_hash="test-hash",
        first_name="Ada",
        last_name="Member",
    )
    db.add(user)
    await db.flush()
    db.add(ClinicMembership(user_id=user.id, clinic_id=clinic_id, role="assistant"))
    await db.commit()
    return str(user.id)


async def _outsider(db: AsyncSession, which: str) -> str:
    if which == "unknown":
        return str(uuid4())
    other = Clinic(id=uuid4(), name="Other", tax_id="B87654321")
    db.add(other)
    await db.flush()
    return await _member(db, other.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("which", ["unknown", "other_clinic"])
async def test_create_rejects_an_assignee_outside_the_clinic(
    client: AsyncClient, auth_headers, db_session: AsyncSession, test_clinic: Clinic, which
) -> None:
    assignee = await _outsider(db_session, which)
    r = await client.post(
        f"{BASE}/", json={"title": "Call back", "assignee_id": assignee}, headers=auth_headers
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
@pytest.mark.parametrize("which", ["unknown", "other_clinic"])
async def test_update_rejects_an_assignee_outside_the_clinic_and_keeps_the_old_one(
    client: AsyncClient, auth_headers, db_session: AsyncSession, test_clinic: Clinic, which
) -> None:
    mine = await _member(db_session, test_clinic.id)
    created = await client.post(
        f"{BASE}/", json={"title": "Call back", "assignee_id": mine}, headers=auth_headers
    )
    assert created.status_code == 201, created.text
    url = f"{BASE}/{created.json()['data']['id']}"

    r = await client.patch(
        url, json={"assignee_id": await _outsider(db_session, which)}, headers=auth_headers
    )
    assert r.status_code == 400, r.text
    assert (await client.get(url, headers=auth_headers)).json()["data"]["assignee_id"] == mine
