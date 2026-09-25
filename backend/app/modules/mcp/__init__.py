"""MCP module - Model Context Protocol server for external AI clients.

Exposes a curated, scope-gated slice of DentalPin's agent tools over the MCP
streamable-HTTP transport at ``/api/v1/mcp``. Clients authenticate with the
``dp_`` API tokens issued by the integrations module (no JWT, no browser
session); ``patients:read`` tokens get the read tools, ``patients:write``
tokens add ``create_patient``. Every tool call flows through the shared
``tool_registry`` chokepoint, so RBAC, guardrails, input validation and the
audit log behave exactly as they do for internal agents.

Transport-only module: no models, no DB tables, no RBAC permissions,
no agent-facing tools of its own. Carries a single no-op Alembic
revision (own branch) purely so ``removable=True`` has an isolated
branch to validate against and uninstall has a ``base_revision`` to
bounce off.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .router import build_mcp_router


class MCPModule(BaseModule):
    """MCP server bridge — scope-gated patient tools for external AI agents."""

    manifest = {
        "name": "mcp",
        "version": "0.1.0",
        "summary": "MCP server exposing curated DentalPin tools to external AI clients.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients", "integrations"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {},
    }

    def get_models(self) -> list:
        # Transport only — no persistent state of its own.
        return []

    def get_router(self) -> APIRouter:
        return build_mcp_router()

    def get_permissions(self) -> list[str]:
        # Access is governed by API-token scopes (integrations), not staff RBAC.
        return []

    def get_tools(self) -> list:
        # Re-exposes other modules' tools via the registry at call time; adds
        # nothing of its own, so registering tools here would create conflicts.
        return []
