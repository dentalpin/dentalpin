"""Agent execution context and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.agents.guardrails import GuardrailConfig
    from app.core.agents.memory import AgentMemory
    from app.core.agents.tools.registry import ToolRegistry


class AgentMode(StrEnum):
    """How an agent's actions are gated.

    ``AUTONOMOUS`` agents execute tool calls immediately, subject only
    to guardrails and RBAC. ``SUPERVISED`` agents queue every write
    action for human approval before it takes effect.
    """

    AUTONOMOUS = "autonomous"
    SUPERVISED = "supervised"


@dataclass
class AgentContext:
    """State passed into every tool handler and agent run.

    The context is the single source of truth for *who* is acting and
    *where* they are acting. Tool handlers MUST filter by
    ``clinic_id`` the same way regular router endpoints do.
    """

    agent_id: UUID
    session_id: UUID
    clinic_id: UUID
    mode: AgentMode
    permissions: list[str]
    tools: ToolRegistry
    db: AsyncSession
    memory: AgentMemory | None = None
    supervisor_id: UUID | None = None
    # Tool subsetting (#558). ``None`` means unrestricted: the caller's
    # RBAC grants are the only limit, which is what conversational
    # surfaces like copilot need. A **list** is a hard allow-list checked
    # at the registry chokepoint, so an empty list permits nothing.
    #
    # None and [] are both falsy and mean opposite things, so this is
    # always compared with ``is None`` — treating "declared nothing" as
    # "allow everything" would invert the control this field exists to
    # provide. ``BaseAgent.allowed_tools`` defaults to ``[]`` precisely
    # so an agent that forgets to declare gets nothing rather than
    # everything; whatever builds the context for an agent must pass
    # that list through.
    allowed_tools: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    # Per-session guardrail override. Surfaces that gate writes
    # themselves (e.g. copilot's inline confirmation) pass a config that
    # disables the approval-queue triggers. ``None`` → module default.
    guardrail_config: GuardrailConfig | None = None


@dataclass
class AgentResult:
    """Outcome of a single agent run."""

    ok: bool
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)
