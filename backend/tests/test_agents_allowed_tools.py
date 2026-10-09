"""``allowed_tools`` is a hard allow-list, enforced at the chokepoint (#558).

``BaseAgent.allowed_tools`` was declared and referenced nowhere, while
``docs/technical/creating-modules.md`` — the module-author contract —
promised that "the agent cannot invoke anything outside it, even if the
registry has other tools". These tests make that sentence true.

The trap worth pinning: on the context, ``None`` and ``[]`` are both
falsy and mean opposite things. ``None`` is "no subsetting", which
copilot and other conversational surfaces rely on; ``[]`` is a
declaration that nothing may be called, which is ``BaseAgent``'s
default so a forgetful agent gets nothing rather than everything. A
truthiness test would collapse the two and silently invert the control.
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents import AgentContext, AgentMode, Tool, ToolCategory, tool_registry
from app.core.agents.base import BaseAgent
from app.core.agents.guardrails import reset_counters
from app.core.agents.models import Agent, AgentAuditLog, AgentSession
from app.core.plugins.base import BaseModule


class _Args(BaseModel):
    message: str


async def _allowed_handler(ctx: AgentContext, params: _Args) -> dict:
    return {"ran": "allowed", "echo": params.message}


async def _other_handler(ctx: AgentContext, params: _Args) -> dict:
    return {"ran": "other", "echo": params.message}


class _SubsetFixtureModule(BaseModule):
    manifest = {
        "name": "fixture_subset",
        "version": "0.0.1",
        "summary": "Throwaway fixture for allowed_tools.",
        "category": "official",
        "installable": True,
        "auto_install": True,
        "removable": True,
    }

    def get_models(self) -> list:
        return []

    def get_router(self) -> APIRouter:
        return APIRouter()

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="allowed",
                description="In the agent's list.",
                parameters=_Args,
                handler=_allowed_handler,
                category=ToolCategory.READ,
                permissions=["fixture_subset.allowed"],
            ),
            Tool(
                name="other",
                description="Registered, but NOT in the agent's list.",
                parameters=_Args,
                handler=_other_handler,
                category=ToolCategory.READ,
                permissions=["fixture_subset.other"],
            ),
        ]


@pytest.fixture(autouse=True)
def _register_fixture_tools():
    """Register, then *unregister* -- ``tool_registry`` is a process-wide
    singleton, so a fixture module left behind leaks into every later
    test file. These tools gate on permissions that deliberately do not
    exist in the real catalog, which makes
    ``test_agents_tooling.py::test_every_tool_permission_exists`` fail
    once it sees them (it walks the whole registry). Same register /
    yield / unregister shape as ``test_agents_registry.py``.
    """
    tool_registry.register_from(_SubsetFixtureModule())
    reset_counters()
    yield
    tool_registry.unregister_module("fixture_subset")
    reset_counters()


async def _agent_and_session(db: AsyncSession, clinic_id) -> tuple:
    agent = Agent(clinic_id=clinic_id, name="t", type="fixture", mode="autonomous", config={})
    db.add(agent)
    await db.flush()
    session = AgentSession(agent_id=agent.id, clinic_id=clinic_id)
    db.add(session)
    await db.flush()
    return agent, session


def _ctx(agent, session, clinic_id, db, allowed) -> AgentContext:
    kwargs = dict(
        agent_id=agent.id,
        session_id=session.id,
        clinic_id=clinic_id,
        mode=AgentMode.AUTONOMOUS,
        # Deliberately permitted by RBAC: this is what proves the subset
        # check is doing the work rather than the permission check.
        permissions=["fixture_subset.allowed", "fixture_subset.other"],
        tools=tool_registry,
        db=db,
    )
    if allowed is not ...:
        kwargs["allowed_tools"] = allowed
    return AgentContext(**kwargs)


async def _audit(db: AsyncSession, session_id) -> list[AgentAuditLog]:
    rows = await db.execute(select(AgentAuditLog).where(AgentAuditLog.session_id == session_id))
    return list(rows.scalars().all())


# --- the control itself ---------------------------------------------------


@pytest.mark.asyncio
async def test_a_tool_outside_the_list_is_refused(db_session, test_clinic):
    agent, session = await _agent_and_session(db_session, test_clinic.id)
    ctx = _ctx(agent, session, test_clinic.id, db_session, ["fixture_subset.allowed"])

    result = await tool_registry.call(ctx, "fixture_subset.other", {"message": "hi"})

    assert result.ok is False
    assert "not in allowed_tools" in (result.error or "")
    assert result.data is None or result.data == {}


@pytest.mark.asyncio
async def test_a_tool_inside_the_list_still_runs(db_session, test_clinic):
    agent, session = await _agent_and_session(db_session, test_clinic.id)
    ctx = _ctx(agent, session, test_clinic.id, db_session, ["fixture_subset.allowed"])

    result = await tool_registry.call(ctx, "fixture_subset.allowed", {"message": "hi"})

    assert result.ok is True
    assert result.data == {"ran": "allowed", "echo": "hi"}


@pytest.mark.asyncio
async def test_rbac_permission_does_not_rescue_a_tool_outside_the_list(db_session, test_clinic):
    """The subset is a second, narrower gate — not a restatement of RBAC."""
    agent, session = await _agent_and_session(db_session, test_clinic.id)
    ctx = _ctx(agent, session, test_clinic.id, db_session, ["fixture_subset.allowed"])
    assert "fixture_subset.other" in ctx.permissions

    result = await tool_registry.call(ctx, "fixture_subset.other", {"message": "hi"})
    assert result.ok is False and "not in allowed_tools" in (result.error or "")


# --- None vs [] ----------------------------------------------------------


@pytest.mark.asyncio
async def test_none_means_unrestricted_so_copilot_keeps_working(db_session, test_clinic):
    """The live surfaces build a context without this field at all."""
    agent, session = await _agent_and_session(db_session, test_clinic.id)
    ctx = _ctx(agent, session, test_clinic.id, db_session, ...)  # field omitted
    assert ctx.allowed_tools is None

    for name in ("fixture_subset.allowed", "fixture_subset.other"):
        assert (await tool_registry.call(ctx, name, {"message": "hi"})).ok is True


@pytest.mark.asyncio
async def test_explicit_none_is_also_unrestricted(db_session, test_clinic):
    agent, session = await _agent_and_session(db_session, test_clinic.id)
    ctx = _ctx(agent, session, test_clinic.id, db_session, None)

    assert (await tool_registry.call(ctx, "fixture_subset.other", {"message": "hi"})).ok is True


@pytest.mark.asyncio
async def test_empty_list_permits_nothing(db_session, test_clinic):
    """The inversion this guards against: `if not ctx.allowed_tools`
    would read an empty declaration as "allow everything"."""
    agent, session = await _agent_and_session(db_session, test_clinic.id)
    ctx = _ctx(agent, session, test_clinic.id, db_session, [])

    for name in ("fixture_subset.allowed", "fixture_subset.other"):
        result = await tool_registry.call(ctx, name, {"message": "hi"})
        assert result.ok is False, name
        assert "not in allowed_tools" in (result.error or "")


def test_base_agent_defaults_to_declaring_nothing():
    """So an agent that forgets gets nothing, not everything."""
    assert BaseAgent.allowed_tools == []


# --- the refusal is auditable --------------------------------------------


@pytest.mark.asyncio
async def test_the_refusal_is_recorded_as_blocked(db_session, test_clinic):
    agent, session = await _agent_and_session(db_session, test_clinic.id)
    ctx = _ctx(agent, session, test_clinic.id, db_session, ["fixture_subset.allowed"])

    await tool_registry.call(ctx, "fixture_subset.other", {"message": "hi"})

    rows = await _audit(db_session, session.id)
    assert len(rows) == 1
    assert rows[0].status == "BLOCKED"
    assert rows[0].tool_name == "fixture_subset.other"


@pytest.mark.asyncio
async def test_an_unknown_tool_still_raises_rather_than_being_refused(db_session, test_clinic):
    """Order matters: existence is checked before the subset, so a typo
    is a ToolRegistryError rather than a quiet policy refusal."""
    from app.core.agents.tools.registry import ToolRegistryError

    agent, session = await _agent_and_session(db_session, test_clinic.id)
    ctx = _ctx(agent, session, test_clinic.id, db_session, ["fixture_subset.allowed"])

    with pytest.raises(ToolRegistryError):
        await tool_registry.call(ctx, "fixture_subset.does_not_exist", {"message": "hi"})
