"""leads: staff CRUD, conversion, tenancy and permission dependencies."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.leads.models import Lead
from app.modules.patients.models import Patient

from .conftest import STAFF_ROLE, make_headers, role_grants

BASE = "/api/v1/leads/"

#: An enquiry that matches nobody (the patient phones used in the shared
#: fixtures are 666123456 / 600000001).
UNMATCHED = {
    "full_name": "Marta Ruiz",
    "phone": "+34 699 888 777",
    "email": "marta@example.com",
    "motive": "Presupuesto de ortodoncia",
    "description": "Viene de Instagram.",
    "availability_days": ["tue", "thu"],
    "availability_slot": "afternoon",
}

PATIENT_BODY = {
    "first_name": "Marta",
    "last_name": "Ruiz",
    "phone": "+34 699 888 777",
    "email": "marta@example.com",
    "date_of_birth": "1990-04-02",
    "national_id": "12345678A",
    "notes": "Motivo: Presupuesto de ortodoncia",
}


async def _create_lead(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {**UNMATCHED, **overrides}
    response = await client.post(BASE, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["outcome"] == "lead_created", body
    return body["lead"]


@pytest.mark.asyncio
async def test_create_list_patch_get_roundtrip(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    lead = await _create_lead(client, auth_headers)
    assert lead["status"] == "new"
    assert lead["patient_id"] is None
    assert lead["converted_at"] is None
    # Stored as typed, trimmed.
    assert lead["phone"] == "+34 699 888 777"
    # Availability is structured and canonicalised (mon..sun, no duplicates),
    # whatever order the caller sent.
    assert lead["availability_days"] == ["tue", "thu"]
    assert lead["availability_slot"] == "afternoon"

    listed = await client.get(BASE, headers=auth_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["data"]] == [lead["id"]]
    assert listed.json()["total"] == 1

    patched = await client.patch(
        f"{BASE}{lead['id']}", json={"status": "contacted"}, headers=auth_headers
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["status"] == "contacted"

    detail = await client.get(f"{BASE}{lead['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "contacted"


@pytest.mark.asyncio
async def test_unknown_lead_is_404(client: AsyncClient, auth_headers: dict, test_clinic: Clinic):
    missing = uuid4()
    assert (await client.get(f"{BASE}{missing}", headers=auth_headers)).status_code == 404
    assert (
        await client.patch(f"{BASE}{missing}", json={"status": "new"}, headers=auth_headers)
    ).status_code == 404


@pytest.mark.asyncio
async def test_cross_clinic_lead_is_invisible(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    other_clinic: Clinic,
):
    """The other clinic gets 404 — not an empty list, not a 403."""
    lead = await _create_lead(client, auth_headers)
    other_headers = await make_headers(db_session, other_clinic.id, role="admin")

    assert (await client.get(f"{BASE}{lead['id']}", headers=other_headers)).status_code == 404
    assert (
        await client.patch(
            f"{BASE}{lead['id']}", json={"status": "discarded"}, headers=other_headers
        )
    ).status_code == 404
    assert (
        await client.post(f"{BASE}{lead['id']}/convert", json=PATIENT_BODY, headers=other_headers)
    ).status_code == 404

    listed = await client.get(BASE, headers=other_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 0


@pytest.mark.asyncio
async def test_convert_creates_patient_and_converts_lead(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic: Clinic
):
    lead = await _create_lead(client, auth_headers)

    response = await client.post(
        f"{BASE}{lead['id']}/convert", json=PATIENT_BODY, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]

    assert data["patient"]["first_name"] == "Marta"
    assert data["patient"]["last_name"] == "Ruiz"
    assert data["lead"]["status"] == "converted"
    assert data["lead"]["patient_id"] == data["patient"]["id"]
    assert data["lead"]["converted_at"] is not None

    patient = (
        await db_session.execute(
            select(Patient).where(
                Patient.id == data["patient"]["id"], Patient.clinic_id == test_clinic.id
            )
        )
    ).scalar_one()
    assert patient.date_of_birth == date(1990, 4, 2)
    assert patient.national_id == "12345678A"

    # Converting twice is a 409, not a second patient.
    again = await client.post(
        f"{BASE}{lead['id']}/convert", json=PATIENT_BODY, headers=auth_headers
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_convert_requires_patients_write(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
    test_clinic: Clinic,
):
    """leads.write alone cannot create a patient record."""
    lead = await _create_lead(client, auth_headers)
    headers = await make_headers(db_session, test_clinic.id, role=STAFF_ROLE)

    # The receptionist's leads permissions are untouched: the 403 below
    # is the patients.write dependency, not a blanket denial.
    with role_grants(STAFF_ROLE, ["read"]):
        assert (
            await client.patch(f"{BASE}{lead['id']}", json={"status": "contacted"}, headers=headers)
        ).status_code == 200
        denied = await client.post(
            f"{BASE}{lead['id']}/convert", json=PATIENT_BODY, headers=headers
        )
    assert denied.status_code == 403, denied.text


@pytest.mark.asyncio
async def test_patch_with_empty_body_keeps_fields(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    lead = await _create_lead(client, auth_headers)
    response = await client.patch(f"{BASE}{lead['id']}", json={}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["full_name"] == lead["full_name"]
    assert data["phone"] == lead["phone"]
    assert data["status"] == "new"


@pytest.mark.asyncio
async def test_status_filter_and_search(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    keep = await _create_lead(client, auth_headers, full_name="Ana Lopez", phone="699111111")
    contacted = await _create_lead(
        client, auth_headers, full_name="Bruno Diaz", phone="699222222", email="bruno@example.com"
    )
    discarded = await _create_lead(client, auth_headers, full_name="Carla Gil", phone="699333333")
    for lead, status_value in ((contacted, "contacted"), (discarded, "discarded")):
        patched = await client.patch(
            f"{BASE}{lead['id']}", json={"status": status_value}, headers=auth_headers
        )
        assert patched.status_code == 200

    # No status param: every status, discarded included.
    everything = await client.get(BASE, headers=auth_headers)
    assert everything.json()["total"] == 3

    only_new = await client.get(f"{BASE}?status=new", headers=auth_headers)
    assert {item["id"] for item in only_new.json()["data"]} == {keep["id"]}

    multi = await client.get(f"{BASE}?status=new,discarded", headers=auth_headers)
    assert {item["id"] for item in multi.json()["data"]} == {keep["id"], discarded["id"]}

    bogus = await client.get(f"{BASE}?status=nonsense", headers=auth_headers)
    assert bogus.status_code == 422

    by_phone = await client.get(f"{BASE}?search=699111", headers=auth_headers)
    assert [item["id"] for item in by_phone.json()["data"]] == [keep["id"]]

    by_name = await client.get(f"{BASE}?search=ana lopez", headers=auth_headers)
    assert [item["id"] for item in by_name.json()["data"]] == [keep["id"]]


@pytest.mark.asyncio
async def test_clinic_scoped_rows_only(
    db_session: AsyncSession, test_clinic: Clinic, other_clinic: Clinic
):
    """Belt and braces on the service layer: a foreign row is never read."""
    db_session.add(
        Lead(
            clinic_id=other_clinic.id,
            full_name="Foreign",
            phone="600999999",
            motive="x",
        )
    )
    await db_session.flush()

    from app.modules.leads.service import LeadService

    items, total = await LeadService.list_leads(db_session, test_clinic.id)
    assert items == [] and total == 0
