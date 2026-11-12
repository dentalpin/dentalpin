"""A clinic always keeps at least one active admin.

An admin can't target themselves (self-deactivation, self-removal and
self-demotion are refused), so the guard matters for a custom role that holds
`admin.users.write` without being admin (#556, #842). Demotion was guarded; turning
the last admin off and removing them from the clinic were not, and the demotion
count included admins who can no longer log in.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.rbac import invalidate_rbac_cache
from app.core.auth.seed_rbac import seed_rbac
from app.core.auth.service import create_access_token, hash_password


@pytest_asyncio.fixture
async def manager_headers(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> AsyncGenerator[dict[str, str], None]:
    """A user whose custom role grants `admin.users.write` and nothing admin."""
    settings.RBAC_FROM_DB = True
    try:
        invalidate_rbac_cache()
        await seed_rbac(db_session)
        role = await client.post(
            "/api/v1/roles",
            json={"name": "usermanager", "permissions": ["admin.users.write"]},
            headers=auth_headers,
        )
        assert role.status_code == 201, role.text
        created = await client.post(
            "/api/v1/auth/users",
            json={
                "email": "manager@test.clinic",
                "password": "Str0ngPassw0rd!!",
                "first_name": "M",
                "last_name": "G",
                "role": "usermanager",
            },
            headers=auth_headers,
        )
        assert created.status_code == 201, created.text
        manager = await db_session.scalar(select(User).where(User.email == "manager@test.clinic"))
        assert manager is not None
        token = create_access_token(manager.id, token_version=manager.token_version)
        yield {"Authorization": f"Bearer {token}"}
    finally:
        settings.RBAC_FROM_DB = False
        invalidate_rbac_cache()


async def _admin_id(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    return me.json()["data"]["user"]["id"]


async def _second_admin(db: AsyncSession, clinic: Clinic, *, active: bool) -> User:
    user = User(
        email=f"admin-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("Str0ngPassw0rd!!"),
        first_name="Second",
        last_name="Admin",
        is_active=active,
    )
    db.add(user)
    await db.flush()
    db.add(ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic.id, role="admin"))
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_the_last_admin_cannot_be_deactivated(
    client: AsyncClient, auth_headers: dict[str, str], manager_headers: dict[str, str]
) -> None:
    admin_id = await _admin_id(client, auth_headers)

    r = await client.put(
        f"/api/v1/auth/users/{admin_id}", json={"is_active": False}, headers=manager_headers
    )
    assert r.status_code == 400, r.text
    assert "last admin" in r.text


@pytest.mark.asyncio
async def test_the_last_admin_cannot_be_removed_from_the_clinic(
    client: AsyncClient, auth_headers: dict[str, str], manager_headers: dict[str, str]
) -> None:
    admin_id = await _admin_id(client, auth_headers)

    r = await client.delete(f"/api/v1/auth/users/{admin_id}", headers=manager_headers)
    assert r.status_code == 400, r.text
    assert "last admin" in r.text


@pytest.mark.asyncio
async def test_an_inactive_admin_does_not_count_as_remaining(
    client: AsyncClient,
    auth_headers: dict[str, str],
    manager_headers: dict[str, str],
    db_session: AsyncSession,
    test_clinic: Clinic,
) -> None:
    await _second_admin(db_session, test_clinic, active=False)
    admin_id = await _admin_id(client, auth_headers)

    for request in (
        client.put(
            f"/api/v1/auth/users/{admin_id}", json={"role": "receptionist"}, headers=manager_headers
        ),
        client.put(
            f"/api/v1/auth/users/{admin_id}", json={"is_active": False}, headers=manager_headers
        ),
        client.delete(f"/api/v1/auth/users/{admin_id}", headers=manager_headers),
    ):
        r = await request
        assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_an_admin_can_go_while_another_active_admin_remains(
    client: AsyncClient,
    auth_headers: dict[str, str],
    manager_headers: dict[str, str],
    db_session: AsyncSession,
    test_clinic: Clinic,
) -> None:
    await _second_admin(db_session, test_clinic, active=True)
    admin_id = await _admin_id(client, auth_headers)

    r = await client.put(
        f"/api/v1/auth/users/{admin_id}", json={"is_active": False}, headers=manager_headers
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_reactivating_an_admin_is_not_blocked(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_clinic: Clinic,
) -> None:
    inactive = await _second_admin(db_session, test_clinic, active=False)

    r = await client.put(
        f"/api/v1/auth/users/{inactive.id}", json={"is_active": True}, headers=auth_headers
    )
    assert r.status_code == 200, r.text
