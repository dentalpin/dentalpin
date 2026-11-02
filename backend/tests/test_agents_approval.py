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
    assert approved.status == "executed"
    assert approved.reviewed_by == reviewer_id
    assert approved.review_notes == "looks good"
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

    assert first is not None and first.status == "executed"
    assert second is None
    assert _WRITES == ["room"]
    assert await _audit_statuses(db_session, test_clinic) == ["PENDING_APPROVAL", "SUCCESS"]


@pytest.mark.asyncio
async def test_rejected_request_is_never_executed(db_session, test_clinic):
    request_id = await _queue(db_session, test_clinic)
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)

    await ApprovalService.reject(db_session, test_clinic.id, request_id, reviewer_id=reviewer_id)
    late = await ApprovalService.approve(
        db_session, test_clinic.id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
    )

    assert late is None
    assert _WRITES == []


@pytest.mark.asyncio
async def test_failed_execution_is_marked_failed_and_rolled_back(db_session, test_clinic):
    clinic_id = test_clinic.id  # the rollback below expires ORM objects
    request_id = await _queue(db_session, test_clinic, tool="fail_thing")
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)

    result = await ApprovalService.approve(
        db_session, clinic_id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
    )

    assert result is not None
    assert result.status == "failed"
    assert result.reviewed_by == reviewer_id  # the decision itself still stands
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

    assert result is not None and result.status == "failed"


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

    assert result.status == "failed"
    assert _WRITES == []


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
    assert denied is not None and denied.status == "failed"
    assert _WRITES == []

    request_id = await _queue(db_session, test_clinic, tool="admin_thing")
    allowed = await ApprovalService.approve(
        db_session, test_clinic.id, request_id, reviewer_id=reviewer_id, reviewer_role="admin"
    )
    assert allowed.status == "executed"
    assert _WRITES == ["room"]


@pytest.mark.asyncio
async def test_approve_without_a_reviewer_role_fails_closed(db_session, test_clinic):
    request_id = await _queue(db_session, test_clinic, tool="admin_thing")
    reviewer_id = await _clinic_admin_id(db_session, test_clinic)

    result = await ApprovalService.approve(
        db_session, test_clinic.id, request_id, reviewer_id=reviewer_id
    )

    assert result.status == "failed"
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
    assert second.status_code == 404
    assert _WRITES == ["room"]


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
