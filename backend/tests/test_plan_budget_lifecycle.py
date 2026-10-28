"""Cross-module round-trips for the plan ↔ budget lifecycle (issue #162).

Harness note: the plan ↔ budget handlers are transactional (ADR 0019) — they
run on the publisher's session, so they see the request's own writes and the
test sees theirs. ``_sync`` remains for the events still handled
own-session (patient_timeline and friends): it commits so those handlers can
see the rows, and expires so the test session picks up their writes instead
of stale identity-map state.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.core.events import event_bus
from app.modules.budget.models import Budget
from app.modules.treatment_plan.models import TreatmentPlan
from tests.test_treatment_plan import (
    _create_plan_with_items,
    _create_treatment,
    _seed_catalog_crown,
)


@pytest.fixture
async def setup(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> dict:
    """Clinic + admin membership + patient + catalog item.

    Admin role (wildcard) so the test can drive both modules' endpoints
    (confirm/reactivate on plans, renegotiate/resend on budgets).
    """
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    clinic = Clinic(
        id=uuid4(),
        name="Lifecycle Clinic",
        tax_id="B16216216",
        address={"street": "a", "city": "b"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(ClinicMembership(id=uuid4(), user_id=user_id, clinic_id=clinic.id, role="admin"))
    await db_session.commit()

    patient_resp = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Rosa", "last_name": "Vega", "phone": "+34666555444"},
    )
    ctx = {
        "clinic_id": str(clinic.id),
        "user_id": user_id,
        "patient_id": patient_resp.json()["data"]["id"],
    }
    ctx["crown_id"] = await _seed_catalog_crown(db_session, clinic.id)
    return ctx


async def _sync(db_session: AsyncSession) -> None:
    """Commit the test session and drop cached ORM state (see module docstring)."""
    await db_session.commit()
    db_session.expire_all()


async def _get_plan(client: AsyncClient, auth_headers: dict, plan_id: str) -> dict:
    r = await client.get(f"/api/v1/treatment_plan/treatment-plans/{plan_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _confirm_plan(client: AsyncClient, auth_headers: dict, plan_id: str) -> str:
    """Confirm the plan (draft → pending) and return the linked budget id."""
    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/confirm", headers=auth_headers
    )
    assert r.status_code == 200, r.text
    budget_id = (await _get_plan(client, auth_headers, plan_id))["budget_id"]
    assert budget_id, "confirm should have created a draft budget"
    return budget_id


async def _send_budget(client: AsyncClient, auth_headers: dict, budget_id: str) -> None:
    r = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/send",
        headers=auth_headers,
        json={"send_email": False},
    )
    assert r.status_code == 200, r.text


async def _reject_budget(client: AsyncClient, auth_headers: dict, budget_id: str) -> None:
    r = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/reject",
        headers=auth_headers,
        json={"signature": {"signed_by_name": "Rosa Vega", "relationship_to_patient": "patient"}},
    )
    assert r.status_code == 200, r.text


async def _accept_budget(client: AsyncClient, auth_headers: dict, budget_id: str) -> None:
    r = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/accept",
        headers=auth_headers,
        json={"signature": {"signed_by_name": "Rosa Vega", "relationship_to_patient": "patient"}},
    )
    assert r.status_code == 200, r.text


class _Spy:
    """Collect payloads for one event type; use as a context manager."""

    def __init__(self, event_type: str) -> None:
        self.event_type = event_type
        self.captured: list[dict] = []

    def __enter__(self) -> "_Spy":
        event_bus.subscribe(self.event_type, self.captured.append)
        return self

    def __exit__(self, *exc: object) -> None:
        event_bus.unsubscribe(self.event_type, self.captured.append)


# ---------------------------------------------------------------------------
# Bug 1 — reactivated / renegotiated plans must get a fresh quote
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_reactivate_confirm_creates_new_budget(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    old_budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)

    await _send_budget(client, auth_headers, old_budget_id)
    await _reject_budget(client, auth_headers, old_budget_id)
    await _sync(db_session)

    plan = await _get_plan(client, auth_headers, plan_id)
    assert plan["status"] == "closed", "budget.rejected should close the plan"

    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/reactivate", headers=auth_headers
    )
    assert r.status_code == 200, r.text

    new_budget_id = await _confirm_plan(client, auth_headers, plan_id)
    assert new_budget_id != old_budget_id, "re-confirm must produce a fresh quote"

    # The rejected budget survives untouched for history.
    r = await client.get(f"/api/v1/budget/budgets/{old_budget_id}", headers=auth_headers)
    assert r.json()["data"]["status"] == "rejected"

    # Patient-side budget lists show the plan link via the denormalized
    # snapshot (issue #184).
    r = await client.get(
        f"/api/v1/budget/budgets?patient_id={setup['patient_id']}", headers=auth_headers
    )
    assert r.status_code == 200, r.text
    plan_number = plan["plan_number"]
    assert {b["plan_number_snapshot"] for b in r.json()["data"]} == {plan_number}


@pytest.mark.asyncio
async def test_renegotiate_then_confirm_relinks(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Renegotiation reopens the plan (via the handler — must not hang)
    and re-confirming links the plan to the fresh budget."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    old_budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)

    await _send_budget(client, auth_headers, old_budget_id)
    r = await client.post(
        f"/api/v1/budget/budgets/{old_budget_id}/renegotiate", headers=auth_headers, json={}
    )
    assert r.status_code == 200, r.text
    await _sync(db_session)

    plan = await _get_plan(client, auth_headers, plan_id)
    assert plan["status"] == "draft", "budget.renegotiated should reopen the plan"

    new_budget_id = await _confirm_plan(client, auth_headers, plan_id)
    assert new_budget_id != old_budget_id, "confirm after renegotiation must relink"


@pytest.mark.asyncio
async def test_item_add_allowed_on_plan_with_rejected_budget(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """A terminal budget is dead paper — it must not lock the plan."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)

    await _send_budget(client, auth_headers, budget_id)
    await _reject_budget(client, auth_headers, budget_id)
    await _sync(db_session)

    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/reactivate", headers=auth_headers
    )
    assert r.status_code == 200, r.text

    treatment_id = await _create_treatment(client, auth_headers, setup, tooth_number=15)
    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/items",
        headers=auth_headers,
        json={"treatment_id": treatment_id},
    )
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# Bug 2 — resend must relink the plan; accepting V2 must reactivate it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resend_relinks_plan_and_versions(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    old_budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)
    await _send_budget(client, auth_headers, old_budget_id)
    await _reject_budget(client, auth_headers, old_budget_id)
    await _sync(db_session)

    with _Spy("budget.superseded") as spy:
        r = await client.post(
            f"/api/v1/budget/budgets/{old_budget_id}/resend", headers=auth_headers
        )
    assert r.status_code == 200, r.text
    new_budget = r.json()["data"]
    assert new_budget["version"] == 2
    assert new_budget["parent_budget_id"] == old_budget_id

    assert len(spy.captured) == 1
    payload = spy.captured[0]
    assert payload["budget_id"] == old_budget_id
    assert payload["new_budget_id"] == new_budget["id"]
    assert payload["plan_id"] == plan_id

    await _sync(db_session)
    plan = await _get_plan(client, auth_headers, plan_id)
    assert plan["budget_id"] == new_budget["id"], "plan link must follow the new version"

    # The clone refreshes the plan-status snapshot from the live plan.
    row = await db_session.get(Budget, UUID(new_budget["id"]))
    assert row is not None and row.plan_status_snapshot == "closed"


@pytest.mark.asyncio
async def test_accept_resent_budget_reactivates_rejected_plan(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    old_budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)
    await _send_budget(client, auth_headers, old_budget_id)
    await _reject_budget(client, auth_headers, old_budget_id)
    await _sync(db_session)

    r = await client.post(f"/api/v1/budget/budgets/{old_budget_id}/resend", headers=auth_headers)
    new_budget_id = r.json()["data"]["id"]
    await _sync(db_session)

    await _send_budget(client, auth_headers, new_budget_id)
    with _Spy("treatment_plan.reactivated") as spy:
        await _accept_budget(client, auth_headers, new_budget_id)
    await _sync(db_session)

    plan = await _get_plan(client, auth_headers, plan_id)
    assert plan["status"] == "active", "accepting the new version must revive the plan"
    assert len(spy.captured) == 1
    assert spy.captured[0]["previous_closure_reason"] == "rejected_by_patient"

    # Closure fields cleared, original confirmation kept (not in the
    # response schema — check the row).
    row = await db_session.get(TreatmentPlan, UUID(plan_id))
    assert row is not None
    assert row.closure_reason is None
    assert row.closed_at is None
    assert row.confirmed_at is not None, "original confirmation stands"


@pytest.mark.asyncio
async def test_accept_resent_budget_noop_for_other_closure_reasons(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Plans the clinic closed on purpose stay closed."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)
    await _send_budget(client, auth_headers, budget_id)

    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/close",
        headers=auth_headers,
        json={"closure_reason": "patient_abandoned"},
    )
    assert r.status_code == 200, r.text
    # Commit the close before cancelling: in production these are
    # separate requests; without it the cancel handler would see the
    # plan as still-pending and block on our uncommitted plan row.
    await _sync(db_session)
    r = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/cancel", headers=auth_headers, json={}
    )
    assert r.status_code == 200, r.text
    await _sync(db_session)

    r = await client.post(f"/api/v1/budget/budgets/{budget_id}/resend", headers=auth_headers)
    new_budget_id = r.json()["data"]["id"]
    await _sync(db_session)

    await _send_budget(client, auth_headers, new_budget_id)
    await _accept_budget(client, auth_headers, new_budget_id)
    await _sync(db_session)

    plan = await _get_plan(client, auth_headers, plan_id)
    assert plan["status"] == "closed"
    row = await db_session.get(TreatmentPlan, UUID(plan_id))
    assert row is not None and row.closure_reason == "patient_abandoned"


@pytest.mark.asyncio
async def test_resend_requires_terminal_status(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)
    await _send_budget(client, auth_headers, budget_id)

    r = await client.post(f"/api/v1/budget/budgets/{budget_id}/resend", headers=auth_headers)
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_resending_a_terminal_budget_twice_does_not_500(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """The second resend took `cloned.version + 1`, which was taken.

    `clone_to_new_draft` derived the new version from the row it was
    cloning, while `BudgetService.duplicate_budget` derived it from
    `max(version)`. So a terminal budget stayed resendable after its
    resend had already produced the next version, and the second call hit
    `uq_budget_clinic_number_version` — a 500 with the INSERT statement in
    the response body. Both paths now go through
    `BudgetService.next_version`.
    """
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)
    await _send_budget(client, auth_headers, budget_id)
    await _reject_budget(client, auth_headers, budget_id)
    await _sync(db_session)

    first = await client.post(f"/api/v1/budget/budgets/{budget_id}/resend", headers=auth_headers)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["version"] == 2
    await _sync(db_session)

    # The original is still rejected, so the route still accepts it. It
    # must allocate the next *free* version rather than collide on 2.
    second = await client.post(f"/api/v1/budget/budgets/{budget_id}/resend", headers=auth_headers)
    assert second.status_code == 200, second.text
    assert second.json()["data"]["version"] == 3
    assert second.json()["data"]["parent_budget_id"] == budget_id

    versions = await client.get(
        f"/api/v1/budget/budgets/{budget_id}/versions", headers=auth_headers
    )
    assert versions.status_code == 200, versions.text
    chain = versions.json()["data"]
    assert sorted(v["version"] for v in chain["versions"]) == [1, 2, 3]
    # `current_version` is the version of the row that was asked about
    # (v1 here), not the newest in the chain — unchanged by this fix.
    assert chain["current_version"] == 1


@pytest.mark.asyncio
async def test_next_version_reads_the_whole_chain(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """`next_version` is max+1 over the budget number, not per-row."""
    from app.modules.budget.service import BudgetService

    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)
    row = await db_session.get(Budget, UUID(budget_id))
    assert row is not None

    assert await BudgetService.next_version(db_session, row.clinic_id, row.budget_number) == 2
    # An unrelated budget number starts at 1, so the lookup is scoped.
    assert await BudgetService.next_version(db_session, row.clinic_id, "PRES-NOPE-0000") == 1


@pytest.mark.asyncio
async def test_on_budget_superseded_idempotent(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """The handler only relinks while the plan still points at the old
    budget — a stale/replayed event is a no-op."""
    from app.modules.treatment_plan.events import on_budget_superseded

    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)

    await on_budget_superseded(
        {
            "clinic_id": setup["clinic_id"],
            "plan_id": plan_id,
            "budget_id": str(uuid4()),  # not the budget the plan points at
            "new_budget_id": str(uuid4()),
        },
        db=db_session,
    )
    db_session.expire_all()
    plan = await _get_plan(client, auth_headers, plan_id)
    assert plan["budget_id"] == budget_id, "mismatched supersede must not relink"


# ---------------------------------------------------------------------------
# Bug 3 — direct cancel must notify the plan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_direct_cancel_reopens_pending_plan(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)
    await _send_budget(client, auth_headers, budget_id)

    with _Spy("budget.cancelled") as spy:
        r = await client.post(
            f"/api/v1/budget/budgets/{budget_id}/cancel", headers=auth_headers, json={}
        )
    assert r.status_code == 200, r.text
    assert len(spy.captured) == 1
    assert spy.captured[0]["plan_id"] == plan_id
    await _sync(db_session)

    plan = await _get_plan(client, auth_headers, plan_id)
    assert plan["status"] == "draft", "cancelling the quote must reopen the pending plan"


@pytest.mark.asyncio
async def test_cancel_standalone_budget_is_noop(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    r = await client.post(
        "/api/v1/budget/budgets",
        headers=auth_headers,
        json={"patient_id": setup["patient_id"], "valid_from": "2026-01-01"},
    )
    budget_id = r.json()["data"]["id"]
    await _sync(db_session)

    with _Spy("budget.cancelled") as spy:
        r = await client.post(
            f"/api/v1/budget/budgets/{budget_id}/cancel", headers=auth_headers, json={}
        )
    assert r.status_code == 200, r.text
    assert len(spy.captured) == 1
    assert spy.captured[0]["plan_id"] is None


@pytest.mark.asyncio
async def test_reopen_publishes_no_budget_cancelled(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Plan-initiated reopen owns the transition — no echo event."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)
    await _send_budget(client, auth_headers, budget_id)

    with _Spy("budget.cancelled") as spy:
        r = await client.post(
            f"/api/v1/treatment_plan/treatment-plans/{plan_id}/reopen", headers=auth_headers
        )
    assert r.status_code == 200, r.text
    assert spy.captured == []
    await _sync(db_session)

    plan = await _get_plan(client, auth_headers, plan_id)
    assert plan["status"] == "draft"
    r = await client.get(f"/api/v1/budget/budgets/{budget_id}", headers=auth_headers)
    assert r.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_reopen_with_expired_budget_does_not_500(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """expired → cancelled is not a valid transition; reopen must skip
    the cancel instead of raising."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)

    budget = await db_session.get(Budget, UUID(budget_id))
    assert budget is not None
    budget.status = "expired"
    await _sync(db_session)

    r = await client.post(
        f"/api/v1/treatment_plan/treatment-plans/{plan_id}/reopen", headers=auth_headers
    )
    assert r.status_code == 200, r.text
    plan = await _get_plan(client, auth_headers, plan_id)
    assert plan["status"] == "draft"

    result = await db_session.execute(select(Budget.status).where(Budget.id == UUID(budget_id)))
    assert result.scalar_one() == "expired", "terminal budget must be left alone"


# ---------------------------------------------------------------------------
# Atomicity — plan and budget agree or neither moves (issue #183)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_acceptance_rolls_back_when_the_plan_cannot_activate(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The plan activation used to run on its own session with the error
    logged and swallowed: the budget ended up accepted next to a plan that
    never activated, and nothing surfaced it."""
    from app.modules.treatment_plan.service import TreatmentPlanService

    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)
    await _send_budget(client, auth_headers, budget_id)
    await _sync(db_session)

    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("plan activation failed")

    monkeypatch.setattr(TreatmentPlanService, "accept_from_budget", _boom)

    with pytest.raises(RuntimeError, match="plan activation failed"):
        await client.post(
            f"/api/v1/budget/budgets/{budget_id}/accept",
            headers=auth_headers,
            json={
                "signature": {
                    "signed_by_name": "Rosa Vega",
                    "relationship_to_patient": "patient",
                }
            },
        )

    await db_session.rollback()
    status = await db_session.scalar(select(Budget.status).where(Budget.id == UUID(budget_id)))
    assert status == "sent", "a failed plan activation must not leave the budget accepted"


@pytest.mark.asyncio
async def test_update_response_keeps_the_linked_plan(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """PUT must carry ``treatment_plan`` like GET does.

    The detail page replaces its budget with the PUT response; without the
    link it dropped the "lines are managed by the plan" notice and showed
    add/remove controls until a reload.
    """
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)

    r = await client.put(
        f"/api/v1/budget/budgets/{budget_id}",
        headers=auth_headers,
        json={"patient_notes": "Edited"},
    )
    assert r.status_code == 200, r.text
    linked = r.json()["data"]["treatment_plan"]
    assert linked is not None, "PUT response lost the linked plan"
    assert linked["id"] == plan_id


@pytest.mark.asyncio
async def test_plan_linked_budget_cannot_be_deleted(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Deleting the plan's quote hid it while the plan still pointed at it."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)

    # Even while still a draft, the quote belongs to the plan.
    r = await client.delete(f"/api/v1/budget/budgets/{budget_id}", headers=auth_headers)
    assert r.status_code == 409, r.text

    await _send_budget(client, auth_headers, budget_id)
    await _accept_budget(client, auth_headers, budget_id)
    await _sync(db_session)
    r = await client.delete(f"/api/v1/budget/budgets/{budget_id}", headers=auth_headers)
    assert r.status_code == 409, r.text

    r = await client.get(f"/api/v1/budget/budgets/{budget_id}", headers=auth_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_reconfirm_does_not_relink_an_already_deleted_budget(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, setup: dict
) -> None:
    """Rows deleted before the guard existed: confirm must provision a new quote."""
    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    budget_id = await _confirm_plan(client, auth_headers, plan_id)
    await _sync(db_session)
    await _send_budget(client, auth_headers, budget_id)
    await _accept_budget(client, auth_headers, budget_id)
    await _sync(db_session)

    budget = await db_session.get(Budget, UUID(budget_id))
    budget.deleted_at = datetime.now(UTC)
    await _sync(db_session)

    base = f"/api/v1/treatment_plan/treatment-plans/{plan_id}"
    r = await client.post(f"{base}/close", headers=auth_headers, json={"closure_reason": "other"})
    assert r.status_code == 200, r.text
    r = await client.post(f"{base}/reactivate", headers=auth_headers, json={})
    assert r.status_code == 200, r.text
    new_budget_id = await _confirm_plan(client, auth_headers, plan_id)

    assert new_budget_id != budget_id
    r = await client.get(f"/api/v1/budget/budgets/{new_budget_id}", headers=auth_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_concurrent_confirms_create_one_budget(
    client: AsyncClient, auth_headers: dict, setup: dict, db_session: AsyncSession
):
    """Two confirms at once (double click) both passed the draft check on
    their unlocked plan: two draft budgets, two confirmed events. The second
    now waits for the first and finds the plan pending (#774)."""
    import asyncio

    from app.database import async_session_maker
    from app.modules.treatment_plan.service import TreatmentPlanService

    plan_id, _ = await _create_plan_with_items(client, auth_headers, setup, [16])
    await db_session.commit()
    clinic_id, user_id = UUID(setup["clinic_id"]), UUID(setup["user_id"])

    async with async_session_maker() as first, async_session_maker() as second:
        await TreatmentPlanService.confirm(first, clinic_id, UUID(plan_id), user_id)
        other = asyncio.create_task(
            TreatmentPlanService.confirm(second, clinic_id, UUID(plan_id), user_id)
        )
        await asyncio.sleep(0.3)  # the second confirm reaches the lock
        await first.commit()
        with pytest.raises(ValueError, match="Cannot confirm"):
            await other
        await second.rollback()

    async with async_session_maker() as db:
        budgets = (
            (await db.execute(select(Budget).where(Budget.clinic_id == clinic_id))).scalars().all()
        )
    assert len(budgets) == 1
