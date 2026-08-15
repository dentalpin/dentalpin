"""Smoke tests for the treatment plan module after the Treatment refactor."""

from decimal import Decimal
from uuid import uuid4

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
        name="Plan Clinic",
        tax_id="B11111111",
        address={"street": "a", "city": "b"},
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
        json={"first_name": "Luis", "last_name": "Soto", "phone": "+34666333444"},
    )
    patient_id = patient_resp.json()["data"]["id"]

    return {"clinic_id": str(clinic.id), "user_id": user_id, "patient_id": patient_id}


async def _seed_catalog_crown(db_session: AsyncSession, clinic_id) -> str:
    vat = VatType(clinic_id=clinic_id, names={"es": "Exento"}, rate=0.0, is_default=True)
    db_session.add(vat)
    await db_session.flush()
    cat = TreatmentCategory(clinic_id=clinic_id, key="rest", names={"es": "R"}, is_system=True)
    db_session.add(cat)
    await db_session.flush()
    crown = TreatmentCatalogItem(
        clinic_id=clinic_id,
        category_id=cat.id,
        internal_code="PLAN-CROWN",
        names={"es": "Corona"},
        default_price=Decimal("500.00"),
        pricing_strategy="flat",
        treatment_scope="tooth",
        vat_type_id=vat.id,
    )
    db_session.add(crown)
    await db_session.flush()
    db_session.add(
        TreatmentOdontogramMapping(
            clinic_id=clinic_id,
            catalog_item_id=crown.id,
            odontogram_treatment_type="crown",
            clinical_category="restauradora",
            visualization_rules=[],
            visualization_config={},
        )
    )
    await db_session.commit()
    return str(crown.id)


@pytest.fixture
async def setup(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> dict:
    ctx = await _ensure_clinic_and_patient(db_session, client, auth_headers)
    ctx["crown_id"] = await _seed_catalog_crown(db_session, ctx["clinic_id"])
    return ctx


async def _create_treatment(
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
    tooth_number: int = 16,
) -> str:
    r = await client.post(
        f"/api/v1/odontogram/patients/{setup['patient_id']}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": setup["crown_id"],
            "tooth_numbers": [tooth_number],
            "status": "planned",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def _create_plan_with_items(
    client: AsyncClient, auth_headers: dict, setup: dict, tooth_numbers: list[int]
) -> tuple[str, list[str]]:
    """Helper: create a plan and add N items (one per tooth). Returns (plan_id, item_ids)."""
    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"], "title": "Reorder plan"},
    )
    assert plan_resp.status_code == 201, plan_resp.text
    plan_id = plan_resp.json()["data"]["id"]

    item_ids: list[str] = []
    for tn in tooth_numbers:
        treatment_id = await _create_treatment(client, auth_headers, setup, tooth_number=tn)
        add = await client.post(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
            headers=auth_headers,
            json={"treatment_id": treatment_id},
        )
        assert add.status_code == 201, add.text
        item_ids.append(add.json()["data"]["id"])
    return plan_id, item_ids


async def _sync(db_session: AsyncSession) -> None:
    """Commit the test session and drop cached ORM state.

    Event handlers (``on_budget_accepted``) run in their own session, so the
    rows created through the shared test session must be committed before
    the event fires and re-read after the handler commits.
    """
    await db_session.commit()
    db_session.expire_all()


async def _activate_plan(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, plan_id: str
) -> str:
    """draft → pending (confirm) → active (accept the provisioned budget). Returns budget_id.

    Completing items books money, so the backend refuses it until the plan
    is ``active`` (issue #167) — every completion test goes through here.
    """
    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/confirm",
        headers=auth_headers,
        json={},
    )
    assert r.status_code == 200, r.text
    budget_id = r.json()["data"]["budget_id"]
    assert budget_id
    await _sync(db_session)
    r = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/accept",
        headers=auth_headers,
        json={"signature": {"signed_by_name": "Rosa Vega", "relationship_to_patient": "patient"}},
    )
    assert r.status_code == 200, r.text
    await _sync(db_session)
    plan = await client.get(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}", headers=auth_headers
    )
    assert plan.json()["data"]["status"] == "active", plan.text
    return budget_id


@pytest.mark.asyncio
async def test_create_empty_plan(client: AsyncClient, auth_headers: dict, setup: dict) -> None:
    r = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"], "title": "Demo plan"},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_add_treatment_item_to_plan(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"], "title": "Demo"},
    )
    plan_id = plan_resp.json()["data"]["id"]
    treatment_id = await _create_treatment(client, auth_headers, setup)

    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
        headers=auth_headers,
        json={"treatment_id": treatment_id},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["treatment_id"] == treatment_id
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_duplicate_treatment_id_rejected(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"]},
    )
    plan_id = plan_resp.json()["data"]["id"]
    treatment_id = await _create_treatment(client, auth_headers, setup)

    first = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
        headers=auth_headers,
        json={"treatment_id": treatment_id},
    )
    assert first.status_code == 201

    # Unique constraint on treatment_id — second add raises IntegrityError
    # which the handler surfaces as a 5xx. Capture the exception to keep the
    # assertion focused on "the duplicate was blocked".
    from sqlalchemy.exc import IntegrityError

    try:
        second = await client.post(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
            headers=auth_headers,
            json={"treatment_id": treatment_id},
        )
        assert second.status_code in (400, 409, 500)
    except IntegrityError:
        pass


# ---------------------------------------------------------------------------
# Reorder
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reorder_items_happy_path(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, item_ids = await _create_plan_with_items(client, auth_headers, setup, [16, 15, 14])
    reversed_ids = list(reversed(item_ids))

    r = await client.patch(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/reorder",
        headers=auth_headers,
        json={"item_ids": reversed_ids},
    )
    assert r.status_code == 200, r.text
    returned = [i["id"] for i in r.json()["data"]["items"]]
    assert returned == reversed_ids

    # Persistence: re-fetch.
    g = await client.get(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
    )
    again = [i["id"] for i in g.json()["data"]["items"]]
    assert again == reversed_ids


@pytest.mark.asyncio
async def test_reorder_rejects_missing_item(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, item_ids = await _create_plan_with_items(client, auth_headers, setup, [16, 15])
    # Drop one.
    r = await client.patch(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/reorder",
        headers=auth_headers,
        json={"item_ids": [item_ids[0]]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_reorder_rejects_foreign_item(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    from uuid import uuid4

    plan_id, item_ids = await _create_plan_with_items(client, auth_headers, setup, [16, 15])
    bogus = str(uuid4())
    r = await client.patch(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/reorder",
        headers=auth_headers,
        json={"item_ids": [item_ids[0], bogus]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_reorder_rejects_duplicate_ids(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, item_ids = await _create_plan_with_items(client, auth_headers, setup, [16, 15])
    r = await client.patch(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/reorder",
        headers=auth_headers,
        json={"item_ids": [item_ids[0], item_ids[0]]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_reorder_unknown_plan_returns_404(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    from uuid import uuid4

    r = await client.patch(
        f"/api/v1/treatment_plan/treatment-plans/{uuid4()}/items/reorder",
        headers=auth_headers,
        json={"item_ids": []},
    )
    assert r.status_code == 404


# -----------------------------------------------------------------------------
# Orphan cleanup on terminal plan states (archive / cancel)
# -----------------------------------------------------------------------------


async def _treatment_is_deleted(
    client: AsyncClient, auth_headers: dict, patient_id: str, treatment_id: str
) -> bool:
    """Check whether a Treatment is soft-deleted by looking for it in the odontogram list."""
    r = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/treatments",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    active_ids = {t["id"] for t in r.json()["data"]}
    return treatment_id not in active_ids


@pytest.mark.asyncio
async def test_delete_plan_removes_planned_treatments_from_odontogram(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Archiving a plan via DELETE soft-deletes its planned Treatments."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16, 15])

    # Snapshot treatment ids from the plan items
    plan_resp = await client.get(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
    )
    treatment_ids = [i["treatment"]["id"] for i in plan_resp.json()["data"]["items"]]
    assert len(treatment_ids) == 2

    # Archive plan
    r = await client.delete(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
    )
    assert r.status_code == 204, r.text

    # Both planned treatments should be gone from the odontogram
    for tid in treatment_ids:
        assert await _treatment_is_deleted(client, auth_headers, setup["patient_id"], tid), (
            f"treatment {tid} should be soft-deleted"
        )


@pytest.mark.asyncio
async def test_delete_plan_keeps_performed_treatments(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Archiving a plan preserves Treatments that were already performed."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16, 15])

    plan_resp = await client.get(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
    )
    items = plan_resp.json()["data"]["items"]
    treatment_ids = [i["treatment"]["id"] for i in items]
    performed_id, planned_id = treatment_ids[0], treatment_ids[1]

    # Mark first treatment as performed
    r = await client.patch(
        f"/api/v1/odontogram/treatments/{performed_id}/perform",
        headers=auth_headers,
        json={},
    )
    assert r.status_code == 200, r.text

    # Archive plan
    r = await client.delete(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
    )
    assert r.status_code == 204, r.text

    # Performed survives, planned removed
    assert not await _treatment_is_deleted(
        client, auth_headers, setup["patient_id"], performed_id
    ), "performed treatment must be preserved"
    assert await _treatment_is_deleted(client, auth_headers, setup["patient_id"], planned_id), (
        "planned treatment must be soft-deleted"
    )


# -----------------------------------------------------------------------------
# Lock / unlock on budget generation
# -----------------------------------------------------------------------------


async def _send_plan_budget(client: AsyncClient, auth_headers: dict, plan_id: str) -> str:
    """Fetch the plan's linked budget and mark it as sent (manual delivery)."""
    r = await client.get(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    budget_id = r.json()["data"]["budget_id"]
    assert budget_id, "confirm should have created a draft budget"

    r = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/send",
        headers=auth_headers,
        json={"send_email": False},
    )
    assert r.status_code == 200, r.text
    return budget_id


@pytest.mark.asyncio
async def test_add_item_allowed_on_draft_budget_blocked_once_sent(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """A draft budget does not lock the plan; sending it does.

    The draft never left the clinic, so the plan stays editable and the
    budget module mirrors the edit into the draft. Once the budget is
    sent it becomes a patient-facing contract — 409 from then on.
    """
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])

    # Confirm the plan (auto-creates a draft budget).
    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/confirm",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text

    # Draft budget → still editable (Telegram report: users had to
    # accept the quote just to keep choosing treatments).
    new_treatment_id = await _create_treatment(client, auth_headers, setup, tooth_number=15)
    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
        headers=auth_headers,
        json={"treatment_id": new_treatment_id},
    )
    assert r.status_code in (200, 201), r.text

    # Sent budget → locked.
    await _send_plan_budget(client, auth_headers, plan_id)
    another_treatment_id = await _create_treatment(client, auth_headers, setup, tooth_number=14)
    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
        headers=auth_headers,
        json={"treatment_id": another_treatment_id},
    )
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_remove_item_allowed_on_draft_budget_blocked_once_sent(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, item_ids = await _create_plan_with_items(client, auth_headers, setup, [16, 15])

    await client.patch(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/status",
        headers=auth_headers,
        json={"status": "active"},
    )
    await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/generate-budget",
        headers=auth_headers,
    )

    # Draft budget → removal allowed.
    r = await client.delete(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_ids[0]}",
        headers=auth_headers,
    )
    assert r.status_code in (200, 204), r.text

    # Sent budget → locked.
    await _send_plan_budget(client, auth_headers, plan_id)
    r = await client.delete(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_ids[1]}",
        headers=auth_headers,
    )
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_cancel_plan_removes_planned_treatments(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Closing an active plan cleans up its orphaned planned Treatments.

    Workflow rework: draft → pending → active → closed (cancelled_by_clinic).
    """
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    plan_resp = await client.get(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
    )
    treatment_id = plan_resp.json()["data"]["items"][0]["treatment"]["id"]

    # draft → pending (auto-creates draft budget)
    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/confirm",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text

    # pending → active (admin override via patch /status, would normally come from
    # the budget acceptance event; tests do that path explicitly).
    r = await client.patch(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/status",
        headers=auth_headers,
        json={"status": "active"},
    )
    assert r.status_code == 200, r.text

    # active → closed (cancelled by clinic)
    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/close",
        headers=auth_headers,
        json={"closure_reason": "cancelled_by_clinic"},
    )
    assert r.status_code == 200, r.text

    assert await _treatment_is_deleted(client, auth_headers, setup["patient_id"], treatment_id)


# ---------------------------------------------------------------------------
# Per-item assigned professional (doctor por tratamiento)
# ---------------------------------------------------------------------------


async def _add_professional(
    db_session: AsyncSession,
    clinic_id: str,
    email: str,
    role: str = "dentist",
) -> str:
    """Create a User + ClinicMembership for tests that need extra doctors."""
    from app.core.auth.models import User
    from app.core.auth.service import hash_password

    user = User(
        id=uuid4(),
        email=email,
        password_hash=hash_password("TestPass123"),
        first_name="Dr",
        last_name=email.split("@")[0],
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic_id, role=role))
    await db_session.commit()
    return str(user.id)


@pytest.mark.asyncio
async def test_add_item_inherits_plan_doctor(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
) -> None:
    doctor_id = await _add_professional(db_session, setup["clinic_id"], "doc-a@test.com")

    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={
            "patient_id": setup["patient_id"],
            "title": "Inherit",
            "assigned_professional_id": doctor_id,
        },
    )
    plan_id = plan_resp.json()["data"]["id"]
    treatment_id = await _create_treatment(client, auth_headers, setup)

    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
        headers=auth_headers,
        json={"treatment_id": treatment_id},
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["assigned_professional_id"] == doctor_id


@pytest.mark.asyncio
async def test_add_item_with_explicit_doctor_overrides_plan(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
) -> None:
    doctor_a = await _add_professional(db_session, setup["clinic_id"], "doc-a2@test.com")
    doctor_b = await _add_professional(db_session, setup["clinic_id"], "doc-b@test.com")

    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={
            "patient_id": setup["patient_id"],
            "assigned_professional_id": doctor_a,
        },
    )
    plan_id = plan_resp.json()["data"]["id"]
    treatment_id = await _create_treatment(client, auth_headers, setup)

    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
        headers=auth_headers,
        json={"treatment_id": treatment_id, "assigned_professional_id": doctor_b},
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["assigned_professional_id"] == doctor_b


@pytest.mark.asyncio
async def test_add_item_plan_without_doctor_yields_null(
    client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"]},
    )
    plan_id = plan_resp.json()["data"]["id"]
    treatment_id = await _create_treatment(client, auth_headers, setup)

    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
        headers=auth_headers,
        json={"treatment_id": treatment_id},
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["assigned_professional_id"] is None


@pytest.mark.asyncio
async def test_add_item_rejects_user_not_in_clinic(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
) -> None:
    # User exists but has no membership in our clinic.
    from app.core.auth.models import User
    from app.core.auth.service import hash_password

    other = User(
        id=uuid4(),
        email="not-here@test.com",
        password_hash=hash_password("TestPass123"),
        first_name="Foreign",
        last_name="Doc",
        is_active=True,
    )
    db_session.add(other)
    await db_session.commit()

    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"]},
    )
    plan_id = plan_resp.json()["data"]["id"]
    treatment_id = await _create_treatment(client, auth_headers, setup)

    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
        headers=auth_headers,
        json={"treatment_id": treatment_id, "assigned_professional_id": str(other.id)},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_update_item_doctor_can_be_unset_to_null(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
) -> None:
    doctor_id = await _add_professional(db_session, setup["clinic_id"], "doc-c@test.com")

    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"], "assigned_professional_id": doctor_id},
    )
    plan_id = plan_resp.json()["data"]["id"]
    treatment_id = await _create_treatment(client, auth_headers, setup)

    add = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
        headers=auth_headers,
        json={"treatment_id": treatment_id},
    )
    item_id = add.json()["data"]["id"]

    r = await client.put(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}",
        headers=auth_headers,
        json={"assigned_professional_id": None},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["assigned_professional_id"] is None


@pytest.mark.asyncio
async def test_update_plan_cascade_reassigns_matching_pending(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
) -> None:
    doctor_a = await _add_professional(db_session, setup["clinic_id"], "doc-cas-a@test.com")
    doctor_b = await _add_professional(db_session, setup["clinic_id"], "doc-cas-b@test.com")
    doctor_c = await _add_professional(db_session, setup["clinic_id"], "doc-cas-c@test.com")

    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"], "assigned_professional_id": doctor_a},
    )
    plan_id = plan_resp.json()["data"]["id"]

    # Two items inherit doctor_a, one explicit override to doctor_b.
    t1 = await _create_treatment(client, auth_headers, setup, tooth_number=16)
    t2 = await _create_treatment(client, auth_headers, setup, tooth_number=15)
    t3 = await _create_treatment(client, auth_headers, setup, tooth_number=14)

    i1 = (
        await client.post(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
            headers=auth_headers,
            json={"treatment_id": t1},
        )
    ).json()["data"]["id"]
    i2 = (
        await client.post(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
            headers=auth_headers,
            json={"treatment_id": t2, "assigned_professional_id": doctor_b},
        )
    ).json()["data"]["id"]
    i3 = (
        await client.post(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
            headers=auth_headers,
            json={"treatment_id": t3},
        )
    ).json()["data"]["id"]

    # Move plan doctor a → c with cascade.
    r = await client.put(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
        json={"assigned_professional_id": doctor_c, "reassign_pending_items": True},
    )
    assert r.status_code == 200, r.text

    detail = await client.get(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
    )
    by_id = {i["id"]: i for i in detail.json()["data"]["items"]}
    assert by_id[i1]["assigned_professional_id"] == doctor_c
    assert by_id[i2]["assigned_professional_id"] == doctor_b  # override survives
    assert by_id[i3]["assigned_professional_id"] == doctor_c


@pytest.mark.asyncio
async def test_update_plan_without_cascade_flag_leaves_items(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
) -> None:
    doctor_a = await _add_professional(db_session, setup["clinic_id"], "doc-nc-a@test.com")
    doctor_c = await _add_professional(db_session, setup["clinic_id"], "doc-nc-c@test.com")

    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"], "assigned_professional_id": doctor_a},
    )
    plan_id = plan_resp.json()["data"]["id"]
    t1 = await _create_treatment(client, auth_headers, setup)
    i1 = (
        await client.post(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
            headers=auth_headers,
            json={"treatment_id": t1},
        )
    ).json()["data"]["id"]

    r = await client.put(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
        json={"assigned_professional_id": doctor_c},  # no flag
    )
    assert r.status_code == 200

    detail = await client.get(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
    )
    items = {i["id"]: i for i in detail.json()["data"]["items"]}
    assert items[i1]["assigned_professional_id"] == doctor_a


@pytest.mark.asyncio
async def test_update_plan_cascade_skips_completed_items(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
) -> None:
    doctor_a = await _add_professional(db_session, setup["clinic_id"], "doc-sk-a@test.com")
    doctor_c = await _add_professional(db_session, setup["clinic_id"], "doc-sk-c@test.com")

    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"], "assigned_professional_id": doctor_a},
    )
    plan_id = plan_resp.json()["data"]["id"]
    t1 = await _create_treatment(client, auth_headers, setup, tooth_number=16)
    t2 = await _create_treatment(client, auth_headers, setup, tooth_number=15)

    i1 = (
        await client.post(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
            headers=auth_headers,
            json={"treatment_id": t1},
        )
    ).json()["data"]["id"]
    i2 = (
        await client.post(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
            headers=auth_headers,
            json={"treatment_id": t2},
        )
    ).json()["data"]["id"]

    await _activate_plan(client, auth_headers, db_session, plan_id)

    # Complete item 1.
    c = await client.patch(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{i1}/complete",
        headers=auth_headers,
        json={"completed_without_appointment": True},
    )
    assert c.status_code == 200, c.text

    # Cascade: i1 should keep doctor_a (completed); i2 should switch to doctor_c.
    r = await client.put(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
        json={"assigned_professional_id": doctor_c, "reassign_pending_items": True},
    )
    assert r.status_code == 200, r.text

    detail = await client.get(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
        headers=auth_headers,
    )
    items = {i["id"]: i for i in detail.json()["data"]["items"]}
    assert items[i1]["assigned_professional_id"] == doctor_a
    assert items[i2]["assigned_professional_id"] == doctor_c


@pytest.mark.asyncio
async def test_treatment_added_event_carries_assigned_professional(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
) -> None:
    from app.core.events import event_bus

    captured: list[dict] = []

    def _spy(payload: dict) -> None:
        captured.append(payload)

    event_bus.subscribe("treatment_plan.treatment_added", _spy)
    try:
        doctor_id = await _add_professional(db_session, setup["clinic_id"], "doc-event@test.com")
        plan_resp = await client.post(
            "/api/v1/treatment_plan/treatment-plans",
            headers=auth_headers,
            json={
                "patient_id": setup["patient_id"],
                "assigned_professional_id": doctor_id,
            },
        )
        plan_id = plan_resp.json()["data"]["id"]
        treatment_id = await _create_treatment(client, auth_headers, setup)

        r = await client.post(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
            headers=auth_headers,
            json={"treatment_id": treatment_id},
        )
        assert r.status_code == 201, r.text
    finally:
        event_bus.unsubscribe("treatment_plan.treatment_added", _spy)

    assert captured, "treatment_added event was not published"
    assert captured[-1]["assigned_professional_id"] == doctor_id


@pytest.mark.asyncio
async def test_change_item_doctor_works_when_plan_is_locked(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
) -> None:
    """Doctor reassignment bypasses the plan-lock guard.

    Reassigning who performs a treatment doesn't change the patient-facing
    contract, so it must stay possible even after the plan is confirmed and
    its budget is active.
    """
    doctor_b = await _add_professional(db_session, setup["clinic_id"], "doc-lock-b@test.com")

    plan_id, item_ids = await _create_plan_with_items(client, auth_headers, setup, [16])
    item_id = item_ids[0]

    # Confirm + activate + send the budget → plan ends up locked.
    # (A draft budget no longer locks — the contract starts at `sent`.)
    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/confirm",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    r = await client.patch(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/status",
        headers=auth_headers,
        json={"status": "active"},
    )
    assert r.status_code == 200, r.text
    await _send_plan_budget(client, auth_headers, plan_id)

    # Sanity: a structural change on the same item is still rejected.
    r = await client.put(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}",
        headers=auth_headers,
        json={"notes": "blocked by lock"},
    )
    assert r.status_code == 409, r.text

    # But the doctor change goes through.
    r = await client.put(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}",
        headers=auth_headers,
        json={"assigned_professional_id": doctor_b},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["assigned_professional_id"] == doctor_b


@pytest.mark.asyncio
async def test_change_doctor_rejected_on_completed_item(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
) -> None:
    """Once an item is completed, the planned doctor is frozen.

    ``completed_by`` is the source of truth for "who did it" after the fact;
    rewriting ``assigned_professional_id`` post-completion would distort
    clinical history.
    """
    doctor_b = await _add_professional(db_session, setup["clinic_id"], "doc-comp-b@test.com")

    plan_id, item_ids = await _create_plan_with_items(client, auth_headers, setup, [16])
    item_id = item_ids[0]
    await _activate_plan(client, auth_headers, db_session, plan_id)

    r = await client.patch(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/complete",
        headers=auth_headers,
        json={"completed_without_appointment": True},
    )
    assert r.status_code == 200, r.text

    r = await client.put(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}",
        headers=auth_headers,
        json={"assigned_professional_id": doctor_b},
    )
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# Multi-session billing
# ---------------------------------------------------------------------------


async def _seed_catalog_crown_with_sessions(db_session: AsyncSession, clinic_id) -> str:
    """Seed a catalog item with a 2-session template (200€ + 600€ = 800€)."""
    from app.modules.catalog.models import CatalogItemSession

    vat = VatType(clinic_id=clinic_id, names={"es": "Exento"}, rate=0.0, is_default=True)
    db_session.add(vat)
    await db_session.flush()
    cat = TreatmentCategory(clinic_id=clinic_id, key="restMS", names={"es": "R"}, is_system=True)
    db_session.add(cat)
    await db_session.flush()
    crown = TreatmentCatalogItem(
        clinic_id=clinic_id,
        category_id=cat.id,
        internal_code="CROWN-MS",
        names={"es": "Corona multi-sesión"},
        default_price=Decimal("800.00"),
        pricing_strategy="flat",
        treatment_scope="tooth",
        vat_type_id=vat.id,
    )
    db_session.add(crown)
    await db_session.flush()
    db_session.add(
        TreatmentOdontogramMapping(
            clinic_id=clinic_id,
            catalog_item_id=crown.id,
            odontogram_treatment_type="crown",
            clinical_category="restauradora",
            visualization_rules=[],
            visualization_config={},
        )
    )
    db_session.add_all(
        [
            CatalogItemSession(
                catalog_item_id=crown.id,
                sequence=1,
                labels={"es": "Toma de medidas"},
                default_price=Decimal("200.00"),
            ),
            CatalogItemSession(
                catalog_item_id=crown.id,
                sequence=2,
                labels={"es": "Colocación"},
                default_price=Decimal("600.00"),
            ),
        ]
    )
    await db_session.commit()
    return str(crown.id)


@pytest.fixture
async def setup_multi_session(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> dict:
    ctx = await _ensure_clinic_and_patient(db_session, client, auth_headers)
    ctx["crown_ms_id"] = await _seed_catalog_crown_with_sessions(db_session, ctx["clinic_id"])
    return ctx


async def _add_multi_session_item(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    ctx: dict,
    *,
    activate: bool = True,
) -> tuple[str, str, list[dict]]:
    """Create a plan + a treatment from the MS catalog item, add it, activate the plan.

    Returns (plan_id, item_id, sessions) — sessions as snapshotted at add time.
    """
    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={"patient_id": ctx["patient_id"], "title": "MS"},
    )
    plan_id = plan_resp.json()["data"]["id"]
    treatment_resp = await client.post(
        f"/api/v1/odontogram/patients/{ctx['patient_id']}/treatments",
        headers=auth_headers,
        json={
            "catalog_item_id": ctx["crown_ms_id"],
            "tooth_numbers": [16],
            "status": "planned",
        },
    )
    treatment_id = treatment_resp.json()["data"]["id"]
    add = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
        headers=auth_headers,
        json={"treatment_id": treatment_id},
    )
    assert add.status_code == 201, add.text
    item = add.json()["data"]
    if activate:
        await _activate_plan(client, auth_headers, db_session, plan_id)
    return plan_id, item["id"], item["sessions"]


@pytest.mark.asyncio
async def test_add_item_snapshots_catalog_sessions(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup_multi_session: dict
):
    """Catalog template with 2 sessions creates 2 plan item sessions."""
    _, _, sessions = await _add_multi_session_item(
        client, auth_headers, db_session, setup_multi_session
    )
    assert len(sessions) == 2
    assert [s["sequence"] for s in sessions] == [1, 2]
    assert sessions[0]["label"] == "Toma de medidas"
    assert float(sessions[0]["amount"]) == 200.00
    assert sessions[1]["label"] == "Colocación"
    assert float(sessions[1]["amount"]) == 600.00
    assert all(s["status"] == "pending" for s in sessions)


@pytest.mark.asyncio
async def test_add_item_without_catalog_template_creates_single_session(
    client: AsyncClient, auth_headers: dict, setup: dict
):
    """Item from a catalog item without sessions falls back to one session."""
    plan_resp = await client.post(
        "/api/v1/treatment_plan/treatment-plans",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"]},
    )
    plan_id = plan_resp.json()["data"]["id"]
    treatment_id = await _create_treatment(client, auth_headers, setup)
    add = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
        headers=auth_headers,
        json={"treatment_id": treatment_id},
    )
    sessions = add.json()["data"]["sessions"]
    assert len(sessions) == 1
    assert float(sessions[0]["amount"]) == 500.00


@pytest.mark.asyncio
async def test_complete_first_session_does_not_finalize_item(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup_multi_session: dict
):
    """Completing 1/2 sessions leaves item pending and emits the session event only."""
    from app.core.events import event_bus

    events: list[dict] = []

    async def _capture(payload: dict) -> None:
        events.append(payload)

    event_bus.subscribe("treatment_plan.item_session_completed", _capture)
    event_bus.subscribe("treatment_plan.treatment_completed", _capture)
    try:
        plan_id, item_id, sessions = await _add_multi_session_item(
            client, auth_headers, db_session, setup_multi_session
        )
        r = await client.patch(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/sessions/{sessions[0]['id']}/complete",
            headers=auth_headers,
            json={},
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["status"] == "pending"
        completed = [s for s in data["sessions"] if s["status"] == "completed"]
        assert len(completed) == 1
        # Session-completed event fired; treatment_completed must NOT have fired yet.
        session_events = [e for e in events if "session_id" in e]
        treatment_events = [e for e in events if "treatment_category_key" in e]
        assert len(session_events) == 1
        assert session_events[0]["amount"] == "200.00"
        assert treatment_events == []
    finally:
        event_bus._handlers.pop("treatment_plan.item_session_completed", None)  # noqa: SLF001
        event_bus._handlers.pop("treatment_plan.treatment_completed", None)  # noqa: SLF001


@pytest.mark.asyncio
async def test_complete_last_session_finalizes_item(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup_multi_session: dict
):
    """Completing the final pending session flips the item to completed and fires treatment_completed."""
    from app.core.events import event_bus

    events: list[dict] = []

    async def _capture(payload: dict) -> None:
        events.append(payload)

    event_bus.subscribe("treatment_plan.treatment_completed", _capture)
    try:
        plan_id, item_id, sessions = await _add_multi_session_item(
            client, auth_headers, db_session, setup_multi_session
        )
        for s in sessions:
            r = await client.patch(
                f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/sessions/{s['id']}/complete",
                headers=auth_headers,
                json={},
            )
            assert r.status_code == 200, r.text
        item = r.json()["data"]
        assert item["status"] == "completed"
        assert len(events) == 1  # treatment_completed fires exactly once
    finally:
        event_bus._handlers.pop("treatment_plan.treatment_completed", None)  # noqa: SLF001


@pytest.mark.asyncio
async def test_cancel_session_blocks_earned(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup_multi_session: dict
):
    """Cancelled sessions do not fire the session_completed event."""
    from app.core.events import event_bus

    session_events: list[dict] = []

    async def _capture(payload: dict) -> None:
        session_events.append(payload)

    event_bus.subscribe("treatment_plan.item_session_completed", _capture)
    try:
        plan_id, item_id, sessions = await _add_multi_session_item(
            client, auth_headers, db_session, setup_multi_session
        )
        # Cancel the 2nd session, complete the 1st
        cancel = await client.patch(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/sessions/{sessions[1]['id']}/cancel",
            headers=auth_headers,
            json={},
        )
        assert cancel.status_code == 200, cancel.text
        complete = await client.patch(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/sessions/{sessions[0]['id']}/complete",
            headers=auth_headers,
            json={},
        )
        item = complete.json()["data"]
        # Item finalizes since all sessions are terminal and one is completed
        assert item["status"] == "completed"
        # Only the completed session fired an earned event; cancelled didn't
        assert len(session_events) == 1
    finally:
        event_bus._handlers.pop("treatment_plan.item_session_completed", None)  # noqa: SLF001


@pytest.mark.asyncio
async def test_legacy_complete_endpoint_advances_next_session(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup_multi_session: dict
):
    """Legacy PATCH /items/{id}/complete completes the next pending session."""
    plan_id, item_id, sessions = await _add_multi_session_item(
        client, auth_headers, db_session, setup_multi_session
    )
    r = await client.patch(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/complete",
        headers=auth_headers,
        json={},
    )
    assert r.status_code == 200, r.text
    item = r.json()["data"]
    assert item["status"] == "pending"
    assert sum(1 for s in item["sessions"] if s["status"] == "completed") == 1


@pytest.mark.asyncio
async def test_edit_completed_session_rejected(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup_multi_session: dict
):
    """Edits on completed sessions are refused (400)."""
    plan_id, item_id, sessions = await _add_multi_session_item(
        client, auth_headers, db_session, setup_multi_session
    )
    await client.patch(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/sessions/{sessions[0]['id']}/complete",
        headers=auth_headers,
        json={},
    )
    r = await client.put(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/sessions/{sessions[0]['id']}",
        headers=auth_headers,
        json={"label": "Cambio", "amount": 250.00},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_finalize_suppresses_performed_price(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup_multi_session: dict
):
    """Regression: finalizing a sessioned item must NOT re-publish the full price.

    Each session already booked its amount via ``item_session_completed``;
    a ``unit_price`` on the finalizing ``odontogram.treatment.performed``
    event would double-charge the patient (2× the treatment price).
    """
    from app.core.events import event_bus

    performed_events: list[dict] = []
    session_events: list[dict] = []

    async def _capture_performed(payload: dict) -> None:
        performed_events.append(payload)

    async def _capture_session(payload: dict) -> None:
        session_events.append(payload)

    event_bus.subscribe("odontogram.treatment.performed", _capture_performed)
    event_bus.subscribe("treatment_plan.item_session_completed", _capture_session)
    try:
        plan_id, item_id, sessions = await _add_multi_session_item(
            client, auth_headers, db_session, setup_multi_session
        )
        for s in sessions:
            r = await client.patch(
                f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/sessions/{s['id']}/complete",
                headers=auth_headers,
                json={},
            )
            assert r.status_code == 200, r.text
        # The sessions carried the money: 200 + 600 = full price.
        assert [e["amount"] for e in session_events] == ["200.00", "600.00"]
        # Finalization fired performed exactly once, with the price suppressed.
        assert len(performed_events) == 1
        assert performed_events[0]["unit_price"] is None
    finally:
        # unsubscribe (not _handlers.pop) — pop would also remove the
        # module handlers registered at startup and poison later tests.
        event_bus.unsubscribe("odontogram.treatment.performed", _capture_performed)
        event_bus.unsubscribe("treatment_plan.item_session_completed", _capture_session)


@pytest.mark.asyncio
async def test_odontogram_perform_first_cancels_pending_sessions(
    client: AsyncClient,
    auth_headers: dict,
    setup_multi_session: dict,
    db_session: AsyncSession,
):
    """Odontogram-first completion books the full price once and closes the session path.

    Performing the treatment directly on the odontogram publishes the
    full ``unit_price`` (NULL-session earned row). The plan item's
    pending sessions must flip to cancelled — completing one later
    would book the same money a second time.
    """
    from app.core.events import event_bus

    performed_events: list[dict] = []

    async def _capture(payload: dict) -> None:
        performed_events.append(payload)

    event_bus.subscribe("odontogram.treatment.performed", _capture)
    try:
        plan_id, item_id, sessions = await _add_multi_session_item(
            client, auth_headers, db_session, setup_multi_session
        )
        item_resp = await client.get(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
            headers=auth_headers,
        )
        treatment_id = next(
            i["treatment_id"] for i in item_resp.json()["data"]["items"] if i["id"] == item_id
        )
        # The handler opens its own DB connection — commit the shared test
        # session so the planned item is visible to it.
        await db_session.commit()
        r = await client.patch(
            f"/api/v1/odontogram/treatments/{treatment_id}/perform",
            headers=auth_headers,
            json={},
        )
        assert r.status_code == 200, r.text
        # Direct odontogram completion keeps the price on the event.
        assert len(performed_events) == 1
        assert performed_events[0]["unit_price"] == "800.00"
        # The plan item completed and its pending sessions were cancelled.
        plan = await client.get(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}",
            headers=auth_headers,
        )
        item = next(i for i in plan.json()["data"]["items"] if i["id"] == item_id)
        assert item["status"] == "completed"
        assert all(s["status"] == "cancelled" for s in item["sessions"])
        # A late session-complete attempt is refused.
        late = await client.patch(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/sessions/{sessions[0]['id']}/complete",
            headers=auth_headers,
            json={},
        )
        assert late.status_code == 400
    finally:
        event_bus.unsubscribe("odontogram.treatment.performed", _capture)


# ---------------------------------------------------------------------------
# Issue #167 — completion gated on plan status; sessions repriced on acceptance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_refused_until_plan_is_active(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup_multi_session: dict
):
    """Both completion endpoints return 400 on draft and pending plans."""
    plan_id, item_id, sessions = await _add_multi_session_item(
        client, auth_headers, db_session, setup_multi_session, activate=False
    )
    session_url = (
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}"
        f"/sessions/{sessions[0]['id']}/complete"
    )
    item_url = f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/complete"

    # draft
    r = await client.patch(session_url, headers=auth_headers, json={})
    assert r.status_code == 400, r.text
    r = await client.patch(
        item_url, headers=auth_headers, json={"completed_without_appointment": True}
    )
    assert r.status_code == 400, r.text

    # pending (confirmed, quote not accepted yet)
    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/confirm", headers=auth_headers, json={}
    )
    assert r.status_code == 200, r.text
    r = await client.patch(session_url, headers=auth_headers, json={})
    assert r.status_code == 400, r.text

    # nothing was booked
    plan = (
        await client.get(f"/api/v1/treatment_plan/treatment-plans/{plan_id}", headers=auth_headers)
    ).json()["data"]
    assert all(s["status"] == "pending" for s in plan["items"][0]["sessions"])


@pytest.mark.asyncio
async def test_accepting_discounted_quote_reprices_pending_sessions(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup_multi_session: dict
):
    """Line 20% + global 10% on an 800 € crown → sessions rescale to 576 € (200:600 ratio kept),
    and the completed-session event carries the discounted amount."""
    from app.core.events import event_bus

    plan_id, item_id, _ = await _add_multi_session_item(
        client, auth_headers, db_session, setup_multi_session, activate=False
    )
    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/confirm", headers=auth_headers, json={}
    )
    budget_id = r.json()["data"]["budget_id"]
    budget = (await client.get(f"/api/v1/budget/budgets/{budget_id}", headers=auth_headers)).json()[
        "data"
    ]
    line = budget["items"][0]
    r = await client.put(
        f"/api/v1/budget/budgets/{budget_id}/items/{line['id']}",
        headers=auth_headers,
        json={"discount_type": "percentage", "discount_value": 20},
    )
    assert r.status_code == 200, r.text
    r = await client.put(
        f"/api/v1/budget/budgets/{budget_id}",
        headers=auth_headers,
        json={"global_discount_type": "percentage", "global_discount_value": 10},
    )
    assert r.status_code == 200, r.text
    await _sync(db_session)
    r = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/accept",
        headers=auth_headers,
        json={"signature": {"signed_by_name": "Rosa Vega", "relationship_to_patient": "patient"}},
    )
    assert r.status_code == 200, r.text
    await _sync(db_session)

    plan = (
        await client.get(f"/api/v1/treatment_plan/treatment-plans/{plan_id}", headers=auth_headers)
    ).json()["data"]
    assert plan["status"] == "active"
    sessions = sorted(plan["items"][0]["sessions"], key=lambda s: s["sequence"])
    amounts = [Decimal(s["amount"]) for s in sessions]
    # 800 → 640 after line 20% → 576 after global 10%; 200:600 ratio → 144 + 432
    assert amounts == [Decimal("144.00"), Decimal("432.00")]

    events: list[dict] = []
    event_bus.subscribe("treatment_plan.item_session_completed", events.append)
    try:
        r = await client.patch(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}"
            f"/sessions/{sessions[0]['id']}/complete",
            headers=auth_headers,
            json={},
        )
        assert r.status_code == 200, r.text
    finally:
        event_bus.unsubscribe("treatment_plan.item_session_completed", events.append)
    assert [e["amount"] for e in events] == ["144.00"]


def test_reprice_sessions_keeps_completed_amounts() -> None:
    """Revive path: a session already booked keeps its amount; the pending
    remainder absorbs the new target (clamped at zero)."""
    from types import SimpleNamespace

    from app.modules.treatment_plan.service import TreatmentPlanService

    tid = uuid4()
    done = SimpleNamespace(status="completed", amount=Decimal("200.00"))
    pend_a = SimpleNamespace(status="pending", amount=Decimal("300.00"))
    pend_b = SimpleNamespace(status="pending", amount=Decimal("300.00"))
    gone = SimpleNamespace(status="cancelled", amount=Decimal("50.00"))
    item = SimpleNamespace(treatment_id=tid, sessions=[done, pend_a, pend_b, gone])
    plan = SimpleNamespace(items=[item])

    TreatmentPlanService._reprice_sessions(plan, {tid: Decimal("500.00")})
    assert done.amount == Decimal("200.00")
    assert gone.amount == Decimal("50.00")
    assert pend_a.amount + pend_b.amount == Decimal("300.00")
    assert pend_a.amount == Decimal("150.00")

    # Odd cents land on the last pending session.
    TreatmentPlanService._reprice_sessions(plan, {tid: Decimal("200.01")})
    assert pend_a.amount == Decimal("0.00") and pend_b.amount == Decimal("0.01")

    # Unknown treatment → untouched.
    TreatmentPlanService._reprice_sessions(plan, {uuid4(): Decimal("1.00")})
    assert pend_b.amount == Decimal("0.01")
