"""Catalog items and categories only reference this clinic's VAT types and categories.

``category_id`` was already checked. ``vat_type_id`` and ``parent_id`` were
stored as given. An unknown id was a 500 (ForeignKeyViolation). Another
clinic's VAT type was stored, and every budget line made from the item then
snapshotted that clinic's rate. A category could also be its own parent.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.catalog.models import TreatmentCategory, VatType

BASE = "/api/v1/catalog"


@pytest_asyncio.fixture
async def foreign(db_session: AsyncSession) -> dict[str, str]:
    """A 21 % VAT type and a category owned by another clinic."""
    other = Clinic(id=uuid4(), name="Other", tax_id="B87654321")
    db_session.add(other)
    await db_session.flush()
    vat = VatType(clinic_id=other.id, names={"es": "General"}, rate=21.0)
    category = TreatmentCategory(clinic_id=other.id, key="other", names={"es": "Otra"})
    db_session.add_all([vat, category])
    await db_session.commit()
    return {"vat": str(vat.id), "category": str(category.id)}


@pytest_asyncio.fixture
async def own(db_session: AsyncSession, test_clinic: Clinic) -> dict[str, str]:
    vat = VatType(clinic_id=test_clinic.id, names={"es": "Reducido"}, rate=10.0)
    category = TreatmentCategory(clinic_id=test_clinic.id, key="mine", names={"es": "Mía"})
    db_session.add_all([vat, category])
    await db_session.commit()
    return {"vat": str(vat.id), "category": str(category.id)}


def _item(category_id: str, **extra) -> dict:
    return {
        "category_id": category_id,
        "internal_code": f"T-{uuid4().hex[:6]}",
        "names": {"es": "Limpieza"},
        **extra,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("which", ["unknown", "other_clinic"])
async def test_item_create_rejects_a_vat_type_that_isnt_the_clinics(
    client: AsyncClient, auth_headers, own, foreign, which
) -> None:
    vat = str(uuid4()) if which == "unknown" else foreign["vat"]
    r = await client.post(
        f"{BASE}/items", json=_item(own["category"], vat_type_id=vat), headers=auth_headers
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_item_edit_rejects_another_clinics_vat_type_and_keeps_its_own(
    client: AsyncClient, auth_headers, own, foreign
) -> None:
    created = await client.post(
        f"{BASE}/items", json=_item(own["category"], vat_type_id=own["vat"]), headers=auth_headers
    )
    assert created.status_code == 201, created.text
    url = f"{BASE}/items/{created.json()['data']['id']}"

    r = await client.put(url, json={"vat_type_id": foreign["vat"]}, headers=auth_headers)
    assert r.status_code == 400, r.text

    assert (await client.get(url, headers=auth_headers)).json()["data"]["vat_type_id"] == own["vat"]


@pytest.mark.asyncio
async def test_item_accepts_the_clinics_vat_type(client: AsyncClient, auth_headers, own) -> None:
    r = await client.post(
        f"{BASE}/items", json=_item(own["category"], vat_type_id=own["vat"]), headers=auth_headers
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["vat_type_id"] == own["vat"]


@pytest.mark.asyncio
@pytest.mark.parametrize("which", ["unknown", "other_clinic"])
async def test_category_create_rejects_a_parent_that_isnt_the_clinics(
    client: AsyncClient, auth_headers, test_clinic, foreign, which
) -> None:
    parent = str(uuid4()) if which == "unknown" else foreign["category"]
    r = await client.post(
        f"{BASE}/categories",
        json={"key": "child", "names": {"es": "Hija"}, "parent_id": parent},
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_category_edit_rejects_a_cycle_and_accepts_a_real_parent(
    client: AsyncClient, auth_headers, own
) -> None:
    child = await client.post(
        f"{BASE}/categories",
        json={"key": "child", "names": {"es": "Hija"}, "parent_id": own["category"]},
        headers=auth_headers,
    )
    assert child.status_code == 201, child.text
    child_id = child.json()["data"]["id"]

    # Neither the category itself nor its own child can become its parent.
    for parent in (own["category"], child_id):
        r = await client.put(
            f"{BASE}/categories/{own['category']}",
            json={"parent_id": parent},
            headers=auth_headers,
        )
        assert r.status_code == 400, r.text
