"""MCP (Model Context Protocol) bridge over DentalPin's tool registry.

Curated, scope-gated exposure of agent tools to external MCP clients (AI
desktops, Cursor, etc.). Tools are NOT re-implemented here: each exposed
tool maps to its registered ``<module>.<name>`` in the global
:data:`~app.core.agents.tools.registry.tool_registry`, and every ``tools/
call`` flows through :meth:`ToolRegistry.call` — guardrails, RBAC, input
validation and the audit log all stay enforced at the single chokepoint.
Identity (clinic) comes from the ``dp_`` API token that authenticated the
request, read off the per-message starlette request in ``ctx.request``.
"""

from __future__ import annotations

import json
import logging
from uuid import NAMESPACE_DNS, UUID, uuid5

from mcp.server import Server
from mcp.shared.exceptions import MCPError
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ContentBlock,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
)
from mcp.types import (
    Tool as MCPTool,
)
from mcp_types import INTERNAL_ERROR, INVALID_PARAMS
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents import AgentContext, AgentMode, tool_registry
from app.core.agents.models import Agent, AgentSession
from app.core.agents.tools.schema import pydantic_to_json_schema
from app.core.auth.permissions import permission_matches
from app.database import async_session_maker

logger = logging.getLogger(__name__)

# The curated tool surface, namespaced registry keys. Deliberately a closed
# allowlist: only tools a ``dp_`` token scope admits. ``search_patients`` /
# ``get_patient`` take the ``patients:read`` scope, ``create_patient`` takes
# ``patients:write`` — each tool's RBAC requirement (via
# ``_SCOPE_TO_PERMISSION``) filters what a given session may even see.
CURATED_TOOLS: tuple[str, ...] = (
    "patients.search_patients",
    "patients.get_patient",
    "patients.create_patient",
)

# Token scope -> the RBAC grant it represents. Translating scopes into the
# RBAC strings the curated tools declare means the registry chokepoint
# enforces exactly what the HTTP routes would: a read-only token can
# list/search but not create; a write-only token can create but not read;
# a token with both gets both surfaces.
_SCOPE_TO_PERMISSION: dict[str, str] = {
    "patients:read": "patients.read",
    "patients:write": "patients.write",
}


def _scopes_to_rbac(scopes: list[str]) -> list[str]:
    """Translate the API-token scopes into the RBAC grants they cover."""
    return [perm for scope, perm in _SCOPE_TO_PERMISSION.items() if scope in scopes]


# Deterministic agent/session ids so the audit trail for one API token stays
# grouped without any cross-request state. Namespaces are frozen constants
# derived from fixed names via uuid5 — stable across restarts. Never change
# them: a different namespace mints different ids and splits one token's
# history across new agent/session rows.
_AGENT_NS = uuid5(NAMESPACE_DNS, "dentalpin.agents")
_SESSION_NS = uuid5(NAMESPACE_DNS, "dentalpin.sessions")


def build_mcp_server() -> Server:
    """Construct the lowlevel MCP server wiring the curated handlers."""
    return Server(
        "dentalpin-mcp",
        version="0.1.0",
        title="DentalPin MCP",
        description="Dental clinic data for AI agents — patient access scoped by API token.",
        on_list_tools=_list_tools,
        on_call_tool=_call_tool,
    )


async def _list_tools(ctx, params: PaginatedRequestParams | None) -> ListToolsResult:
    identity = _identity_from_ctx(ctx)
    if identity is None:
        # The auth middleware gate guarantees identity; reaching the handler
        # without it is an internal inconsistency, fail closed.
        raise MCPError(code=INTERNAL_ERROR, message="Missing request identity")

    rbac = _scopes_to_rbac(identity["scopes"])
    tools: list[MCPTool] = []
    for qualified in CURATED_TOOLS:
        tool = tool_registry.get(qualified)
        if tool is None:
            # Only reachable when patients is not mounted — depends guards it.
            continue
        # Only surface tools the token's scopes would let it call; a
        # read-only token never sees create_patient, so clients can't build
        # prompts around permissions they don't have.
        if not all(
            any(permission_matches(required, granted) for granted in rbac)
            for required in tool.permissions
        ):
            continue
        tools.append(
            MCPTool(
                name=qualified.split(".", 1)[1],
                description=tool.description,
                input_schema=pydantic_to_json_schema(tool.parameters),
            )
        )
    return ListToolsResult(tools=tools)


async def _call_tool(ctx, params: CallToolRequestParams) -> CallToolResult:
    identity = _identity_from_ctx(ctx)
    if identity is None:
        # The auth middleware gate guarantees identity; reaching the handler
        # without it is an internal inconsistency, fail closed.
        raise MCPError(code=INTERNAL_ERROR, message="Missing request identity")

    qualified = f"patients.{params.name}"
    tool = tool_registry.get(qualified)
    if tool is None:
        raise MCPError(code=INVALID_PARAMS, message=f"Unknown tool: {params.name}")

    token_key = str(UUID(str(identity["token_id"])))
    agent_id = uuid5(_AGENT_NS, token_key)
    session_id = uuid5(_SESSION_NS, token_key)
    async with async_session_maker() as db:
        await _ensure_agent_and_session(db, agent_id, session_id, identity["clinic_id"])
        agent_ctx = AgentContext(
            agent_id=agent_id,
            session_id=session_id,
            clinic_id=identity["clinic_id"],
            mode=AgentMode.AUTONOMOUS,
            permissions=_scopes_to_rbac(identity["scopes"]),
            tools=tool_registry,
            db=db,
        )
        result = await tool_registry.call(agent_ctx, qualified, params.arguments or {})
        # The audit row is flushed by AuditService but only persisted on commit.
        await db.commit()

    if result.ok:
        text = json.dumps(result.data, ensure_ascii=False, default=str)
        content: list[ContentBlock] = [TextContent(type="text", text=text)]
        return CallToolResult(content=content, structured_content=result.data, is_error=False)

    return CallToolResult(
        content=[TextContent(type="text", text=result.error or "error")],
        is_error=True,
    )


async def _ensure_agent_and_session(
    db: AsyncSession, agent_id: UUID, session_id: UUID, clinic_id: UUID
) -> None:
    """Create the agent + session rows the audit trail FK requires.

    The audit log is keyed on ``agent_id``/``session_id`` (both FK-cascaded),
    and those ids are derived deterministically from the API token. UPSERT so
    the rows exist from the very first tool call and persist for all later
    ones; the token's whole history stays grouped under one agent/session.
    """
    await db.execute(
        pg_insert(Agent)
        .values(
            id=agent_id,
            clinic_id=clinic_id,
            name=f"MCP client {str(agent_id)[:8]}",
            type="external_mcp",
            mode="autonomous",
            config={},
            status="active",
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await db.execute(
        pg_insert(AgentSession)
        .values(
            id=session_id,
            agent_id=agent_id,
            clinic_id=clinic_id,
            status="active",
            session_metadata={},
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )


def _identity_from_ctx(ctx) -> dict | None:
    """Read the identity stored by ``DentalPinAuthMiddleware``.

    ``ctx.request`` is the starlette ``Request`` the transport attached to
    this message (``mcp.server.context.ServerRequestContext.request``); its
    scope is the same dict the middleware mutated, so the stash is visible
    per message even for stateful sessions.
    """
    request = getattr(ctx, "request", None)
    if request is None:
        return None
    try:
        return request.scope.get("state", {}).get("dentalpin")
    except AttributeError:
        return None
