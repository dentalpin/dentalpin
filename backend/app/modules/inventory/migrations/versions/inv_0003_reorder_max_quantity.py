"""inventory: add reorder_max_quantity.

Follow-up on inv_0002 (same branch, not a new one) — per Phase 13's own
note: "If you need a max threshold field on items, add it via a new
migration (inv_0003 chained on inv_0002)."

Revision ID: inv_0003
Revises: inv_0002
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "inv_0003"
down_revision: str | None = "inv_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inventory_items", sa.Column("reorder_max_quantity", sa.Numeric(10, 2), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("inventory_items", "reorder_max_quantity")
