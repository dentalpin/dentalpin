"""A staff member removed from the clinic can be added back (#1068).

Removing a user deletes the clinic membership and keeps the account, while
creating a user checks the email across all accounts. So the same email
answered 409 forever and the person could only come back through SQL.

Creating a user with the email of an account that has no membership at all
now restores that account into the clinic. The restore is conservative: the
old password and every old token stop working, and an account that still
belongs to any clinic is left alone (409), so no admin can pull another
clinic's staff member into their own clinic by email (#95).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, RefreshToken, User
from app.core.auth.service import (
    create_access_token,
    issue_refresh_token,
    verify_password,
)

OLD_PASSWORD = "OldPassw0rd1234"
NEW_PASSWORD = "NewPassw0rd5678"


def _payload(email: str, **extra) -> dict:
    return {
        "email": email,
        "password": OLD_PASSWORD,
        "first_name": "Anna",
        "last_name": "Kovacs",
        "role": "dentist",
    } | extra


async def _create(client: AsyncClient, headers: dict[str, str], body: dict):
    return await client.post("/api/v1/auth/users", json=body, headers=headers)


async def _user(db: AsyncSession, user_id: str) -> User:
    user = await db.scalar(
        select(User).where(User.id == UUID(user_id)).execution_options(populate_existing=True)
    )
    assert user is not None
    return user


@pytest.mark.asyncio
async def test_removed_member_can_be_added_back(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    email = f"anna-{uuid4().hex[:8]}@example.com"
    first = await _create(client, auth_headers, _payload(email))
    assert first.status_code == 201, first.text
    user_id = first.json()["data"]["id"]

    removed = await client.delete(f"/api/v1/auth/users/{user_id}", headers=auth_headers)
    assert removed.status_code == 204, removed.text

    # Case-insensitive match (#840) still finds the same account.
    again = await _create(
        client,
        auth_headers,
        _payload(email.upper(), role="hygienist", first_name="Anna M.", password=NEW_PASSWORD),
    )
    assert again.status_code == 201, again.text
    assert again.json()["data"]["id"] == user_id  # same account, history stays joined

    listed = await client.get("/api/v1/auth/users", headers=auth_headers)
    rows = {u["id"]: u for u in listed.json()["data"]}
    assert rows[user_id]["role"] == "hygienist"
    assert rows[user_id]["first_name"] == "Anna M."
    assert rows[user_id]["is_active"] is True

    user = await _user(db_session, user_id)
    assert verify_password(NEW_PASSWORD, user.password_hash)
    assert not verify_password(OLD_PASSWORD, user.password_hash)


@pytest.mark.asyncio
async def test_restore_revokes_old_credentials_and_sessions(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    email = f"anna-{uuid4().hex[:8]}@example.com"
    first = await _create(client, auth_headers, _payload(email))
    user_id = first.json()["data"]["id"]
    user = await _user(db_session, user_id)
    old_access = create_access_token(user.id, token_version=user.token_version)
    await issue_refresh_token(db_session, user)
    await db_session.commit()

    await client.delete(f"/api/v1/auth/users/{user_id}", headers=auth_headers)

    # No password: the account gets an unusable one until an invite link is used.
    body = _payload(email)
    del body["password"]
    again = await _create(client, auth_headers, body)
    assert again.status_code == 201, again.text

    user = await _user(db_session, user_id)
    assert not verify_password(OLD_PASSWORD, user.password_hash)

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"})
    assert me.status_code == 401, me.text

    live = await db_session.scalars(
        select(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .execution_options(populate_existing=True)
    )
    assert live.all() == []

    link = await client.post(f"/api/v1/auth/users/{user_id}/invite-link", headers=auth_headers)
    assert link.status_code == 200, link.text


@pytest.mark.asyncio
async def test_current_member_still_conflicts(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
) -> None:
    email = f"anna-{uuid4().hex[:8]}@example.com"
    assert (await _create(client, auth_headers, _payload(email))).status_code == 201
    r = await _create(client, auth_headers, _payload(email))
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_member_of_another_clinic_is_not_taken_over(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    other = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999999",
        address={"street": "Elsewhere", "city": "Bilbao"},
        settings={},
    )
    email = f"other-{uuid4().hex[:8]}@example.com"
    stranger = User(email=email, password_hash="x", first_name="O", last_name="C")
    db_session.add_all([other, stranger])
    await db_session.flush()
    db_session.add(ClinicMembership(user_id=stranger.id, clinic_id=other.id, role="dentist"))
    await db_session.commit()

    r = await _create(client, auth_headers, _payload(email))
    assert r.status_code == 409, r.text

    here = await db_session.scalar(
        select(ClinicMembership.id).where(
            ClinicMembership.user_id == stranger.id,
            ClinicMembership.clinic_id == test_clinic.id,
        )
    )
    assert here is None
    stranger = await _user(db_session, str(stranger.id))
    assert stranger.password_hash == "x"
