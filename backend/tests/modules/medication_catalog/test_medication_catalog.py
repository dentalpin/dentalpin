"""medication_catalog: CRUD, duplicate-name 409s, filters, isolation — over HTTP."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.medication_catalog.models import MedicationCatalogItem
from app.modules.medication_catalog.seed import DENTAL_MEDICATIONS


async def _create(client: AsyncClient, headers: dict, **payload) -> dict:
    res = await client.post("/api/v1/medication_catalog/", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["data"]


@pytest.mark.asyncio
async def test_crud_over_http(client: AsyncClient, auth_headers: dict, test_clinic: Clinic):
    item = await _create(
        client,
        auth_headers,
        name="Amoxicillin",
        dose="500",
        unit="mg",
        form="capsule",
        requires_prescription=True,
    )
    assert item["form"] == "capsule"
    assert item["requires_prescription"] is True

    res = await client.get(f"/api/v1/medication_catalog/{item['id']}", headers=auth_headers)
    assert res.status_code == 200

    # Rename to a case variant of itself is allowed.
    res = await client.patch(
        f"/api/v1/medication_catalog/{item['id']}",
        json={"name": "amoxicillin", "is_active": False},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["name"] == "amoxicillin"
    assert res.json()["data"]["is_active"] is False

    res = await client.delete(f"/api/v1/medication_catalog/{item['id']}", headers=auth_headers)
    assert res.status_code == 204

    res = await client.get(f"/api/v1/medication_catalog/{item['id']}", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_name_case_insensitive_409(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    """Same guarantee as medical_reference renames: 'Amoxicillin' and
    'amoxicillin' cannot coexist; the second create gets a 409 (not a
    raw unique-constraint 500), and renaming another row onto an
    existing name is rejected too."""
    await _create(client, auth_headers, name="Ibuprofen", dose="400", unit="mg")

    res = await client.post(
        "/api/v1/medication_catalog/", json={"name": "ibuprofen"}, headers=auth_headers
    )
    assert res.status_code == 409, res.text

    other = await _create(client, auth_headers, name="Naproxen")
    res = await client.patch(
        f"/api/v1/medication_catalog/{other['id']}",
        json={"name": "IBUPROFEN"},
        headers=auth_headers,
    )
    assert res.status_code == 409, res.text


@pytest.mark.asyncio
async def test_duplicate_with_inner_whitespace_is_409_not_500(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    """The service's name normalisation must match the index key
    (``lower(btrim(name))``) exactly. Collapsing inner whitespace made the
    409 lookup looser than the index, so a repeated double-spaced name
    slipped through and blew up as a raw IntegrityError."""
    payload = {"name": "Ibuprofen  400 mg", "form": "tablet"}
    res = await client.post("/api/v1/medication_catalog/", json=payload, headers=auth_headers)
    assert res.status_code == 201, res.text

    res = await client.post("/api/v1/medication_catalog/", json=payload, headers=auth_headers)
    assert res.status_code == 409, res.text


@pytest.mark.asyncio
async def test_search_filter_and_pagination_over_http(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    for name in ("Amoxicillin", "Ampicillin", "Ibuprofen"):
        await _create(client, auth_headers, name=name)

    async def _list(**params) -> tuple[list[str], int]:
        res = await client.get("/api/v1/medication_catalog/", params=params, headers=auth_headers)
        assert res.status_code == 200, res.text
        body = res.json()
        return [m["name"] for m in body["data"]], body["total"]

    names, total = await _list(q="Am")
    assert sorted(names) == ["Amoxicillin", "Ampicillin"]
    assert total == 2

    names, _ = await _list(page=1, page_size=2)
    assert len(names) == 2  # alphabetical first page of three items


@pytest.mark.asyncio
async def test_items_are_clinic_scoped(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_clinic: Clinic
):
    other = Clinic(id=uuid4(), name="Other Clinic", tax_id="B44444444", address={}, settings={})
    db_session.add(other)
    await db_session.commit()

    db_session.add(
        MedicationCatalogItem(clinic_id=other.id, name="Secret medication", form="tablet")
    )
    await db_session.commit()

    res = await client.get("/api/v1/medication_catalog/", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert all(m["name"] != "Secret medication" for m in body["data"])

    # Direct id access from the other clinic must 404 as well.
    other_item = (
        (
            await db_session.execute(
                select(MedicationCatalogItem).where(MedicationCatalogItem.clinic_id == other.id)
            )
        )
        .scalars()
        .one()
    )
    res = await client.get(f"/api/v1/medication_catalog/{other_item.id}", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_same_name_allowed_across_clinics(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
):
    """Regression: mc_0001 originally indexed lower(btrim(name)) WITHOUT
    clinic_id, making names unique globally — the second clinic ever
    created couldn't stock the same drug (and its seed silently failed).
    Names are unique per clinic only."""
    from app.modules.medication_catalog.schemas import MedicationCatalogCreate
    from app.modules.medication_catalog.service import MedicationCatalogService

    other = Clinic(id=uuid4(), name="Clinic B", tax_id="B66666666", address={}, settings={})
    db_session.add(other)
    await db_session.commit()

    payload = MedicationCatalogCreate(name="Amoxicillin 500 mg", dose="500", unit="mg")
    a = await MedicationCatalogService.create_item(db_session, test_clinic.id, payload)
    b = await MedicationCatalogService.create_item(db_session, other.id, payload)
    assert a.id != b.id

    # ...but still unique WITHIN each clinic.
    with pytest.raises(HTTPException) as exc_info:
        await MedicationCatalogService.create_item(db_session, test_clinic.id, payload)
    assert exc_info.value.status_code == 409


def test_seed_list_has_56_unique_entries():
    names = [n.strip().lower() for n, *_ in DENTAL_MEDICATIONS]
    assert len(DENTAL_MEDICATIONS) == 56
    assert len(set(names)) == len(names)


@pytest.mark.asyncio
async def test_seed_endpoint_is_idempotent(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    for _ in range(2):
        res = await client.post("/api/v1/medication_catalog/seed", headers=auth_headers)
        assert res.status_code == 200, res.text
        summary = res.json()["data"]

    res = await client.get(
        "/api/v1/medication_catalog/", params={"page_size": 100}, headers=auth_headers
    )
    body = res.json()
    # Second run created nothing and skipped everything already present.
    assert summary["created"] == 0
    assert summary["skipped"] == 56
    assert body["total"] == 56
