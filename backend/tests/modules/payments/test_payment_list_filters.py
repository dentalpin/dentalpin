"""``GET /payments`` search + multi-method filters run in SQL (#1033).

The list page used to fetch one server page and filter it in the
browser, so a match outside that page vanished while ``total`` still
counted every payment. These tests pin that the filters are applied
before pagination and that ``total`` reflects them.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.patients.models import Patient


async def _seed(db: AsyncSession, auth_headers: dict, client: AsyncClient) -> str:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    clinic = Clinic(
        id=uuid4(),
        name="Filter Clinic",
        tax_id="A28000000",
        timezone="Europe/Madrid",
        currency="EUR",
        settings={},
    )
    db.add(clinic)
    await db.flush()
    db.add(ClinicMembership(id=uuid4(), clinic_id=clinic.id, user_id=user_id, role="admin"))
    ana = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Ana", last_name="García")
    luis = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Luis", last_name="Pérez")
    db.add_all([ana, luis])
    await db.commit()

    clinic_id = str(clinic.id)
    today = date.today()
    # Ana's single payment is the OLDEST, so it never lands on page 1
    # of the default payment_date:desc order.
    rows = [
        (ana.id, "bank_transfer", "50%OFF", 10),
        (luis.id, "cash", "ABC-1", 3),
        (luis.id, "card", "ABC-2", 2),
        (luis.id, "cash", None, 1),
    ]
    for patient_id, method, reference, days_ago in rows:
        body = {
            "patient_id": str(patient_id),
            "amount": "10.00",
            "method": method,
            "payment_date": (today - timedelta(days=days_ago)).isoformat(),
            "allocations": [{"target_type": "on_account", "amount": "10.00"}],
        }
        if reference:
            body["reference"] = reference
        resp = await client.post(
            f"/api/v1/payments?clinic_id={clinic_id}", headers=auth_headers, json=body
        )
        assert resp.status_code == 201, resp.text
    return clinic_id


async def _list(client: AsyncClient, auth_headers: dict, clinic_id: str, query: str) -> dict:
    resp = await client.get(
        f"/api/v1/payments?clinic_id={clinic_id}&page_size=2&{query}", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_search_by_patient_name_filters_before_pagination(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    clinic_id = await _seed(db_session, auth_headers, client)

    body = await _list(client, auth_headers, clinic_id, "search=ana%20garc")
    assert body["total"] == 1
    assert [p["reference"] for p in body["data"]] == ["50%OFF"]

    # Case-insensitive, last name only.
    body = await _list(client, auth_headers, clinic_id, "search=P%C3%89REZ")
    assert body["total"] == 3


@pytest.mark.asyncio
async def test_search_by_reference_escapes_like_wildcards(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    clinic_id = await _seed(db_session, auth_headers, client)

    body = await _list(client, auth_headers, clinic_id, "search=abc-")
    assert body["total"] == 2

    # A literal "%" must not act as a wildcard matching every row.
    body = await _list(client, auth_headers, clinic_id, "search=%25")
    assert body["total"] == 1
    assert body["data"][0]["reference"] == "50%OFF"


@pytest.mark.asyncio
async def test_multi_method_filter_and_single_method_compat(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    clinic_id = await _seed(db_session, auth_headers, client)

    body = await _list(client, auth_headers, clinic_id, "method=bank_transfer&method=card")
    assert body["total"] == 2
    assert {p["method"] for p in body["data"]} == {"bank_transfer", "card"}

    body = await _list(client, auth_headers, clinic_id, "method=cash")
    assert body["total"] == 2
    assert {p["method"] for p in body["data"]} == {"cash"}

    body = await _list(client, auth_headers, clinic_id, "method=cash&search=luis")
    assert body["total"] == 2
