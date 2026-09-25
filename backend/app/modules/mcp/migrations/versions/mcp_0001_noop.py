"""mcp: no-op, establishes an isolated branch.

This module has no tables — it's transport-only (see CLAUDE.md). But
`removable=True` requires a self-contained Alembic branch even so:
`app/core/plugins/manifest_validator.py`'s `module_branch_is_isolated`
check is what makes `alembic downgrade mcp@base` safe to run on
uninstall without touching any other module's migrations, and that
check needs at least one revision living under this module's own
`migrations/versions/` directory to have something to walk.
Additionally, `ModuleService.uninstall` refuses any module whose
`base_revision` is unset — this revision is what backfills it.

Standalone branch, no parent — there is nothing here to root on core
"0001" for, since there's no schema to create.

Revision ID: mcp_0001
Revises:
Create Date: 2026-09-14
"""

from collections.abc import Sequence

revision: str = "mcp_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("mcp",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
