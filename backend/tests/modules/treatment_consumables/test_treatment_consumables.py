"""treatment_consumables: validated links, duplicates, isolation — over HTTP."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory
from app.modules.inventory.models import InventoryItem


@pytest.fixture
async def seeded_pair(db_session: AsyncSession, test_clinic: Clinic):
    """One catalog treatment + one inventory item in the test clinic."""
    category = TreatmentCategory(
        clinic_id=test_clinic.id,
        key="tests",
        names={"es": "Pruebas", "en": "Tests"},
    )
    db_session.add(category)
    await db_session.flush()

    treatment = TreatmentCatalogItem(
        clinic_id=test_clinic.id,
        category_id=category.id,
        internal_code="ENDO-01",
        names={"es": "Endodoncia", "en": "Root canal"},
    )
    item = InventoryItem(
        clinic_id=test_clinic.id,
        name="Anesthetic vial",
        category="consumables",
        unit="vials",
    )
    db_session.add_all([treatment, item])
    await db_session.commit()
    return treatment, item


async def _create(client: AsyncClient, headers: dict, **payload) -> tuple[int, dict]:
    res = await client.post("/api/v1/treatment_consumables/", json=payload, headers=headers)
    body = res.json() if res.content else {}
    return res.status_code, (body.get("data") or {})


@pytest.mark.asyncio
async def test_create_update_delete_over_http(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    seeded_pair,
):
    treatment, item = seeded_pair

    code, link = await _create(
        client,
        auth_headers,
        catalog_item_id=str(treatment.id),
        inventory_item_id=str(item.id),
        quantity="2",
        note="per session",
    )
    assert code == 201, link
    assert link["treatment_name"] == "Endodoncia"  # resolved from JSONB names
    assert link["item_name"] == "Anesthetic vial"
    assert link["item_unit"] == "vials"
    assert Decimal(link["quantity"]) == Decimal("2")
    assert link["note"] == "per session"

    # Duplicate pair → 409 (never a raw unique-constraint 500).
    code, _ = await _create(
        client,
        auth_headers,
        catalog_item_id=str(treatment.id),
        inventory_item_id=str(item.id),
        quantity="1",
    )
    assert code == 409

    # Update quantity — an omitted note leaves the stored one untouched.
    res = await client.patch(
        f"/api/v1/treatment_consumables/{link['id']}",
        json={"quantity": "3.5"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    assert Decimal(res.json()["data"]["quantity"]) == Decimal("3.5")
    assert res.json()["data"]["note"] == "per session"

    # Editing the note, and clearing it with "".
    res = await client.patch(
        f"/api/v1/treatment_consumables/{link['id']}",
        json={"quantity": "3.5", "note": "only if surgery"},
        headers=auth_headers,
    )
    assert res.json()["data"]["note"] == "only if surgery"
    res = await client.patch(
        f"/api/v1/treatment_consumables/{link['id']}",
        json={"quantity": "3.5", "note": ""},
        headers=auth_headers,
    )
    assert res.json()["data"]["note"] is None

    # The note survives the round-trip through the list endpoint too.
    res = await client.patch(
        f"/api/v1/treatment_consumables/{link['id']}",
        json={"quantity": "3.5", "note": "per session"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    res = await client.get("/api/v1/treatment_consumables/", headers=auth_headers)
    assert res.json()["data"][0]["note"] == "per session"

    # Filter by treatment.
    res = await client.get(
        "/api/v1/treatment_consumables/",
        params={"catalog_item_id": str(treatment.id)},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["total"] == 1

    # Delete.
    res = await client.delete(f"/api/v1/treatment_consumables/{link['id']}", headers=auth_headers)
    assert res.status_code == 204
    res = await client.get("/api/v1/treatment_consumables/", headers=auth_headers)
    assert res.json()["total"] == 0


@pytest.mark.asyncio
async def test_links_to_other_clinic_are_rejected(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    seeded_pair,
):
    """Validation reads both dependency modules scoped to OUR clinic:
    a treatment/item belonging to another clinic must 404, not link."""
    other = Clinic(id=uuid4(), name="Other", tax_id="B55555555", address={}, settings={})
    db_session.add(other)
    await db_session.commit()

    foreign_category = TreatmentCategory(
        clinic_id=other.id,
        key="other-tests",
        names={"es": "Otra"},
    )
    db_session.add(foreign_category)
    await db_session.flush()
    foreign_treatment = TreatmentCatalogItem(
        clinic_id=other.id,
        category_id=foreign_category.id,
        internal_code="FOREIGN-01",
        names={"es": "Tratamiento ajeno"},
    )
    foreign_item = InventoryItem(
        clinic_id=other.id, name="Foreign item", category="x", unit="units"
    )
    db_session.add_all([foreign_treatment, foreign_item])
    await db_session.commit()

    treatment, item = seeded_pair

    code, _ = await _create(
        client,
        auth_headers,
        catalog_item_id=str(foreign_treatment.id),
        inventory_item_id=str(item.id),
        quantity="1",
    )
    assert code == 404

    code, _ = await _create(
        client,
        auth_headers,
        catalog_item_id=str(treatment.id),
        inventory_item_id=str(foreign_item.id),
        quantity="1",
    )
    assert code == 404


@pytest.mark.asyncio
async def test_link_options_search(client: AsyncClient, auth_headers: dict, seeded_pair):
    treatment, item = seeded_pair

    res = await client.get(
        "/api/v1/treatment_consumables/link-options", params={"q": "endo"}, headers=auth_headers
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert any(t["id"] == str(treatment.id) for t in data["treatments"])
    assert data["items"] == []  # 'endo' matches no item name

    res = await client.get(
        "/api/v1/treatment_consumables/link-options", params={"q": "anesth"}, headers=auth_headers
    )
    data = res.json()["data"]
    assert any(i["id"] == str(item.id) for i in data["items"])
