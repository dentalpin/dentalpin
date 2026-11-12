"""A staff email address is matched without regard to case.

The local part of an address is case-insensitive at every mail provider a
clinic uses, and `EmailStr` only lowercases the domain. So login, the
uniqueness checks and the stored value all compare a lowercased address.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.schemas import SystemSetup, UserCreate, UserUpdate
from app.core.auth.service import hash_password

PASSWORD = "TestPass1234"


async def _staff(db: AsyncSession, clinic: Clinic, email: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        first_name="Anna",
        last_name="Kovacs",
    )
    db.add(user)
    await db.flush()
    db.add(ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic.id, role="dentist"))
    await db.commit()
    return user


async def _login(client: AsyncClient, email: str):
    return await client.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD})


def _new_user(email: str) -> dict:
    return {
        "email": email,
        "password": PASSWORD,
        "first_name": "New",
        "last_name": "Staff",
        "role": "receptionist",
    }


def test_schemas_lowercase_the_address() -> None:
    assert UserCreate(**_new_user("Anna.Kovacs@Clinic.HU")).email == "anna.kovacs@clinic.hu"
    assert UserUpdate(email=" Anna.Kovacs@clinic.hu ").email == "anna.kovacs@clinic.hu"
    assert UserUpdate().email is None
    setup = SystemSetup(
        admin_first_name="Admin",
        admin_last_name="User",
        admin_email="Admin@Clinic.HU",
        admin_password=PASSWORD,
        clinic_name="Clinic",
        clinic_tax_id="B12345678",
    )
    assert setup.admin_email == "admin@clinic.hu"


@pytest.mark.asyncio
async def test_login_ignores_the_case_of_the_address(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
) -> None:
    await _staff(db_session, test_clinic, "anna.kovacs@example.com")

    for typed in ("anna.kovacs@example.com", "Anna.Kovacs@example.com", "ANNA.KOVACS@EXAMPLE.COM"):
        r = await _login(client, typed)
        assert r.status_code == 200, (typed, r.text)


@pytest.mark.asyncio
async def test_login_finds_a_row_stored_in_mixed_case(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
) -> None:
    # Rows written before addresses were lowercased keep their case.
    await _staff(db_session, test_clinic, "Mixed.Case@example.com")

    r = await _login(client, "mixed.case@example.com")
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_created_user_is_stored_lowercase(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_clinic: Clinic,
) -> None:
    r = await client.post(
        "/api/v1/auth/users", json=_new_user("New.Staff@Example.com"), headers=auth_headers
    )
    assert r.status_code == 201, r.text

    stored = await db_session.scalar(select(User.email).where(User.id == r.json()["data"]["id"]))
    assert stored == "new.staff@example.com"
    assert (await _login(client, "New.Staff@example.com")).status_code == 200


@pytest.mark.asyncio
async def test_a_recased_address_is_already_registered(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_clinic: Clinic,
) -> None:
    await _staff(db_session, test_clinic, "Anna.Kovacs@example.com")

    r = await client.post(
        "/api/v1/auth/users", json=_new_user("anna.kovacs@example.com"), headers=auth_headers
    )
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_changing_to_a_recased_address_of_another_user_conflicts(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_clinic: Clinic,
) -> None:
    await _staff(db_session, test_clinic, "anna.kovacs@example.com")
    other = await _staff(db_session, test_clinic, "bela.nagy@example.com")

    r = await client.put(
        f"/api/v1/auth/users/{other.id}",
        json={"email": "Anna.Kovacs@example.com"},
        headers=auth_headers,
    )
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_lowercasing_your_own_mixed_case_address_is_allowed(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_clinic: Clinic,
) -> None:
    user = await _staff(db_session, test_clinic, "Mixed.Case@example.com")

    r = await client.put(
        f"/api/v1/auth/users/{user.id}",
        json={"email": "mixed.case@example.com"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["email"] == "mixed.case@example.com"


@pytest.mark.asyncio
async def test_login_prefers_the_exact_spelling_when_two_rows_differ_by_case(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
) -> None:
    # Two legacy accounts the old case-sensitive check let through.
    older = await _staff(db_session, test_clinic, "twin@example.com")
    newer = await _staff(db_session, test_clinic, "Twin@example.com")

    me = await client.get(
        "/api/v1/auth/me", cookies=(await _login(client, "Twin@example.com")).cookies
    )
    assert me.json()["data"]["user"]["id"] == str(newer.id)

    me = await client.get(
        "/api/v1/auth/me", cookies=(await _login(client, "TWIN@example.com")).cookies
    )
    assert me.json()["data"]["user"]["id"] == str(older.id)
