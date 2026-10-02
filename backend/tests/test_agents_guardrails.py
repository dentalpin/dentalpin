"""Tests for guardrail policy decisions."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.core.agents import AgentContext, AgentMode, Tool, ToolCategory, tool_registry
from app.core.agents.guardrails import (
    GuardrailConfig,
    GuardrailDecision,
    check,
    reset_counters,
)


class _Args(BaseModel):
    x: int = 0


async def _noop(ctx, params):
    return None


def _make_ctx(*, mode=AgentMode.AUTONOMOUS, session_id=None) -> AgentContext:
    return AgentContext(
        agent_id=uuid4(),
        session_id=session_id or uuid4(),
        clinic_id=uuid4(),
        mode=mode,
        permissions=["*"],
        tools=tool_registry,
        db=None,  # not used in pure guardrail checks
    )


def _tool(name: str, category: ToolCategory = ToolCategory.READ) -> Tool:
    return Tool(
        name=name,
        description="x",
        parameters=_Args,
        handler=_noop,
        permissions=[],
        category=category,
    )


@pytest.fixture(autouse=True)
def _clean():
    reset_counters()
    yield
    reset_counters()


def test_read_in_autonomous_mode_is_allowed():
    ctx = _make_ctx()
    assert check(ctx, _tool("r", ToolCategory.READ), "m.r") is GuardrailDecision.ALLOW


def test_write_in_supervised_mode_needs_approval():
    ctx = _make_ctx(mode=AgentMode.SUPERVISED)
    decision = check(ctx, _tool("w", ToolCategory.WRITE), "m.w")
    assert decision is GuardrailDecision.REQUIRE_APPROVAL


def test_destructive_requires_approval_by_default():
    ctx = _make_ctx(mode=AgentMode.AUTONOMOUS)
    decision = check(ctx, _tool("d", ToolCategory.DESTRUCTIVE), "m.d")
    assert decision is GuardrailDecision.REQUIRE_APPROVAL


def test_blocked_tool_is_blocked_even_with_wildcard_permissions():
    ctx = _make_ctx()
    cfg = GuardrailConfig(blocked_tools=["m.danger"])
    assert check(ctx, _tool("danger"), "m.danger", cfg) is GuardrailDecision.BLOCK


def test_wildcard_approval_pattern_matches():
    ctx = _make_ctx()
    cfg = GuardrailConfig(require_approval_for=["billing.*"])
    assert (
        check(ctx, _tool("send"), "billing.send_invoice", cfg) is GuardrailDecision.REQUIRE_APPROVAL
    )


def test_rate_limit_per_minute():
    ctx = _make_ctx()
    cfg = GuardrailConfig(max_actions_per_minute=3)
    for _ in range(3):
        assert check(ctx, _tool("r"), "m.r", cfg) is GuardrailDecision.ALLOW
    # Fourth call in the same minute is blocked.
    assert check(ctx, _tool("r"), "m.r", cfg) is GuardrailDecision.BLOCK


def test_rate_limit_is_scoped_per_session():
    ctx_a = _make_ctx()
    ctx_b = _make_ctx()
    cfg = GuardrailConfig(max_actions_per_minute=1)
    assert check(ctx_a, _tool("r"), "m.r", cfg) is GuardrailDecision.ALLOW
    # Different session — fresh budget.
    assert check(ctx_b, _tool("r"), "m.r", cfg) is GuardrailDecision.ALLOW
    # Same session as A — now over budget.
    assert check(ctx_a, _tool("r"), "m.r", cfg) is GuardrailDecision.BLOCK


def test_session_cap_is_lifetime_not_minute():
    ctx = _make_ctx()
    cfg = GuardrailConfig(max_actions_per_minute=1000, max_actions_per_session=3)
    for _ in range(3):
        assert check(ctx, _tool("r"), "m.r", cfg) is GuardrailDecision.ALLOW
    # Fourth action in the same session is blocked even though the
    # minute window is nowhere near full.
    assert check(ctx, _tool("r"), "m.r", cfg) is GuardrailDecision.BLOCK


def test_leading_wildcard_delete_pattern_matches():
    ctx = _make_ctx()
    # Default config carries "*.delete": a WRITE tool named *.delete
    # needs approval even though it is not DESTRUCTIVE.
    decision = check(ctx, _tool("purge", ToolCategory.WRITE), "media.delete", None)
    assert decision is GuardrailDecision.REQUIRE_APPROVAL
    # ... but a non-delete tool in the same module stays allowed.
    assert check(ctx, _tool("r"), "media.read", None) is GuardrailDecision.ALLOW
