"""Guardrail policy + in-memory enforcement for tool invocations.

Guardrails answer a single question at the registry chokepoint:
may this context invoke this tool right now? The answer is one of
``ALLOW``, ``REQUIRE_APPROVAL`` or ``BLOCK``.

Enforcement is intentionally simple in Phase 1 — per-process,
in-memory counters keyed by session. A per-clinic configuration UI
and a distributed store (for multi-worker deployments) are tracked
as Phase 2 work in ``docs/technical/todos.md``.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from app.core.agents.tools.tool import Tool, ToolCategory
from app.core.auth.permissions import permission_matches

if TYPE_CHECKING:
    from app.core.agents.context import AgentContext


class GuardrailDecision(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"


@dataclass
class GuardrailConfig:
    """Policy knobs enforced by :func:`check`.

    All values are per-session. ``require_approval_for`` and
    ``blocked_tools`` accept the RBAC wildcard grammar
    (``module.*``, ``module.resource.*``, ``*``) plus a guardrails-only
    leading wildcard (``*.delete`` matches any ``<module>.delete`` tool).
    """

    max_actions_per_minute: int = 10
    max_actions_per_session: int = 100
    require_approval_for: list[str] = field(default_factory=lambda: ["*.delete", "billing.*"])
    blocked_tools: list[str] = field(default_factory=list)
    auto_require_approval_for_destructive: bool = True


# Module-level default. Agent rows may override per-session via
# ``agents.config`` (applied by the caller before invoking check()).
default_config = GuardrailConfig()


# Per-session rate-limit windows: session_id -> deque of timestamps.
_windows: dict[UUID, deque[float]] = {}

# Per-session lifetime totals: session_id -> action count. Never pruned:
# the session cap is a real session counter, not a second minute window.
_totals: dict[UUID, int] = {}


def _window_for(session_id: UUID) -> deque[float]:
    window = _windows.get(session_id)
    if window is None:
        window = deque()
        _windows[session_id] = window
    return window


def reset_counters() -> None:
    """Clear all per-session counters. Test-only."""
    _windows.clear()
    _totals.clear()


def _record(session_id: UUID, window: deque[float], now: float) -> None:
    window.append(now)
    _totals[session_id] = _totals.get(session_id, 0) + 1


def _matches_any(qualified_name: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        # Guardrails-only leading wildcard: "*.delete" matches any
        # "<module>.delete". RBAC itself has no such form, so this lives
        # here instead of permission_matches.
        if pattern.startswith("*."):
            if qualified_name.endswith(pattern[1:]):
                return True
        elif permission_matches(qualified_name, pattern):
            return True
    return False


def check(
    ctx: AgentContext,
    tool: Tool,
    qualified_name: str,
    config: GuardrailConfig | None = None,
) -> GuardrailDecision:
    """Decide whether ``ctx`` may invoke ``tool`` right now."""
    cfg = config or default_config

    if _matches_any(qualified_name, cfg.blocked_tools):
        return GuardrailDecision.BLOCK

    window = _window_for(ctx.session_id)
    now = time.monotonic()
    # Drop timestamps older than 60s.
    while window and now - window[0] > 60.0:
        window.popleft()
    if len(window) >= cfg.max_actions_per_minute:
        return GuardrailDecision.BLOCK
    if _totals.get(ctx.session_id, 0) >= cfg.max_actions_per_session:
        return GuardrailDecision.BLOCK

    # In supervised mode, every write action is human-reviewed.
    if ctx.mode.value == "supervised" and tool.category is not ToolCategory.READ:
        _record(ctx.session_id, window, now)
        return GuardrailDecision.REQUIRE_APPROVAL

    if cfg.auto_require_approval_for_destructive and tool.category is ToolCategory.DESTRUCTIVE:
        _record(ctx.session_id, window, now)
        return GuardrailDecision.REQUIRE_APPROVAL

    if _matches_any(qualified_name, cfg.require_approval_for):
        _record(ctx.session_id, window, now)
        return GuardrailDecision.REQUIRE_APPROVAL

    _record(ctx.session_id, window, now)
    return GuardrailDecision.ALLOW
