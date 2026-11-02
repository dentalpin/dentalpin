"""Tests for the catalog seeder.

Verifies that the seeded catalog includes globally-scoped treatments (cleaning,
whitening, whole-arch prosthesis, etc.) and that every seeded item uses one of
the four valid `treatment_scope` values.
"""

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.catalog.models import TreatmentCatalogItem
from app.modules.catalog.seed import seed_catalog

VALID_SCOPES = {"tooth", "multi_tooth", "global_mouth", "global_arch"}


@pytest.fixture
async def seeded_clinic(db_session: AsyncSession) -> Clinic:
    clinic = Clinic(
        id=uuid4(),
        name="Seed Clinic",
        tax_id="B44444444",
        address={"street": "x", "city": "y"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(clinic)
    await db_session.flush()
    await seed_catalog(db_session, clinic.id)
    await db_session.commit()
    return clinic


@pytest.mark.asyncio
async def test_seed_creates_global_mouth_items(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    result = await db_session.execute(
        select(TreatmentCatalogItem).where(
            TreatmentCatalogItem.clinic_id == seeded_clinic.id,
            TreatmentCatalogItem.treatment_scope == "global_mouth",
        )
    )
    items = list(result.scalars().all())
    codes = {i.internal_code for i in items}

    # Essential globals that should always be seeded.
    assert "PREV-CLEAN" in codes
    assert "PREV-FLUOR" in codes
    assert "PREV-CHECKUP" in codes
    assert any(c.startswith("EST-BLAN") for c in codes), (
        "At least one whitening item should be global_mouth"
    )


@pytest.mark.asyncio
async def test_seed_creates_global_arch_items(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    result = await db_session.execute(
        select(TreatmentCatalogItem).where(
            TreatmentCatalogItem.clinic_id == seeded_clinic.id,
            TreatmentCatalogItem.treatment_scope == "global_arch",
        )
    )
    items = list(result.scalars().all())
    codes = {i.internal_code for i in items}

    assert "REST-SPLINT-OCC" in codes
    assert "PROT-FULL-SUP" in codes
    assert "PROT-FULL-INF" in codes


@pytest.mark.asyncio
async def test_seed_creates_multi_tooth_items(
    db_session: AsyncSession, seeded_clinic: Clinic
) -> None:
    result = await db_session.execute(
        select(TreatmentCatalogItem).where(
            TreatmentCatalogItem.clinic_id == seeded_clinic.id,
            TreatmentCatalogItem.treatment_scope == "multi_tooth",
        )
    )
    items = list(result.scalars().all())
    codes = {i.internal_code for i in items}

    # All bridges must be multi_tooth.
    assert "REST-BRIDGE-MC" in codes
    assert "REST-BRIDGE-ZIR" in codes


@pytest.mark.asyncio
async def test_seed_items_have_valid_scope(db_session: AsyncSession, seeded_clinic: Clinic) -> None:
    result = await db_session.execute(
        select(TreatmentCatalogItem).where(
            TreatmentCatalogItem.clinic_id == seeded_clinic.id,
        )
    )
    items = list(result.scalars().all())
    assert items, "Seeder should create items"
    for item in items:
        assert item.treatment_scope in VALID_SCOPES, (
            f"{item.internal_code} has invalid scope {item.treatment_scope}"
        )


@pytest.mark.asyncio
async def test_seed_endpoint_is_idempotent_repair_path(
    client, auth_headers: dict, test_clinic: Clinic, db_session: AsyncSession
) -> None:
    """``POST /catalog/seed`` fills an empty clinic and is a no-op afterwards."""
    from app.modules.catalog.models import TreatmentCategory

    r = await client.post("/api/v1/catalog/seed", headers=auth_headers)
    assert r.status_code == 200, r.text
    first = r.json()["data"]
    assert first["categories"] > 0 and first["items"] > 100 and first["vat_types"] >= 1
    assert first["vat_types"] == 1  # test_clinic has no country → generic preset (exempt only)

    cats = await db_session.scalar(
        select(func.count())
        .select_from(TreatmentCategory)
        .where(TreatmentCategory.clinic_id == test_clinic.id)
    )
    assert cats == first["categories"]

    r = await client.post("/api/v1/catalog/seed", headers=auth_headers)
    assert r.status_code == 200
    second = r.json()["data"]
    assert second == {"categories": 0, "items": 0, "vat_types": 0}


@pytest.mark.asyncio
async def test_seed_endpoint_tolerates_a_clinic_type_at_a_preset_rate(
    client, auth_headers: dict, test_clinic: Clinic, db_session: AsyncSession
) -> None:
    """A clinic's own 0% type next to the seeded exempt one made the repair
    path 500 with ``MultipleResultsFound``; the seed now reuses the system
    row and creates nothing."""
    from app.modules.catalog.models import VatType

    r = await client.post("/api/v1/catalog/seed", headers=auth_headers)
    assert r.status_code == 200, r.text
    system = await db_session.scalar(
        select(VatType).where(VatType.clinic_id == test_clinic.id, VatType.is_system.is_(True))
    )
    own = VatType(clinic_id=test_clinic.id, names={"es": "No sujeto"}, rate=system.rate)
    db_session.add(own)
    await db_session.commit()

    r = await client.post("/api/v1/catalog/seed", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"] == {"categories": 0, "items": 0, "vat_types": 0}
