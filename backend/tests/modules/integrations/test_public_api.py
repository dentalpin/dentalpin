"""Public data-read API: token auth, scope enforcement, rate-limit headers,
patient list/get — issue #65 §2, §11."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

TOKENS_BASE = "/api/v1/integrations/tokens"
PUBLIC_BASE = "/api/v1/integrations/public"


async def _create_token(client: AsyncClient, auth_headers: dict, scopes: list[str]) -> str:
    """Return plaintext token."""
    resp = await client.post(
        TOKENS_BASE,
        json={"name": "test-public", "scopes": scopes},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["token"]


async def _create_patient(
    client: AsyncClient, auth_headers: dict, first_name: str = "Ana", last_name: str = "López"
) -> dict:
    resp = await client.post(
        "/api/v1/patients",
        json={"first_name": first_name, "last_name": last_name, "phone": "+34600000001"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


@pytest.mark.asyncio
async def test_list_patients_returns_paginated_results(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    token = await _create_token(client, auth_headers, ["patients:read"])
    await _create_patient(client, auth_headers)

    resp = await client.get(
        f"{PUBLIC_BASE}/patients",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert len(body["data"]) >= 1
    p = body["data"][0]
    assert "id" in p
    assert "first_name" in p
    assert "last_name" in p
    assert "billing_name" not in p
    assert "notes" not in p


@pytest.mark.asyncio
async def test_list_patients_search_filters_by_name(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    token = await _create_token(client, auth_headers, ["patients:read"])
    await _create_patient(client, auth_headers, first_name="Beatriz", last_name="García")
    await _create_patient(client, auth_headers, first_name="Carlos", last_name="Ruiz")

    resp = await client.get(
        f"{PUBLIC_BASE}/patients",
        params={"search": "Beatriz"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    names = [p["first_name"] for p in resp.json()["data"]]
    assert "Beatriz" in names
    assert "Carlos" not in names


@pytest.mark.asyncio
async def test_get_patient_by_id(client: AsyncClient, auth_headers: dict, test_clinic):
    token = await _create_token(client, auth_headers, ["patients:read"])
    patient = await _create_patient(client, auth_headers)

    resp = await client.get(
        f"{PUBLIC_BASE}/patients/{patient['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == patient["id"]


@pytest.mark.asyncio
async def test_get_patient_unknown_id_returns_404(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    token = await _create_token(client, auth_headers, ["patients:read"])
    resp = await client.get(
        f"{PUBLIC_BASE}/patients/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rate_limit_headers_present(client: AsyncClient, auth_headers: dict, test_clinic):
    token = await _create_token(client, auth_headers, ["patients:read"])
    resp = await client.get(
        f"{PUBLIC_BASE}/patients",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "x-ratelimit-limit-minute" in resp.headers
    assert "x-ratelimit-remaining-minute" in resp.headers
    assert "x-ratelimit-limit-day" in resp.headers
    assert "x-ratelimit-remaining-day" in resp.headers


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429(
    client: AsyncClient, auth_headers: dict, test_clinic, monkeypatch
):
    from app.modules.integrations import service as integrations_service

    token = await _create_token(client, auth_headers, ["patients:read"])
    monkeypatch.setattr(integrations_service, "RATE_LIMIT_PER_MINUTE", 2)
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.get(f"{PUBLIC_BASE}/ping", headers=headers)
    second = await client.get(f"{PUBLIC_BASE}/ping", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200

    third = await client.get(f"{PUBLIC_BASE}/ping", headers=headers)
    assert third.status_code == 429
    assert third.json()["detail"] == "Rate limit exceeded for this API token."
    assert "Retry-After" in third.headers


@pytest.mark.asyncio
async def test_no_token_returns_401(client: AsyncClient, auth_headers: dict, test_clinic):
    resp = await client.get(f"{PUBLIC_BASE}/patients")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client: AsyncClient, auth_headers: dict, test_clinic):
    resp = await client.get(
        f"{PUBLIC_BASE}/patients",
        headers={"Authorization": "Bearer dp_thisisnotavalidtoken1234567890"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_non_dp_prefix_returns_401(client: AsyncClient, auth_headers: dict, test_clinic):
    resp = await client.get(
        f"{PUBLIC_BASE}/patients",
        headers={"Authorization": "Bearer sk_some_other_token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_revoked_token_returns_401(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic
):
    token = await _create_token(client, auth_headers, ["patients:read"])

    listed = await client.get(TOKENS_BASE, headers=auth_headers)
    token_id = listed.json()["data"][0]["id"]

    await client.post(f"{TOKENS_BASE}/{token_id}/revoke", headers=auth_headers)

    resp = await client.get(
        f"{PUBLIC_BASE}/patients",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_without_patients_read_scope_returns_403(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    token = await _create_token(client, auth_headers, [])

    resp = await client.get(
        f"{PUBLIC_BASE}/patients",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cross_clinic_isolation(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic
):
    """A token from clinic A must not see patients from clinic B."""
    from app.core.auth.models import Clinic, ClinicMembership, User
    from app.core.auth.service import create_access_token, hash_password

    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999991",
        address={"street": "Calle Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other_clinic)
    await db_session.flush()

    other_user = User(
        email=f"admin-other-{uuid4().hex[:6]}@example.com",
        password_hash=hash_password("TestPass1234"),
        first_name="Other",
        last_name="Admin",
    )
    db_session.add(other_user)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(),
            user_id=other_user.id,
            clinic_id=other_clinic.id,
            role="admin",
        )
    )
    await db_session.commit()

    other_jwt = create_access_token(other_user.id, token_version=other_user.token_version)
    other_headers = {"Authorization": f"Bearer {other_jwt}"}

    other_token = await _create_token(client, other_headers, ["patients:read"])
    await _create_patient(client, other_headers)

    await _create_patient(client, auth_headers, first_name="Clinic A patient")

    resp = await client.get(
        f"{PUBLIC_BASE}/patients",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 200
    names = [p["first_name"] for p in resp.json()["data"]]
    assert "Clinic A patient" not in names


# --------------------------------------------------------------- #65 deltas
# /ping introspection, last_used_at stamping, structured find params
# (ported from PR #348).


@pytest.mark.asyncio
async def test_ping_introspects_token(client: AsyncClient, auth_headers: dict, test_clinic):
    token = await _create_token(client, auth_headers, ["patients:read"])

    resp = await client.get(f"{PUBLIC_BASE}/ping", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["clinic_id"] == str(test_clinic.id)
    assert body["token_name"] == "test-public"
    assert body["scopes"] == ["patients:read"]
    assert "X-RateLimit-Remaining-Minute" in resp.headers

    resp = await client.get(f"{PUBLIC_BASE}/ping")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_public_call_stamps_last_used_at(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    token = await _create_token(client, auth_headers, ["patients:read"])

    listed = (await client.get(TOKENS_BASE, headers=auth_headers)).json()["data"]
    assert listed[0]["last_used_at"] is None

    resp = await client.get(f"{PUBLIC_BASE}/ping", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    listed = (await client.get(TOKENS_BASE, headers=auth_headers)).json()["data"]
    assert listed[0]["last_used_at"] is not None


@pytest.mark.asyncio
async def test_structured_find_is_format_tolerant(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    token = await _create_token(client, auth_headers, ["patients:read"])
    resp = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Marta",
            "last_name": "Buscable",
            "phone": "+34 600-99-88-77",
            "email": "Marta.Buscable@Example.com",
            "national_id": "12345678z",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    await _create_patient(client, auth_headers, first_name="Otro", last_name="Paciente")

    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        f"{PUBLIC_BASE}/patients", params={"phone": "+34600998877"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1
    assert resp.json()["data"][0]["first_name"] == "Marta"

    resp = await client.get(
        f"{PUBLIC_BASE}/patients",
        params={"email": "  marta.buscable@example.COM "},
        headers=headers,
    )
    assert resp.json()["total"] == 1

    resp = await client.get(
        f"{PUBLIC_BASE}/patients", params={"national_id": "12345678Z"}, headers=headers
    )
    assert resp.json()["total"] == 1

    resp = await client.get(
        f"{PUBLIC_BASE}/patients", params={"phone": "+34999999999"}, headers=headers
    )
    assert resp.json()["total"] == 0
