"""Tests for the approval queue flow (supervised mode)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.core.agents import AgentContext, AgentMode, Tool, ToolCategory, tool_registry
from app.core.agents.guardrails import reset_counters
from app.core.agents.models import Agent, AgentApprovalQueue, AgentAuditLog, AgentSession
from app.core.agents.service import ApprovalService
from app.core.auth.models import ClinicMembership
from app.core.plugins.base import BaseModule


class _Args(BaseModel):
    target: str


_WRITES: list[str] = []


async def _write(ctx, params):
    _WRITES.append(params.target)
    return {"wrote": params.target}


async def _half_write_then_fail(ctx, params):
    # A change that reaches the session before the handler blows up.
    ctx.db.add(
        Agent(clinic_id=ctx.clinic_id, name="leaked", type="fixture", mode="supervised", config={})
    )
    await ctx.db.flush()
    raise RuntimeError("disk on fire")


class _ApprovalsFixture(BaseModule):
    manifest = {
        "name": "approvals_fixture",
        "version": "0.0.1",
        "summary": "x",
        "category": "official",
        "installable": True,
        "auto_install": True,
        "removable": True,
    }

    def get_models(self):
        return []

    def get_router(self) -> APIRouter:
        return APIRouter()

    def get_tools(self):
        return [
            Tool(
                name="write_thing",
                description="writes",
                parameters=_Args,
                handler=_write,
                permissions=[],
                category=ToolCategory.WRITE,
            ),
            Tool(
                name="fail_thing",
                description="fails after a partial write",
                parameters=_Args,
                handler=_half_write_then_fail,
                permissions=[],
                category=ToolCategory.WRITE,
            ),
            Tool(
                name="delete",
                description="destructive; the default guardrails queue it twice over",
                parameters=_Args,
                handler=_write,
                permissions=[],
                category=ToolCategory.DESTRUCTIVE,
            ),
            Tool(
                name="admin_thing",
                description="needs a permission",
                parameters=_Args,
                handler=_write,
                permissions=["approvals_fixture.admin"],
                category=ToolCategory.WRITE,
            ),
        ]


@pytest.fixture(autouse=True)
def _module_fixture():
    tool_registry.register_from(_ApprovalsFixture())
    reset_counters()
    _WRITES.clear()
    yield
    tool_registry.unregister_module("approvals_fixture")
    reset_counters()


async def _setup(db_session, clinic):
    agent = Agent(clinic_id=clinic.id, name="a", type="fixture", mode="supervised", config={})
    db_session.add(agent)
    await db_session.flush()
    session = AgentSession(agent_id=agent.id, clinic_id=clinic.id)
    db_session.add(session)
    await db_session.flush()
    return agent, session


async def _clinic_admin_id(db_session, clinic):
    """Return any user_id with membership in the test clinic (FK-safe reviewer)."""
    result = await db_session.execute(
        select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == clinic.id)
    )
    return result.scalars().first()


@pytest.mark.asyncio
async def test_supervised_write_enqueues_approval(db_session, test_clinic):
    agent, session = await _setup(db_session, test_clinic)
    ctx = AgentContext(
        agent_id=agent.id,
        session_id=session.id,
        clinic_id=test_clinic.id,
        mode=AgentMode.SUPERVISED,
        permissions=["*"],
        tools=tool_registry,
        db=db_session,
    )

    result = await tool_registry.call(ctx, "approvals_fixture.write_thing", {"target": "room"})

    assert result.ok is False
    assert result.error == "pending approval"
    assert "approval_request_id" in (result.data or {})

    pending = await ApprovalService.list_pending(db_session, test_clinic.id)
    assert len(pending) == 1
    assert pending[0].tool_name == "approvals_fixture.write_thing"
    assert pending[0].arguments == {"target": "room"}


async def _queue(db_session, clinic, tool="write_thing", arguments=None):
    """Queue a call through the registry, exactly as a supervised agent would."""
    agent, session = await _setup(db_session, clinic)
    ctx = AgentContext(
        agent_id=agent.id,
        session_id=session.id,
        clinic_id=clinic.id,
        mode=AgentMode.SUPERVISED,
        permissions=["*"],
        tools=tool_registry,
        db=db_session,
    )
    result = await tool_registry.call(
        ctx, f"approvals_fixture.{tool}", arguments or {"target": "room"}
    )
    assert result.error == "pending approval"
    return UUID(result.data["approval_request_id"])


async def _audit_statuses(db_session, clinic):
    rows = await db_session.execute(
        select(AgentAuditLog.status)
        .where(AgentAuditLog.clinic_id == clinic.id)
        .order_by(AgentAuditLog.created_at)
    )
    return list(rows.scalars().all())


@pytest.mark.asyncio
async def test_approve_executes_the_queued_call(db_session, test_clinic):
    """Replaces ``test_approve_marks_request_approved``, which asserted only
    the status flip: approving has to produce the effect. The erasure
    reproduction from the issue is in
    ``tests/modules/gdpr/test_gdpr_approval_executes.py``."""
    request_id = await _queue(db_session, test_clinic)
    assert _WRITES == []  # queued, not run

    reviewer_id = await _clinic_admin_id(db_session, test_clinic)
    approved = await ApprovalService.approve(
        db_session,
        test_clinic.id,
        request_id,
        reviewer_id=reviewer_id,
        reviewer_role="admin",
        notes="looks good",
    )

    assert approved is not None
    assert approved.request.status == "executed"
    assert approved.request.reviewed_by == reviewer_id
    assert approved.request.review_notes == "looks good"
    assert approved.error is None
    assert _WRITES == ["room"]
    # Audit trail: the queueing row, then the real execution row.
    assert await _audit_statuses(db_session, test_clinic) == ["PENDING_APPROVAL", "SUCCESS"]


@pytest.mark.asyncio
async def test_approving_twice_runs_the_action_once(db_session, test_clinic):
    request_id = await _queue(db_session, test_clinic)
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)

    first = await ApprovalService.approve(
        db_session, test_clinic.id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
    )
    second = await ApprovalService.approve(
        db_session, test_clinic.id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
    )

    assert first is not None and first.request.status == "executed"
    assert second is None
    assert _WRITES == ["room"]
    assert await _audit_statuses(db_session, test_clinic) == ["PENDING_APPROVAL", "SUCCESS"]


@pytest.mark.asyncio
async def test_rejected_request_is_never_executed(db_session, test_clinic):
    request_id = await _queue(db_session, test_clinic)
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)

    rejected = await ApprovalService.reject(
        db_session, test_clinic.id, request_id, reviewer_id=reviewer_id
    )
    assert rejected.status == "rejected"
    assert _WRITES == []  # rejecting runs nothing ...
    assert await _audit_statuses(db_session, test_clinic) == ["PENDING_APPROVAL"]

    late = await ApprovalService.approve(
        db_session, test_clinic.id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
    )

    assert late is None  # ... and a rejected request cannot be approved later
    assert _WRITES == []
    assert await _audit_statuses(db_session, test_clinic) == ["PENDING_APPROVAL"]


@pytest.mark.asyncio
async def test_failed_execution_is_marked_failed_and_rolled_back(db_session, test_clinic):
    clinic_id = test_clinic.id  # the rollback below expires ORM objects
    request_id = await _queue(db_session, test_clinic, tool="fail_thing")
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)

    result = await ApprovalService.approve(
        db_session, clinic_id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
    )

    assert result is not None
    assert result.request.status == "failed"
    assert result.request.reviewed_by == reviewer_id  # the decision itself still stands
    assert result.error == "disk on fire"  # returned to the reviewer, not stored
    # The audit row carries the error ...
    log = (
        await db_session.execute(select(AgentAuditLog).where(AgentAuditLog.status == "FAILED"))
    ).scalar_one()
    assert log.error == "disk on fire"
    # ... and the half-written change was taken back.
    leaked = await db_session.execute(select(Agent).where(Agent.name == "leaked"))
    assert leaked.scalars().all() == []
    # A failed request is decided: it cannot be approved again and re-run.
    again = await ApprovalService.approve(
        db_session, clinic_id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
    )
    assert again is None


@pytest.mark.asyncio
async def test_unknown_tool_in_queue_fails_instead_of_raising(db_session, test_clinic):
    agent, session = await _setup(db_session, test_clinic)
    req = AgentApprovalQueue(
        agent_id=agent.id,
        session_id=session.id,
        clinic_id=test_clinic.id,
        tool_name="gone_module.gone_tool",
        arguments={},
        status="pending",
    )
    db_session.add(req)
    await db_session.flush()

    reviewer_id = await _clinic_admin_id(db_session, test_clinic)
    result = await ApprovalService.approve(
        db_session, test_clinic.id, req.id, reviewer_id=reviewer_id, reviewer_role="admin"
    )

    assert result is not None and result.request.status == "failed"
    assert result.error == "Unknown tool: gone_module.gone_tool"


@pytest.mark.asyncio
async def test_stale_arguments_are_revalidated_at_approval(db_session, test_clinic):
    request_id = await _queue(db_session, test_clinic)
    row = await db_session.get(AgentApprovalQueue, request_id)
    row.arguments = {}  # required field now missing (the tool model changed since queueing)
    await db_session.flush()

    reviewer_id = await _clinic_admin_id(db_session, test_clinic)
    result = await ApprovalService.approve(
        db_session, test_clinic.id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
    )

    assert result.request.status == "failed"
    assert result.error.startswith("validation error")
    assert _WRITES == []  # the tool was never called
    log = (
        await db_session.execute(
            select(AgentAuditLog)
            .where(AgentAuditLog.clinic_id == test_clinic.id)
            .order_by(AgentAuditLog.created_at.desc())
            .limit(1)
        )
    ).scalar_one()
    assert log.status == "FAILED"
    assert log.error.startswith("validation error")
    assert log.execution_time_ms == 0


@pytest.mark.asyncio
async def test_execution_uses_the_reviewers_permissions(db_session, test_clinic):
    # The agent session had "*"; what counts is what the reviewer holds.
    request_id = await _queue(db_session, test_clinic, tool="admin_thing")
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)

    denied = await ApprovalService.approve(
        db_session,
        test_clinic.id,
        request_id,
        reviewer_id=reviewer_id,
        reviewer_role="receptionist",
    )
    assert denied is not None and denied.request.status == "failed"
    assert denied.error == "permission denied: approvals_fixture.admin"
    assert _WRITES == []

    request_id = await _queue(db_session, test_clinic, tool="admin_thing")
    allowed = await ApprovalService.approve(
        db_session, test_clinic.id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
    )
    assert allowed.request.status == "executed"
    assert _WRITES == ["room"]


@pytest.mark.asyncio
async def test_approve_without_a_reviewer_role_fails_closed(db_session, test_clinic):
    request_id = await _queue(db_session, test_clinic, tool="admin_thing")
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)

    result = await ApprovalService.approve(
        db_session, test_clinic.id, request_id, reviewer_id=reviewer_id
    )

    assert result.request.status == "failed"
    assert _WRITES == []


@pytest.mark.asyncio
async def test_approve_endpoint_executes_and_a_second_click_is_404(
    client, auth_headers, db_session, test_clinic
):
    request_id = await _queue(db_session, test_clinic)
    headers = {**auth_headers, "X-Clinic-Id": str(test_clinic.id)}

    first = await client.post(
        f"/api/v1/agents/approvals/{request_id}/approve", json={}, headers=headers
    )
    second = await client.post(
        f"/api/v1/agents/approvals/{request_id}/approve", json={}, headers=headers
    )

    assert first.status_code == 200, first.text
    assert first.json()["data"]["status"] == "executed"
    assert first.json()["data"]["error"] is None
    assert second.status_code == 404
    assert _WRITES == ["room"]


@pytest.mark.asyncio
async def test_approve_endpoint_reports_a_failed_run(client, auth_headers, db_session, test_clinic):
    clinic_id = test_clinic.id  # the rollback inside the request expires ORM objects
    request_id = await _queue(db_session, test_clinic, tool="fail_thing")
    headers = {**auth_headers, "X-Clinic-Id": str(clinic_id)}

    resp = await client.post(
        f"/api/v1/agents/approvals/{request_id}/approve", json={}, headers=headers
    )

    # The decision was recorded, the run was not: the response says which.
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "failed"
    assert resp.json()["data"]["error"] == "disk on fire"
    leaked = await db_session.execute(select(Agent).where(Agent.name == "leaked"))
    assert leaked.scalars().all() == []


@pytest.mark.asyncio
async def test_two_reviewers_approving_at_once_run_it_once(db_session, test_clinic):
    """Two approvals racing on their own connections, as two browser tabs
    or two supervisors would: exactly one runs the action."""
    import asyncio

    from app.database import async_session_maker

    clinic_id = test_clinic.id
    request_id = await _queue(db_session, test_clinic)
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)
    await db_session.commit()

    async def approve():
        async with async_session_maker() as db:
            result = await ApprovalService.approve(
                db, clinic_id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
            )
            await db.commit()
            return None if result is None else result.request.status

    outcomes = await asyncio.gather(approve(), approve())

    assert sorted(outcomes, key=lambda o: o is None) == ["executed", None]
    assert _WRITES == ["room"]


@pytest.mark.asyncio
async def test_an_approval_waiting_on_the_lock_sees_the_other_decision(db_session, test_clinic):
    """The second approval has the row cached as ``pending`` and blocks on the
    row lock while the first decides; once the first commits it must re-read
    the row (populate_existing), find it decided, and run nothing."""
    import asyncio

    from app.database import async_session_maker

    clinic_id = test_clinic.id
    request_id = await _queue(db_session, test_clinic)
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)
    await db_session.commit()

    async with async_session_maker() as holder, async_session_maker() as other:
        cached = await other.get(AgentApprovalQueue, request_id)
        assert cached.status == "pending"
        locked = (
            await holder.execute(
                select(AgentApprovalQueue)
                .where(AgentApprovalQueue.id == request_id)
                .with_for_update()
            )
        ).scalar_one()

        waiting = asyncio.create_task(
            ApprovalService.approve(
                other, clinic_id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
            )
        )
        await asyncio.sleep(0.3)
        assert not waiting.done(), "the second approval should be blocked on the row lock"

        locked.status = "approved"  # the first reviewer's decision lands
        await holder.commit()
        assert await waiting is None
        await other.rollback()

    assert _WRITES == []


@pytest.mark.asyncio
async def test_reject_is_idempotent_against_double_decision(db_session, test_clinic):
    agent, session = await _setup(db_session, test_clinic)
    req = AgentApprovalQueue(
        agent_id=agent.id,
        session_id=session.id,
        clinic_id=test_clinic.id,
        tool_name="x.y",
        arguments={},
        status="pending",
    )
    db_session.add(req)
    await db_session.flush()

    reviewer_id = await _clinic_admin_id(db_session, test_clinic)
    await ApprovalService.reject(db_session, test_clinic.id, req.id, reviewer_id=reviewer_id)
    # Second decision on an already-decided request returns None.
    second = await ApprovalService.approve(
        db_session, test_clinic.id, req.id, reviewer_id=reviewer_id
    )
    assert second is None


@pytest.mark.asyncio
async def test_cross_clinic_access_returns_none(db_session, test_clinic):
    agent, session = await _setup(db_session, test_clinic)
    req = AgentApprovalQueue(
        agent_id=agent.id,
        session_id=session.id,
        clinic_id=test_clinic.id,
        tool_name="x.y",
        arguments={},
        status="pending",
    )
    db_session.add(req)
    await db_session.flush()

    other_clinic_id = uuid4()
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)
    result = await ApprovalService.approve(
        db_session, other_clinic_id, req.id, reviewer_id=reviewer_id
    )
    assert result is None


@pytest.mark.asyncio
async def test_a_raising_tool_leaves_the_row_failed_in_its_own_transaction(db_session, test_clinic):
    """The decision and the run are separate transactions: the handler's
    rollback must not take the decision with it. Read back on a fresh
    connection, so only committed state counts."""
    from app.database import async_session_maker

    clinic_id = test_clinic.id
    request_id = await _queue(db_session, test_clinic, tool="fail_thing")
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)

    await ApprovalService.approve(
        db_session,
        clinic_id,
        request_id,
        reviewer_id=reviewer_id,
        reviewer_role="admin",
        notes="erase it",
    )

    async with async_session_maker() as fresh:
        row = await fresh.get(AgentApprovalQueue, request_id)
        assert row.status == "failed"
        # Written in the first transaction, still there after the rollback.
        assert row.reviewed_by == reviewer_id
        assert row.reviewed_at is not None
        assert row.review_notes == "erase it"
        statuses = (
            (
                await fresh.execute(
                    select(AgentAuditLog.status)
                    .where(AgentAuditLog.clinic_id == clinic_id)
                    .order_by(AgentAuditLog.created_at)
                )
            )
            .scalars()
            .all()
        )
        assert list(statuses) == ["PENDING_APPROVAL", "FAILED"]
        leaked = await fresh.execute(select(Agent).where(Agent.name == "leaked"))
        assert leaked.scalars().all() == []


@pytest.mark.asyncio
async def test_an_approved_call_does_not_loop_back_into_the_queue(db_session, test_clinic):
    """``approvals_fixture.delete`` is DESTRUCTIVE *and* matches the default
    ``*.delete`` pattern, so the guardrail would answer REQUIRE_APPROVAL to
    any context, including the reviewer's autonomous one. Approving must run
    it, not open a second request."""
    request_id = await _queue(db_session, test_clinic, tool="delete")
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)

    result = await ApprovalService.approve(
        db_session, test_clinic.id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
    )

    assert result.request.status == "executed"
    assert _WRITES == ["room"]
    queue = (
        (
            await db_session.execute(
                select(AgentApprovalQueue).where(AgentApprovalQueue.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .all()
    )
    assert [r.id for r in queue] == [request_id]  # no second request
    assert await _audit_statuses(db_session, test_clinic) == ["PENDING_APPROVAL", "SUCCESS"]


@pytest.mark.asyncio
async def test_approvals_status_filter_is_a_closed_vocabulary(
    client, auth_headers, db_session, test_clinic
):
    headers = {**auth_headers, "X-Clinic-Id": str(test_clinic.id)}
    request_id = await _queue(db_session, test_clinic)
    await client.post(f"/api/v1/agents/approvals/{request_id}/approve", json={}, headers=headers)

    typo = await client.get("/api/v1/agents/approvals?status=execute", headers=headers)
    assert typo.status_code == 422  # was an empty 200

    executed = await client.get("/api/v1/agents/approvals?status=executed", headers=headers)
    assert executed.status_code == 200
    assert [r["id"] for r in executed.json()["data"]] == [str(request_id)]
    for status in ("pending", "approved", "rejected", "failed"):
        resp = await client.get(f"/api/v1/agents/approvals?status={status}", headers=headers)
        assert resp.status_code == 200, status
        assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_a_supervisor_without_the_tools_permission_gets_failed(
    client, db_session, test_clinic, test_patient
):
    """The reviewer needs ``agents.supervise`` *and* the tool's own
    permission. A clinic role holding only ``agents.supervise`` and
    ``patients.read`` approves a ``patients.update_patient`` call: the
    endpoint lets them decide (they hold ``agents.supervise``), the run is
    refused, the request ends ``failed`` and the patient is untouched.

    No built-in role has ``agents.supervise`` without ``patients.write``, so
    this uses a clinic custom role under DB-backed RBAC."""
    from app.config import settings
    from app.core.auth.models import Permission, Role, RolePermission, User
    from app.core.auth.rbac import invalidate_rbac_cache
    from app.core.auth.seed_rbac import seed_rbac
    from app.core.auth.service import create_access_token, hash_password

    clinic_id = test_clinic.id
    patient_id = test_patient.id
    await seed_rbac(db_session)
    role = Role(clinic_id=clinic_id, name="desk_supervisor", is_system=False)
    db_session.add(role)
    await db_session.flush()
    for code in ("agents.supervise", "patients.read"):
        perm = (
            await db_session.execute(select(Permission).where(Permission.code == code))
        ).scalar_one()
        db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    desk = User(
        email="desk-supervisor@example.com",
        password_hash=hash_password("DeskPass1234"),
        first_name="Desk",
        last_name="Supervisor",
    )
    db_session.add(desk)
    await db_session.flush()
    desk_id = desk.id
    db_session.add(ClinicMembership(user_id=desk_id, clinic_id=clinic_id, role="desk_supervisor"))
    agent, session = await _setup(db_session, test_clinic)
    agent_ctx = AgentContext(
        agent_id=agent.id,
        session_id=session.id,
        clinic_id=clinic_id,
        mode=AgentMode.SUPERVISED,
        permissions=["*"],
        tools=tool_registry,
        db=db_session,
    )
    queued = await tool_registry.call(
        agent_ctx,
        "patients.update_patient",
        {"patient_id": str(patient_id), "phone": "+34600000000"},
    )
    assert queued.error == "pending approval"
    request_id = queued.data["approval_request_id"]
    await db_session.commit()
    headers = {
        "Authorization": f"Bearer {create_access_token(desk_id, token_version=desk.token_version)}",
        "X-Clinic-Id": str(clinic_id),
    }

    original_flag = settings.RBAC_FROM_DB
    settings.RBAC_FROM_DB = True
    invalidate_rbac_cache()
    try:
        resp = await client.post(
            f"/api/v1/agents/approvals/{request_id}/approve", json={}, headers=headers
        )
    finally:
        settings.RBAC_FROM_DB = original_flag
        invalidate_rbac_cache()

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == "failed"
    assert body["error"] == "permission denied: patients.write"
    assert body["reviewed_by"] == str(desk_id)
    db_session.expire_all()
    from app.modules.patients.models import Patient

    assert (await db_session.get(Patient, patient_id)).phone == "+34666123456"
    last = (
        await db_session.execute(
            select(AgentAuditLog)
            .where(AgentAuditLog.tool_name == "patients.update_patient")
            .order_by(AgentAuditLog.created_at.desc())
            .limit(1)
        )
    ).scalar_one()
    assert last.status == "BLOCKED"
    assert last.supervisor_id == desk_id
