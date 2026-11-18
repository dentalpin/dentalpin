"""Tests for the unified /treatments API (header + children model)."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.catalog.models import (
    TreatmentCatalogItem,
    TreatmentCategory,
    TreatmentOdontogramMapping,
    VatType,
)


async def _ensure_clinic_and_patient(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict[str, str]
) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    clinic = Clinic(
        id=uuid4(),
        name="Test Clinic",
        tax_id="B99999999",
        address={"street": "x", "city": "y"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(clinic)
    await db_session.flush()

    db_session.add(
        ClinicMembership(id=uuid4(), user_id=user_id, clinic_id=clinic.id, role="dentist")
    )
    await db_session.commit()

    patient_resp = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Ana", "last_name": "Perez", "phone": "+34666111222"},
    )
    patient_id = patient_resp.json()["data"]["id"]

    return {"clinic_id": str(clinic.id), "user_id": user_id, "patient_id": patient_id}


async def _seed_catalog_items(db_session: AsyncSession, clinic_id) -> dict:
    """Seed a minimal catalog: a flat filling, a per_tooth crown and a per_role bridge."""
    vat = VatType(clinic_id=clinic_id, names={"es": "Exento"}, rate=0.0, is_default=True)
    db_session.add(vat)
    await db_session.flush()

    cat = TreatmentCategory(
        clinic_id=clinic_id,
        key="restauradora",
        names={"es": "Restauradora"},
        is_system=True,
    )
    db_session.add(cat)
    await db_session.flush()

    filling = TreatmentCatalogItem(
        clinic_id=clinic_id,
        category_id=cat.id,
        internal_code="TST-FILL",
        names={"es": "Empaste"},
        default_price=Decimal("80.00"),
        pricing_strategy="flat",
        treatment_scope="tooth",
        requires_surfaces=True,
        vat_type_id=vat.id,
    )
    crown = TreatmentCatalogItem(
        clinic_id=clinic_id,
        category_id=cat.id,
        internal_code="TST-CROWN",
        names={"es": "Corona"},
        default_price=Decimal("500.00"),
        pricing_strategy="per_tooth",
        treatment_scope="tooth",
        vat_type_id=vat.id,
    )
    bridge = TreatmentCatalogItem(
        clinic_id=clinic_id,
        category_id=cat.id,
        internal_code="TST-BRIDGE",
        names={"es": "Puente"},
        default_price=Decimal("400.00"),
        pricing_strategy="per_role",
        pricing_config={"pillar": 500, "pontic": 300},
        treatment_scope="multi_tooth",
        vat_type_id=vat.id,
    )
    cleaning = TreatmentCatalogItem(
        clinic_id=clinic_id,
        category_id=cat.id,
        internal_code="TST-CLEAN",
        names={"es": "Limpieza"},
        default_price=Decimal("60.00"),
        pricing_strategy="flat",
        treatment_scope="global_mouth",
        vat_type_id=vat.id,
    )
    splint = TreatmentCatalogItem(
        clinic_id=clinic_id,
        category_id=cat.id,
        internal_code="TST-SPLINT-ARCH",
        names={"es": "Férula de descarga"},
        default_price=Decimal("120.00"),
        pricing_strategy="flat",
        treatment_scope="global_arch",
        vat_type_id=vat.id,
    )
    # Tooth-scoped item with no odontogram mapping — creating a treatment from
    # it without an explicit clinical_type must be rejected.
    nomap_tooth = TreatmentCatalogItem(
        clinic_id=clinic_id,
        category_id=cat.id,
        internal_code="TST-NOMAP",
        names={"es": "Sin mapping"},
        default_price=Decimal("50.00"),
        pricing_strategy="flat",
        treatment_scope="tooth",
        vat_type_id=vat.id,
    )
    db_session.add_all([filling, crown, bridge, cleaning, splint, nomap_tooth])
    await db_session.flush()

    # Note: `cleaning` (global_mouth) deliberately has NO mapping — like the
    # production seeds. The service falls back to clinical_type='other'.
    for item, otype in (
        (filling, "filling_composite"),
        (crown, "crown"),
        (bridge, "bridge"),
        (splint, "splint"),
    ):
        db_session.add(
            TreatmentOdontogramMapping(
                clinic_id=clinic_id,
                catalog_item_id=item.id,
                odontogram_treatment_type=otype,
                clinical_category="restauradora",
                visualization_rules=[],
                visualization_config={},
            )
        )
    await db_session.commit()

    return {
        "filling_id": str(filling.id),
        "crown_id": str(crown.id),
        "bridge_id": str(bridge.id),
        "cleaning_id": str(cleaning.id),
        "splint_arch_id": str(splint.id),
        "nomap_tooth_id": str(nomap_tooth.id),
    }


@pytest.fixture
async def setup(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> dict:
    ctx = await _ensure_clinic_and_patient(db_session, client, auth_headers)
    catalog = await _seed_catalog_items(db_session, ctx["clinic_id"])
    return {**ctx, **catalog}


# ----------------------------------------------------------------------------
# Single-tooth treatments
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_single_tooth_filling_with_surfaces(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["filling_id"],
            "tooth_numbers": [16],
            "surfaces": ["M", "O"],
            "status": "performed",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["clinical_type"] == "filling_composite"
    assert data["status"] == "performed"
    assert data["price_snapshot"] == "80.00"
    assert len(data["teeth"]) == 1
    assert data["teeth"][0]["surfaces"] == ["M", "O"]


# ----------------------------------------------------------------------------
# per_tooth pricing (multi-tooth uniform)
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uniform_multiple_crowns_scales_price(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["crown_id"],
            "scope": "multi_tooth",
            "tooth_numbers": [12, 11, 21, 22],
            "status": "planned",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["clinical_type"] == "crown"
    assert len(data["teeth"]) == 4
    assert data["price_snapshot"] == "2000.00"  # 500 * 4


# ----------------------------------------------------------------------------
# per_role pricing (bridges)
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bridge_assigns_roles_and_prices_per_role(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["bridge_id"],
            "scope": "multi_tooth",
            "tooth_numbers": [14, 15, 16],
            "status": "planned",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["clinical_type"] == "bridge"
    by_tooth = {t["tooth_number"]: t["role"] for t in data["teeth"]}
    assert by_tooth == {14: "pillar", 15: "pontic", 16: "pillar"}
    assert Decimal(data["price_snapshot"]) == Decimal("1300")  # 500 + 300 + 500


@pytest.mark.asyncio
async def test_bridge_requires_at_least_two_teeth(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    r = await client.post(
        f"/api/v1/odontogram/patients/{setup['patient_id']}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["bridge_id"],
            "scope": "multi_tooth",
            "tooth_numbers": [14],
            "status": "planned",
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_bridge_cantilever_two_teeth_with_explicit_roles(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Cantilever bridge: 2 teeth, 1 pillar + 1 pontic — caller supplies roles."""
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["bridge_id"],
            "scope": "multi_tooth",
            "teeth": [
                {"tooth_number": 14, "role": "pillar"},
                {"tooth_number": 15, "role": "pontic"},
            ],
            "status": "planned",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    by_tooth = {t["tooth_number"]: t["role"] for t in data["teeth"]}
    assert by_tooth == {14: "pillar", 15: "pontic"}
    assert Decimal(data["price_snapshot"]) == Decimal("800")  # 500 + 300


@pytest.mark.asyncio
async def test_bridge_honors_explicit_mid_span_pillar(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Mid-span pillar bridge: pillar-pontic-pillar-pontic-pillar."""
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["bridge_id"],
            "scope": "multi_tooth",
            "teeth": [
                {"tooth_number": 14, "role": "pillar"},
                {"tooth_number": 15, "role": "pontic"},
                {"tooth_number": 16, "role": "pillar"},
                {"tooth_number": 17, "role": "pontic"},
                {"tooth_number": 18, "role": "pillar"},
            ],
            "status": "planned",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    by_tooth = {t["tooth_number"]: t["role"] for t in data["teeth"]}
    assert by_tooth == {14: "pillar", 15: "pontic", 16: "pillar", 17: "pontic", 18: "pillar"}


@pytest.mark.asyncio
async def test_bridge_rejects_all_pontic(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["bridge_id"],
            "scope": "multi_tooth",
            "teeth": [
                {"tooth_number": 14, "role": "pontic"},
                {"tooth_number": 15, "role": "pontic"},
                {"tooth_number": 16, "role": "pontic"},
            ],
            "status": "planned",
        },
    )
    assert r.status_code in (400, 422)


# ----------------------------------------------------------------------------
# Diagnostic finding without catalog item
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_diagnostic_finding_without_catalog(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    r = await client.post(
        f"/api/v1/odontogram/patients/{setup['patient_id']}/treatments",
        headers=auth_headers,
        json={
            "clinical_type": "caries",
            "tooth_numbers": [26],
            "surfaces": ["O"],
            "status": "performed",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["clinical_type"] == "caries"
    assert data["catalog_item_id"] is None
    assert data["price_snapshot"] is None


# ----------------------------------------------------------------------------
# Conflicts and validators
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catalog_clinical_type_conflict_rejected(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """If both catalog and clinical_type are given, they must match."""
    r = await client.post(
        f"/api/v1/odontogram/patients/{setup['patient_id']}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["crown_id"],
            "clinical_type": "filling_composite",
            "tooth_numbers": [21],
            "status": "planned",
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_perform_transitions_status(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    create = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["crown_id"],
            "tooth_numbers": [26],
            "status": "planned",
        },
    )
    tid = create.json()["data"]["id"]
    r = await client.patch(
        f"/api/v1/odontogram/treatments/{tid}/perform",
        headers=auth_headers,
        json={"notes": "done"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "performed"


@pytest.mark.asyncio
async def test_delete_soft_deletes(
    client: AsyncClient, auth_headers: dict, setup: dict, db_session: AsyncSession
) -> None:
    pid = setup["patient_id"]
    create = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["crown_id"],
            "tooth_numbers": [26],
            "status": "planned",
        },
    )
    tid = create.json()["data"]["id"]
    r = await client.delete(f"/api/v1/odontogram/treatments/{tid}", headers=auth_headers)
    assert r.status_code == 204

    listing = await client.get(
        f"/api/v1/odontogram/patients/{pid}/treatments", headers=auth_headers
    )
    assert listing.json()["total"] == 0  # soft-deleted excluded


# ----------------------------------------------------------------------------
# scope derivation and global treatments
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scope_tooth_derived_from_single_tooth(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["crown_id"],
            "tooth_numbers": [26],
            "status": "planned",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["scope"] == "tooth"
    assert data["arch"] is None


@pytest.mark.asyncio
async def test_scope_multi_tooth_derived_when_two_teeth(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["crown_id"],
            "tooth_numbers": [11, 21],
            "status": "planned",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["scope"] == "multi_tooth"


@pytest.mark.asyncio
async def test_create_global_mouth_treatment(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["cleaning_id"],
            "scope": "global_mouth",
            "status": "planned",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["scope"] == "global_mouth"
    assert data["arch"] is None
    assert data["teeth"] == []
    assert data["price_snapshot"] == "60.00"
    # Unmapped catalog item + global scope → server-side 'other' fallback.
    assert data["clinical_type"] == "other"


@pytest.mark.asyncio
async def test_unmapped_tooth_item_requires_clinical_type(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Tooth-scoped items without an odontogram mapping still require an
    explicit clinical_type — the 'other' fallback is global-scope only."""
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["nomap_tooth_id"],
            "tooth_numbers": [26],
            "status": "planned",
        },
    )
    assert r.status_code == 400
    assert "clinical_type" in r.text


@pytest.mark.asyncio
async def test_create_global_arch_treatment(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["splint_arch_id"],
            "scope": "global_arch",
            "arch": "upper",
            "status": "planned",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["scope"] == "global_arch"
    assert data["arch"] == "upper"
    assert data["teeth"] == []


@pytest.mark.asyncio
async def test_global_arch_requires_arch(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["splint_arch_id"],
            "scope": "global_arch",
            "status": "planned",
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_arch_rejected_for_non_global_arch_scope(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["crown_id"],
            "tooth_numbers": [26],
            "arch": "upper",
            "status": "planned",
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_global_mouth_rejects_teeth(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["cleaning_id"],
            "scope": "global_mouth",
            "tooth_numbers": [11],
            "status": "planned",
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_no_scope_no_teeth_raises(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    pid = setup["patient_id"]
    r = await client.post(
        f"/api/v1/odontogram/patients/{pid}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["crown_id"],
            "status": "planned",
        },
    )
    assert r.status_code == 422


# ----------------------------------------------------------------------------
# Earned ledger (payments subscribes transactionally — ADR 0019, issue #183)
# ----------------------------------------------------------------------------


async def _earned_rows(db_session: AsyncSession, treatment_id) -> list:
    from sqlalchemy import select

    from app.modules.payments.models import PatientEarnedEntry

    result = await db_session.execute(
        select(PatientEarnedEntry).where(PatientEarnedEntry.treatment_id == treatment_id)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_perform_books_the_earned_entry(
    client: AsyncClient, auth_headers: dict, setup: dict, db_session: AsyncSession
) -> None:
    create = await client.post(
        f"/api/v1/odontogram/patients/{setup['patient_id']}/treatments",
        headers=auth_headers,
        json={"catalog_item_id": setup["crown_id"], "tooth_numbers": [26], "status": "planned"},
    )
    tid = create.json()["data"]["id"]

    r = await client.patch(
        f"/api/v1/odontogram/treatments/{tid}/perform", headers=auth_headers, json={}
    )
    assert r.status_code == 200

    rows = await _earned_rows(db_session, UUID(tid))
    assert len(rows) == 1
    assert rows[0].amount == Decimal("500.00")


@pytest.mark.asyncio
async def test_earned_entry_rolls_back_with_the_treatment(
    client: AsyncClient, auth_headers: dict, setup: dict, db_session: AsyncSession
) -> None:
    """Revenue is booked in the publisher's transaction.

    The handler used to open its own session and commit there, so a request
    that failed after ``perform`` left an earned entry for a treatment that
    never happened — ``treatment_id`` carries no FK to catch it (issue #183).
    """
    from app.modules.odontogram.service import TreatmentService

    create = await client.post(
        f"/api/v1/odontogram/patients/{setup['patient_id']}/treatments",
        headers=auth_headers,
        json={"catalog_item_id": setup["crown_id"], "tooth_numbers": [27], "status": "planned"},
    )
    tid = UUID(create.json()["data"]["id"])
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = UUID(me.json()["data"]["user"]["id"])

    await TreatmentService.perform(db_session, UUID(setup["clinic_id"]), tid, user_id)
    assert await _earned_rows(db_session, tid), "earned entry should exist inside the tx"

    await db_session.rollback()

    assert await _earned_rows(db_session, tid) == []


@pytest.mark.asyncio
async def test_perform_twice_is_refused(
    client: AsyncClient, auth_headers: dict, setup: dict, db_session: AsyncSession
) -> None:
    """A second perform would publish ``performed`` again (#891).

    That re-books revenue where the first event booked none (a sessioned
    treatment finalized with ``unit_price: null``), adds a second timeline
    entry and overwrites who performed it and when.
    """
    create = await client.post(
        f"/api/v1/odontogram/patients/{setup['patient_id']}/treatments",
        headers=auth_headers,
        json={"catalog_item_id": setup["crown_id"], "tooth_numbers": [36], "status": "planned"},
    )
    tid = create.json()["data"]["id"]
    url = f"/api/v1/odontogram/treatments/{tid}/perform"

    first = await client.patch(url, headers=auth_headers, json={})
    assert first.status_code == 200, first.text
    performed_at = first.json()["data"]["performed_at"]

    again = await client.patch(url, headers=auth_headers, json={"notes": "again"})
    assert again.status_code == 409, again.text

    detail = await client.get(f"/api/v1/odontogram/treatments/{tid}", headers=auth_headers)
    assert detail.json()["data"]["performed_at"] == performed_at
    assert len(await _earned_rows(db_session, UUID(tid))) == 1


async def _own_session_per_request():
    # Production's get_db: one session per request, committed at the end.
    from app.database import async_session_maker

    async with async_session_maker() as session:
        yield session
        await session.commit()


@pytest.mark.asyncio
async def test_concurrent_performs_publish_once(
    client: AsyncClient, auth_headers: dict, setup: dict, db_session: AsyncSession
) -> None:
    """Two requests racing on one treatment: one performs it, the other gets 409."""
    import asyncio

    from sqlalchemy import func, select

    from app.database import async_session_maker, get_db
    from app.main import app
    from app.modules.patient_timeline.models import PatientTimeline

    create = await client.post(
        f"/api/v1/odontogram/patients/{setup['patient_id']}/treatments",
        headers=auth_headers,
        json={"catalog_item_id": setup["crown_id"], "tooth_numbers": [37], "status": "planned"},
    )
    tid = create.json()["data"]["id"]
    await db_session.commit()  # the racing requests each open their own session
    app.dependency_overrides[get_db] = _own_session_per_request
    url = f"/api/v1/odontogram/treatments/{tid}/perform"

    results = await asyncio.gather(
        client.patch(url, headers=auth_headers, json={}),
        client.patch(url, headers=auth_headers, json={}),
    )

    assert sorted(r.status_code for r in results) == [200, 409]
    async with async_session_maker() as fresh:
        performed_rows = (
            await fresh.execute(
                select(func.count()).where(
                    PatientTimeline.source_id == UUID(tid),
                    PatientTimeline.event_type == "odontogram.treatment.performed",
                )
            )
        ).scalar_one()
    assert performed_rows == 1
