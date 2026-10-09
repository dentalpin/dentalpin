"""Base class for AI agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from app.core.agents.context import AgentMode

if TYPE_CHECKING:
    from app.core.agents.context import AgentContext, AgentResult


class BaseAgent(ABC):
    """Abstract base class every agent subclasses.

    An agent is a small, self-contained unit of logic that operates
    within the tool registry. Concrete subclasses declare their
    identity, mode, and the subset of tools they are allowed to call,
    then implement :meth:`process`.
    """

    #: Unique agent identifier, stable across runs.
    name: ClassVar[str]

    #: How this agent's writes are gated. Override per subclass.
    mode: ClassVar[AgentMode] = AgentMode.SUPERVISED

    #: Qualified tool names (``module.tool``) this agent may call.
    #:
    #: A hard allow-list, enforced at the registry chokepoint
    #: (:meth:`ToolRegistry.call`) when it reaches the context as
    #: ``AgentContext.allowed_tools`` — so whatever runs an agent must
    #: pass this through. Exact names; no wildcards.
    #:
    #: The default is deliberately **empty rather than unset**: an agent
    #: that declares nothing may call nothing. (On the context, ``None``
    #: is the separate "no subsetting" case, which non-agent surfaces
    #: such as copilot use.)
    allowed_tools: ClassVar[list[str]] = []

    @abstractmethod
    async def process(self, ctx: AgentContext) -> AgentResult:
        """Run one logical unit of agent work.

        Implementations receive a fully-populated :class:`AgentContext`
        — DB session, clinic, permissions, tools, memory — and return
        an :class:`AgentResult`. All tool invocations MUST go through
        ``ctx.tools.call(ctx, qualified_name, arguments)``.
        """
