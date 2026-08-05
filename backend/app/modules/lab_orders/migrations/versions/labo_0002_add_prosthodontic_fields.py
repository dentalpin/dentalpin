"""lab_orders: add impression_type, antagonist_info, shade (Phase 7).

Also widens ``work_type`` to include "repair" — no schema change needed
for that since the column is a plain String(20), not a DB-level enum.

Revision ID: labo_0002
Revises: labo_0001
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "labo_0002"
down_revision: str | None = "labo_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lab_orders", sa.Column("impression_type", sa.String(length=20), nullable=True))
    op.add_column("lab_orders", sa.Column("antagonist_info", sa.String(length=500), nullable=True))
    op.add_column("lab_orders", sa.Column("shade", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("lab_orders", "shade")
    op.drop_column("lab_orders", "antagonist_info")
    op.drop_column("lab_orders", "impression_type")
