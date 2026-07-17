"""inventory: initial schema.

Tables:
    - ``inventory_items`` — simple stock list with quantity on hand and a
      low-stock threshold.

Lives on its own Alembic branch (``inventory``) per ADR 0002.

Revision ID: inv_0001
Revises:
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "inv_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("inventory",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False, server_default="other"),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("quantity_on_hand", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("low_stock_threshold", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_items_clinic_id", "inventory_items", ["clinic_id"])
    op.create_index("ix_inventory_items_category", "inventory_items", ["category"])


def downgrade() -> None:
    op.drop_index("ix_inventory_items_category", table_name="inventory_items")
    op.drop_index("ix_inventory_items_clinic_id", table_name="inventory_items")
    op.drop_table("inventory_items")
