"""integrations router: API token CRUD, token-shown-once, hashing,
revocation, permission gate, tenancy."""

import hashlib
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.models import ApiToken

BASE = "/api/v1/integrations/tokens"


@pytest.mark.asyncio
async def test_create_returns_token_once_and_hashed_at_rest(
    client: AsyncClient, auth_headers, db_session: AsyncSession, test_clinic
):
    resp = await client.post(
        BASE,
        json={"name": "Zapier", "scopes": ["patients:read"]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    plaintext = body["token"]
    assert len(plaintext) > 20
    token_id = body["id"]

    # Stored row never carries the plaintext — only its SHA-256 hash.
    row = (await db_session.execute(select(ApiToken).where(ApiToken.id == token_id))).scalar_one()
    assert row.token_hash == hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    assert plaintext not in row.token_hash

    # List must never leak the plaintext, even for the token just created.
    listed = await client.get(BASE, headers=auth_headers)
    assert listed.status_code == 200
    for item in listed.json()["data"]:
        assert "token" not in item
        assert "token_hash" not in item


@pytest.mark.asyncio
async def test_two_tokens_get_distinct_plaintext_and_hash(
    client: AsyncClient, auth_headers, test_clinic
):
    first = await client.post(BASE, json={"name": "A"}, headers=auth_headers)
    second = await client.post(BASE, json={"name": "B"}, headers=auth_headers)
    assert first.json()["data"]["token"] != second.json()["data"]["token"]


@pytest.mark.asyncio
async def test_revoke_roundtrip(client: AsyncClient, auth_headers, test_clinic):
    created = await client.post(BASE, json={"name": "Make"}, headers=auth_headers)
    token_id = created.json()["data"]["id"]
    assert created.json()["data"]["revoked_at"] is None

    revoked = await client.post(f"{BASE}/{token_id}/revoke", headers=auth_headers)
    assert revoked.status_code == 200
    assert revoked.json()["data"]["revoked_at"] is not None

    # Revoking an already-revoked token is rejected, not silently repeated.
    again = await client.post(f"{BASE}/{token_id}/revoke", headers=auth_headers)
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_revoke_missing_token_404s(client: AsyncClient, auth_headers, test_clinic):
    resp = await client.post(f"{BASE}/{uuid4()}/revoke", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_non_admin_role_forbidden(
    client: AsyncClient, auth_headers, db_session: AsyncSession, test_clinic
):
    from app.core.auth.models import ClinicMembership, User
    from app.core.auth.service import create_access_token, hash_password

    receptionist = User(
        email="reception-tokens@example.com",
        password_hash=hash_password("TestPass1234"),
        first_name="Recep",
        last_name="Tionist",
    )
    db_session.add(receptionist)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(),
            user_id=receptionist.id,
            clinic_id=test_clinic.id,
            role="receptionist",
        )
    )
    await db_session.commit()

    token = create_access_token(receptionist.id, token_version=receptionist.token_version)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(BASE, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cross_clinic_token_not_visible(
    client: AsyncClient, auth_headers, db_session: AsyncSession, test_clinic
):
    from app.core.auth.models import Clinic

    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B87654322",
        address={"street": "Other St", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other_clinic)
    await db_session.commit()

    other_token = ApiToken(
        clinic_id=other_clinic.id,
        name="Other clinic's token",
        token_hash=hashlib.sha256(b"unrelated").hexdigest(),
        scopes=[],
    )
    db_session.add(other_token)
    await db_session.commit()

    resp = await client.post(f"{BASE}/{other_token.id}/revoke", headers=auth_headers)
    assert resp.status_code == 404
