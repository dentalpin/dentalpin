"""An invite / reset link sets a password once, even when two requests race.

``/auth/set-password`` is single use: consuming the token bumps
``token_version``. Without a row lock two requests carrying the same token
both read version N, both pass the check, both commit N+1 and both get a
session, the last password written winning. Production hands each request
its own session, so these tests do too.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import User
from app.database import async_session_maker, get_db
from app.main import app


async def _invited(client: AsyncClient, auth_headers: dict) -> tuple[str, str]:
    r = await client.post(
        "/api/v1/auth/users",
        json={
            "email": "race@example.com",
            "first_name": "Rita",
            "last_name": "Race",
            "role": "dentist",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    user_id = r.json()["data"]["id"]
    r = await client.post(f"/api/v1/auth/users/{user_id}/invite-link", headers=auth_headers)
    assert r.status_code == 200, r.text
    return user_id, r.json()["data"]["token"]


async def _own_session_per_request() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


@pytest.mark.asyncio
async def test_two_requests_on_one_link_set_the_password_once(
    client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    _, token = await _invited(client, auth_headers)
    app.dependency_overrides[get_db] = _own_session_per_request

    async def consume(password: str) -> int:
        r = await client.post(
            "/api/v1/auth/set-password", json={"token": token, "password": password}
        )
        return r.status_code

    outcomes = await asyncio.gather(consume("FirstPass123"), consume("SecondPass123"))

    assert sorted(outcomes) == [200, 400]
    winner = "FirstPass123" if outcomes[0] == 200 else "SecondPass123"
    loser = "SecondPass123" if winner == "FirstPass123" else "FirstPass123"
    ok = await client.post(
        "/api/v1/auth/login", data={"username": "race@example.com", "password": winner}
    )
    assert ok.status_code == 200
    refused = await client.post(
        "/api/v1/auth/login", data={"username": "race@example.com", "password": loser}
    )
    assert refused.status_code == 401


@pytest.mark.asyncio
async def test_a_request_waiting_on_the_row_sees_the_link_already_used(
    client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    """The second request must read ``token_version`` under the lock: once the
    first commits the bump, the waiting one re-reads it and refuses."""
    user_id, token = await _invited(client, auth_headers)
    app.dependency_overrides[get_db] = _own_session_per_request

    async with async_session_maker() as holder:
        locked = (
            await holder.execute(select(User).where(User.id == user_id).with_for_update())
        ).scalar_one()

        waiting = asyncio.create_task(
            client.post(
                "/api/v1/auth/set-password", json={"token": token, "password": "LatePassword123"}
            )
        )
        await asyncio.sleep(0.3)
        assert not waiting.done(), "the request should be blocked on the user row"

        locked.token_version += 1  # the first request consumed the link
        await holder.commit()
        r = await waiting

    assert r.status_code == 400, r.text
    refused = await client.post(
        "/api/v1/auth/login", data={"username": "race@example.com", "password": "LatePassword123"}
    )
    assert refused.status_code == 401
