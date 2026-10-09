"""T1 public-route audit: adversarial scoping pins per surface.

Budget public links (token + per-token cookie), notifications
push-subscribe (single-use token), leads intake and integrations API
are covered for their shapes here; leads and integrations keep their
deep suites in tests/modules/{leads,test_intake.py} and
tests/modules/integrations/test_public_api.py — this file pins the
cross-surface failure contract (no oracle, no cross-clinic read) and
the two surfaces that had no HTTP-level coverage (budget, push).

Slowapi limits are production-only and deliberately unasserted.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.modules.budget.models import Budget
from app.modules.integrations.service import IntegrationsService
from app.modules.notifications.models import PushSubscription
from app.modules.notifications.push import PushSubscribeTokenService
from app.modules.patients.models import Patient

BUDGET = "/api/v1/budget/public/budgets"
PUSH = "/api/v1/notifications/public/push/subscribe"
INTAKE = "/api/v1/leads/public/intake"
IPATIENTS = "/api/v1/integrations/public/patients"

SUB_KEYS = {"p256dh": "BNc-test-key", "auth": "test-auth-secret"}
ENDPOINT = "https://push.example.test/sub/1"


async def _staff(db: AsyncSession, clinic_id: UUID) -> User:
    user = User(
        id=uuid4(),
        email=f"t1-{uuid4().hex[:8]}@test.clinic",
        password_hash="not-a-real-hash",
        first_name="T1",
        last_name="Staff",
    )
    db.add(user)
    await db.flush()
    db.add(ClinicMembership(user_id=user.id, clinic_id=clinic_id, role="admin"))
    await db.commit()
    return user


async def _patient(db: AsyncSession, clinic_id: UUID, **overrides) -> Patient:
    data = {
        "first_name": "Pub",
        "last_name": "Lic",
        "phone": "+34600111222",  # last4 "1222" for the budget knowledge factor
        "email": "public@example.com",
    }
    data.update(overrides)
    patient = Patient(id=uuid4(), clinic_id=clinic_id, **data)
    db.add(patient)
    await db.commit()
    return patient


async def _budget(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID, user_id: UUID, **overrides
) -> Budget:
    data = {
        "clinic_id": clinic_id,
        "patient_id": patient_id,
        "budget_number": f"T1-{uuid4().hex[:6]}",
        "status": "sent",
        "valid_from": date.today() - timedelta(days=1),
        "valid_until": date.today() + timedelta(days=30),
        "created_by": user_id,
        "total": Decimal("100.00"),
    }
    data.update(overrides)
    budget = Budget(**data)
    db.add(budget)
    await db.commit()
    return budget


@pytest_asyncio.fixture
async def t1_setup(db_session: AsyncSession, test_clinic: Clinic) -> dict:
    """Clinic + staff + patient + a verifiable budget (phone_last4)."""
    user = await _staff(db_session, test_clinic.id)
    patient = await _patient(db_session, test_clinic.id)
    budget = await _budget(db_session, test_clinic.id, patient.id, user.id)
    return {"clinic": test_clinic, "user": user, "patient": patient, "budget": budget}


# ---------------------------------------------------------------------------
# Budget public links
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_unknown_token_meta_404(client: AsyncClient) -> None:
    response = await client.get(f"{BUDGET}/{uuid4()}/meta")
    assert response.status_code == 404
    assert response.json()["message"] == "Budget link not found"


@pytest.mark.asyncio
async def test_budget_unknown_token_detail_404(client: AsyncClient) -> None:
    response = await client.get(f"{BUDGET}/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["message"] == "Budget link not found"


@pytest.mark.asyncio
async def test_budget_bad_verify_value_401(client: AsyncClient, t1_setup: dict) -> None:
    budget = t1_setup["budget"]
    response = await client.post(
        f"{BUDGET}/{budget.public_token}/verify",
        json={"method": "phone_last4", "value": "0000"},
    )
    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_budget_verify_correct_value_sets_cookie(client: AsyncClient, t1_setup: dict) -> None:
    budget = t1_setup["budget"]
    response = await client.post(
        f"{BUDGET}/{budget.public_token}/verify",
        json={"method": "phone_last4", "value": "1222"},
    )
    assert response.status_code == 204, response.text
    assert f"bdg_session_{budget.public_token}" in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_budget_verify_decided_409(
    client: AsyncClient, db_session: AsyncSession, t1_setup: dict
) -> None:
    budget = t1_setup["budget"]
    budget.status = "accepted"
    await db_session.commit()
    response = await client.post(
        f"{BUDGET}/{budget.public_token}/verify",
        json={"method": "phone_last4", "value": "1222"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_budget_expired_detail_410(
    client: AsyncClient, db_session: AsyncSession, t1_setup: dict
) -> None:
    budget = t1_setup["budget"]
    budget.public_auth_method = "none"
    # UTC: the route compares against datetime.now(UTC).date()
    # (budget/public_router.py:328). A local "yesterday" east of UTC is
    # that same day, so the link reads as live and answers 200.
    budget.valid_until = datetime.now(UTC).date() - timedelta(days=1)
    await db_session.commit()
    response = await client.get(f"{BUDGET}/{budget.public_token}")
    assert response.status_code == 410


@pytest.mark.asyncio
async def test_budget_locked_verify_423(
    client: AsyncClient, db_session: AsyncSession, t1_setup: dict
) -> None:
    budget = t1_setup["budget"]
    budget.public_locked_at = datetime.now(UTC)
    await db_session.commit()
    response = await client.post(
        f"{BUDGET}/{budget.public_token}/verify",
        json={"method": "phone_last4", "value": "1222"},
    )
    assert response.status_code == 423


@pytest.mark.asyncio
async def test_budget_cookie_for_other_budget_401(
    client: AsyncClient, db_session: AsyncSession, t1_setup: dict
) -> None:
    clinic, patient, user = t1_setup["clinic"], t1_setup["patient"], t1_setup["user"]
    budget_a = t1_setup["budget"]
    budget_b = await _budget(db_session, clinic.id, patient.id, user.id)
    verify = await client.post(
        f"{BUDGET}/{budget_a.public_token}/verify",
        json={"method": "phone_last4", "value": "1222"},
    )
    assert verify.status_code == 204
    # Re-key A's session under B's cookie name so the `tok` claim check
    # (not just the per-token cookie name) is what rejects it.
    value = verify.headers["set-cookie"].split(";")[0].split("=", 1)[1]
    cookie = f"bdg_session_{budget_b.public_token}={value}"
    response = await client.get(f"{BUDGET}/{budget_b.public_token}", headers={"Cookie": cookie})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_budget_meta_returns_scoped_patient_name(client: AsyncClient, t1_setup: dict) -> None:
    """The /meta patient lookup is clinic-scoped: the budget's own patient
    resolves, so the checklist point-3 filter cannot silently blank the
    name on a same-clinic row."""
    budget = t1_setup["budget"]
    response = await client.get(f"{BUDGET}/{budget.public_token}/meta")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["patient_first_name"] == "Pub"


@pytest.mark.asyncio
async def test_budget_none_method_needs_no_cookie(
    client: AsyncClient, db_session: AsyncSession, t1_setup: dict
) -> None:
    budget = t1_setup["budget"]
    budget.public_auth_method = "none"
    await db_session.commit()
    response = await client.get(f"{BUDGET}/{budget.public_token}")
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# Notifications push-subscribe
# ---------------------------------------------------------------------------


async def _mint_push(db: AsyncSession, clinic_id: UUID, patient_id: UUID):
    row = await PushSubscribeTokenService.mint(db, clinic_id, patient_id)
    await db.commit()
    return row


@pytest.mark.asyncio
async def test_push_unknown_token_404(client: AsyncClient) -> None:
    assert (await client.get(f"{PUSH}/{uuid4()}")).status_code == 404
    response = await client.post(
        f"{PUSH}/{uuid4()}",
        json={"endpoint": ENDPOINT, "keys": SUB_KEYS},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_push_redeem_single_use(
    client: AsyncClient, db_session: AsyncSession, t1_setup: dict
) -> None:
    clinic, patient = t1_setup["clinic"], t1_setup["patient"]
    row = await _mint_push(db_session, clinic.id, patient.id)
    payload = {"endpoint": ENDPOINT, "keys": SUB_KEYS}
    first = await client.post(f"{PUSH}/{row.token}", json=payload)
    assert first.status_code == 201, first.text
    second = await client.post(f"{PUSH}/{row.token}", json=payload)
    assert second.status_code == 404


@pytest.mark.asyncio
async def test_push_expired_token_404(
    client: AsyncClient, db_session: AsyncSession, t1_setup: dict
) -> None:
    clinic, patient = t1_setup["clinic"], t1_setup["patient"]
    row = await _mint_push(db_session, clinic.id, patient.id)
    row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.commit()
    assert (await client.get(f"{PUSH}/{row.token}")).status_code == 404


@pytest.mark.asyncio
async def test_push_redeem_binds_token_patient(
    client: AsyncClient, db_session: AsyncSession, t1_setup: dict
) -> None:
    clinic, patient = t1_setup["clinic"], t1_setup["patient"]
    row = await _mint_push(db_session, clinic.id, patient.id)
    response = await client.post(
        f"{PUSH}/{row.token}", json={"endpoint": ENDPOINT, "keys": SUB_KEYS}
    )
    assert response.status_code == 201, response.text
    stored = (
        await db_session.execute(
            select(PushSubscription).where(
                PushSubscription.clinic_id == clinic.id,
                PushSubscription.endpoint == ENDPOINT,
            )
        )
    ).scalar_one()
    assert stored.patient_id == patient.id


# ---------------------------------------------------------------------------
# Cross-surface: no oracle in failure bodies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_credentials_share_generic_shapes(
    client: AsyncClient, t1_setup: dict
) -> None:
    clinic = t1_setup["clinic"]
    bodies = {}

    bodies["budget"] = (await client.get(f"{BUDGET}/{uuid4()}/meta")).json()["message"]
    bodies["push"] = (await client.get(f"{PUSH}/{uuid4()}")).json()["message"]
    bodies["leads"] = (
        await client.post(
            INTAKE,
            json={
                "full_name": "Nadie",
                "phone": "+34000000000",
                "email": "nadie@example.com",
                "motive": "Presupuesto",
                "description": "Viene de la web.",
                "availability_days": ["mon"],
                "availability_slot": "morning",
            },
            headers={"X-Lead-Key": "lk_missing"},
        )
    ).json()["message"]
    bodies["integrations"] = (
        await client.get(IPATIENTS, headers={"Authorization": "Bearer wrong-token"})
    ).json()["message"]

    assert bodies["budget"] == "Budget link not found"
    assert bodies["push"] == "Invalid or expired subscribe token"
    assert bodies["leads"] == "Invalid intake key"
    assert bodies["integrations"] == "Invalid token."
    joined = " ".join(bodies.values()).lower()
    assert "clinic" not in joined
    assert "patient" not in joined
    assert str(clinic.id) not in joined


@pytest.mark.asyncio
async def test_integration_token_cannot_read_foreign_patient(
    client: AsyncClient, db_session: AsyncSession, t1_setup: dict
) -> None:
    clinic = t1_setup["clinic"]
    other = Clinic(id=uuid4(), name="Foreign", tax_id="B00000000", address={}, settings={})
    db_session.add(other)
    await db_session.flush()
    foreign = Patient(id=uuid4(), clinic_id=other.id, first_name="F", last_name="X")
    db_session.add(foreign)
    await db_session.commit()

    _, plaintext = await IntegrationsService.create_token(
        db_session, clinic.id, {"name": "t1", "scopes": ["patients:read"]}
    )
    response = await client.get(
        f"{IPATIENTS}/{foreign.id}",
        headers={"Authorization": f"Bearer {plaintext}"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Public-link hardening (#531, #538, #540)
# ---------------------------------------------------------------------------


async def _seed_failures(
    db_session: AsyncSession, budget_id: UUID, ip_hash: str, count: int
) -> None:
    """Old failed attempts (outside the 15-minute window)."""
    from app.modules.budget.models import BudgetAccessLog

    old = datetime.now(UTC) - timedelta(hours=1)
    for _ in range(count):
        db_session.add(
            BudgetAccessLog(
                budget_id=budget_id,
                ip_hash=ip_hash,
                success=False,
                method_attempted="phone_last4",
                attempted_at=old,
            )
        )
    await db_session.commit()


@pytest.mark.asyncio
async def test_total_lockout_counts_every_ip(db_session: AsyncSession, t1_setup: dict) -> None:
    """The permanent lockout stays budget-wide: failures from any IPs add up (#531)."""
    from app.modules.budget.workflow import BudgetWorkflowService

    budget = t1_setup["budget"]
    await _seed_failures(db_session, budget.id, "attacker-ip-a", 5)
    await _seed_failures(db_session, budget.id, "attacker-ip-b", 4)
    ok, code = await BudgetWorkflowService.verify_public_access(
        db_session, budget, "phone_last4", "0000", "attacker-ip-c"
    )
    assert (ok, code) == (False, "locked")
    assert budget.public_locked_at is not None


@pytest.mark.asyncio
async def test_unlock_clears_failure_counter(db_session: AsyncSession, t1_setup: dict) -> None:
    """Unlocked links stay unlocked: the counter rows go with the flag (#531)."""
    from app.modules.budget.workflow import BudgetWorkflowService

    budget = t1_setup["budget"]
    await _seed_failures(db_session, budget.id, "attacker-ip", 9)
    ok, code = await BudgetWorkflowService.verify_public_access(
        db_session, budget, "phone_last4", "0000", "attacker-ip"
    )
    assert (ok, code) == (False, "locked")
    await BudgetWorkflowService.unlock_public(db_session, budget)
    assert budget.public_locked_at is None
    ok, code = await BudgetWorkflowService.verify_public_access(
        db_session, budget, "phone_last4", "0000", "attacker-ip"
    )
    assert (ok, code) == (False, "invalid")
    assert budget.public_locked_at is None


@pytest.mark.asyncio
async def test_unlock_records_staff_history(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    t1_setup: dict,
) -> None:
    """Staff unlocks leave a history entry even though failed rows are removed (#531)."""
    from app.modules.budget.models import BudgetAccessLog, BudgetHistory

    budget = t1_setup["budget"]
    budget_id = budget.id
    clinic_id = t1_setup["clinic"].id
    staff_id = UUID(
        (await client.get("/api/v1/auth/me", headers=auth_headers)).json()["data"]["user"]["id"]
    )
    await _seed_failures(db_session, budget_id, "attacker-ip", 9)
    budget.public_locked_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/unlock-public",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    await _seed_failures(db_session, budget_id, "attacker-ip", 9)
    response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/unlock-public",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    entries = (
        (
            await db_session.execute(
                select(BudgetHistory).where(
                    BudgetHistory.budget_id == budget_id,
                    BudgetHistory.action == "public_lock_cleared",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(entries) == 2
    assert {entry.changed_by for entry in entries} == {staff_id}
    assert {entry.clinic_id for entry in entries} == {clinic_id}
    assert sorted(entry.previous_state["locked"] for entry in entries) == [False, True]
    assert {entry.new_state["locked"] for entry in entries} == {False}

    failures = (
        (
            await db_session.execute(
                select(BudgetAccessLog).where(
                    BudgetAccessLog.budget_id == budget_id,
                    BudgetAccessLog.success.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    assert failures == []


@pytest.mark.asyncio
async def test_correct_guess_succeeds_despite_old_failures(
    db_session: AsyncSession, t1_setup: dict
) -> None:
    """Old failures never block the legitimate patient: only failures count (#531)."""
    from app.modules.budget.workflow import BudgetWorkflowService

    clinic, patient, user = t1_setup["clinic"], t1_setup["patient"], t1_setup["user"]
    budget = await _budget(db_session, clinic.id, patient.id, user.id)
    await _seed_failures(db_session, budget.id, "attacker-ip", 9)
    ok, code = await BudgetWorkflowService.verify_public_access(
        db_session, budget, "phone_last4", "1222", "patient-ip"
    )
    assert (ok, code) == (True, None)
    assert budget.public_locked_at is None


def test_public_secret_hard_required_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """No key in production refuses to sign; dev still falls back (#538)."""
    from app.config import settings
    from app.modules.budget.public_router import _public_secret

    monkeypatch.setattr(settings, "BUDGET_PUBLIC_SECRET_KEY", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(RuntimeError):
        _public_secret()
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert _public_secret() == settings.SECRET_KEY
    monkeypatch.setattr(settings, "BUDGET_PUBLIC_SECRET_KEY", " " * 32)
    assert _public_secret() == settings.SECRET_KEY


async def _verified_cookie(client: AsyncClient, budget: Budget) -> str:
    verify = await client.post(
        f"{BUDGET}/{budget.public_token}/verify",
        json={"method": "phone_last4", "value": "1222"},
    )
    assert verify.status_code == 204, verify.text
    value = verify.headers["set-cookie"].split(";")[0].split("=", 1)[1]
    return f"bdg_session_{budget.public_token}={value}"


@pytest.mark.asyncio
async def test_reject_logs_access_row(
    client: AsyncClient, db_session: AsyncSession, t1_setup: dict
) -> None:
    """Reject decisions land in BudgetAccessLog like the other actions (#540)."""
    from app.modules.budget.models import BudgetAccessLog

    budget = t1_setup["budget"]
    cookie = await _verified_cookie(client, budget)
    response = await client.post(
        f"{BUDGET}/{budget.public_token}/reject",
        json={"reason": "price"},
        headers={"Cookie": cookie},
    )
    assert response.status_code == 200, response.text
    row = (
        await db_session.execute(
            select(BudgetAccessLog).where(
                BudgetAccessLog.budget_id == budget.id,
                BudgetAccessLog.method_attempted == "reject",
            )
        )
    ).scalar_one()
    assert row.success is True


@pytest.mark.asyncio
async def test_accept_logs_access_row(
    client: AsyncClient, db_session: AsyncSession, t1_setup: dict
) -> None:
    """Accept decisions land in BudgetAccessLog like the other actions (#540)."""
    from app.modules.budget.models import BudgetAccessLog, BudgetItem
    from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory

    clinic, user = t1_setup["clinic"], t1_setup["user"]
    clinic_id, user_id = clinic.id, user.id
    patient = await _patient(db_session, clinic_id)
    patient_id = patient.id
    budget = await _budget(db_session, clinic_id, patient_id, user_id)
    budget_id = budget.id
    category = TreatmentCategory(id=uuid4(), clinic_id=clinic_id, key=f"t1-{uuid4().hex[:6]}")
    db_session.add(category)
    await db_session.flush()
    catalog_item = TreatmentCatalogItem(
        id=uuid4(),
        clinic_id=clinic_id,
        category_id=category.id,
        internal_code=f"T1-{uuid4().hex[:6]}",
    )
    db_session.add(catalog_item)
    await db_session.flush()
    db_session.add(
        BudgetItem(
            id=uuid4(),
            clinic_id=clinic_id,
            budget_id=budget_id,
            catalog_item_id=catalog_item.id,
            unit_price=Decimal("60.00"),
            quantity=1,
            vat_rate=0.0,
            line_subtotal=Decimal("60.00"),
            line_discount=Decimal("0.00"),
            line_tax=Decimal("0.00"),
            line_total=Decimal("60.00"),
        )
    )
    await db_session.commit()
    cookie = await _verified_cookie(client, budget)
    response = await client.post(
        f"{BUDGET}/{budget.public_token}/accept",
        json={"signer_name": "Pub Lic"},
        headers={"Cookie": cookie},
    )
    assert response.status_code == 200, response.text
    row = (
        await db_session.execute(
            select(BudgetAccessLog).where(
                BudgetAccessLog.budget_id == budget.id,
                BudgetAccessLog.method_attempted == "accept",
            )
        )
    ).scalar_one()
    assert row.success is True
