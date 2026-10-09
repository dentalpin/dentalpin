"""Global tool registry and single-chokepoint invocation path."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from app.core.agents.tools.schema import tool_to_anthropic_schema, tool_to_openai_schema
from app.core.agents.tools.tool import Tool, ToolResult

if TYPE_CHECKING:
    from app.core.agents.context import AgentContext
    from app.core.plugins.base import BaseModule

logger = logging.getLogger(__name__)


class ToolRegistryError(Exception):
    """Raised for registration conflicts or invocation failures."""


class ToolRegistry:
    """Namespace-aware registry of all tools exposed by loaded modules.

    Tools are keyed by their *qualified name* — ``{module}.{tool}`` —
    which mirrors how :mod:`app.core.plugins.registry` namespaces
    permissions. The registry is the single entry point agents must
    use to invoke tools: :meth:`call` enforces permission checks,
    guardrails, input validation and audit logging on every call.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._owners: dict[str, str] = {}  # qualified_name -> module_name

    # --- Registration ---------------------------------------------------

    def register_from(self, module: BaseModule) -> None:
        """Collect and namespace every tool a module exposes."""
        for tool in module.get_tools():
            qualified = f"{module.name}.{tool.name}"
            if qualified in self._tools:
                raise ToolRegistryError(
                    f"Tool '{qualified}' is already registered (owner: {self._owners[qualified]})"
                )
            self._tools[qualified] = tool
            self._owners[qualified] = module.name
            logger.info("Registered tool: %s (category=%s)", qualified, tool.category.value)

    def unregister_module(self, module_name: str) -> None:
        """Drop every tool owned by ``module_name`` (for module uninstall)."""
        to_drop = [q for q, owner in self._owners.items() if owner == module_name]
        for qualified in to_drop:
            del self._tools[qualified]
            del self._owners[qualified]

    def clear(self) -> None:
        """Reset the registry. Test-only."""
        self._tools.clear()
        self._owners.clear()

    # --- Introspection --------------------------------------------------

    def get(self, qualified_name: str) -> Tool | None:
        return self._tools.get(qualified_name)

    def list(self) -> list[str]:
        """All qualified tool names currently registered."""
        return sorted(self._tools.keys())

    def schemas_for(self, qualified_names: list[str], dialect: str = "anthropic") -> list[dict]:
        """Return JSON Schemas for a subset of tools, for LLM prompts.

        ``dialect`` is ``"anthropic"`` or ``"openai"``.
        """
        serializer = tool_to_anthropic_schema if dialect == "anthropic" else tool_to_openai_schema
        out: list[dict] = []
        for qualified in qualified_names:
            tool = self._tools.get(qualified)
            if tool is None:
                raise ToolRegistryError(f"Unknown tool: {qualified}")
            out.append(serializer(tool, qualified))
        return out

    # --- Invocation (the chokepoint) ------------------------------------

    async def call(
        self,
        ctx: AgentContext,
        qualified_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Invoke a tool with enforcement.

        Enforcement order:

        1. Tool exists
        2. ``ctx.allowed_tools`` subset check, when the context declares one
        3. Guardrails check (rate limit, blocked, require-approval)
        4. RBAC permission check against ``ctx.permissions``
        5. Pydantic validation of ``arguments``
        6. Handler execution
        7. Audit-log write (regardless of success/failure)

        The subset check runs before guardrails on purpose: a call the
        agent was never allowed to make should not consume its rate
        limit or open an approval request.
        """
        from app.core.agents.guardrails import GuardrailDecision
        from app.core.agents.guardrails import check as guardrails_check
        from app.core.agents.service import ApprovalService, AuditService
        from app.core.agents.tooling import jsonify
        from app.core.auth.permissions import permission_matches

        tool = self._tools.get(qualified_name)
        if tool is None:
            raise ToolRegistryError(f"Unknown tool: {qualified_name}")

        # Tool subsetting (#558). `is not None` rather than a truthiness
        # test: an empty list is a declaration that this agent may call
        # nothing, while None means no subsetting was requested at all.
        # Exact names only -- the module-author contract calls this "a
        # hard list", so no wildcard expansion.
        if ctx.allowed_tools is not None and qualified_name not in ctx.allowed_tools:
            await AuditService.record(
                ctx,
                qualified_name,
                arguments,
                error=f"not in allowed_tools: {qualified_name}",
                status="BLOCKED",
                execution_time_ms=0,
            )
            return ToolResult(ok=False, error=f"not in allowed_tools: {qualified_name}")

        decision = guardrails_check(ctx, tool, qualified_name, ctx.guardrail_config)
        if decision is GuardrailDecision.BLOCK:
            await AuditService.record(
                ctx,
                qualified_name,
                arguments,
                error="blocked by guardrails",
                status="BLOCKED",
                execution_time_ms=0,
            )
            return ToolResult(ok=False, error="blocked by guardrails")

        if decision is GuardrailDecision.REQUIRE_APPROVAL:
            request = await ApprovalService.request_approval(
                ctx,
                qualified_name,
                arguments,
                reason="guardrail policy requires review",
            )
            await AuditService.record(
                ctx,
                qualified_name,
                arguments,
                result={"approval_request_id": str(request.id)},
                status="PENDING_APPROVAL",
                execution_time_ms=0,
            )
            return ToolResult(
                ok=False,
                data={"approval_request_id": str(request.id)},
                error="pending approval",
            )

        for required in tool.permissions:
            if not any(permission_matches(required, granted) for granted in ctx.permissions):
                await AuditService.record(
                    ctx,
                    qualified_name,
                    arguments,
                    error=f"permission denied: {required}",
                    status="BLOCKED",
                    execution_time_ms=0,
                )
                return ToolResult(ok=False, error=f"permission denied: {required}")

        try:
            validated = tool.parameters.model_validate(arguments)
        except Exception as exc:
            await AuditService.record(
                ctx,
                qualified_name,
                arguments,
                error=f"validation error: {exc}",
                status="FAILED",
                execution_time_ms=0,
            )
            return ToolResult(ok=False, error=f"validation error: {exc}")

        t0 = time.monotonic()
        try:
            raw = await tool.handler(ctx, validated)
            data = jsonify(raw)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            await AuditService.record(
                ctx,
                qualified_name,
                arguments,
                result=data,
                status="SUCCESS",
                execution_time_ms=elapsed_ms,
            )
            return ToolResult(ok=True, data=data, execution_time_ms=elapsed_ms)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            await AuditService.record(
                ctx,
                qualified_name,
                arguments,
                error=str(exc),
                status="FAILED",
                execution_time_ms=elapsed_ms,
            )
            logger.exception("Tool %s raised", qualified_name)
            return ToolResult(ok=False, error=str(exc), execution_time_ms=elapsed_ms)


# Global singleton
tool_registry = ToolRegistry()
