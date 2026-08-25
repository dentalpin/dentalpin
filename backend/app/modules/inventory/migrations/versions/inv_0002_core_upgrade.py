"""inv_0002_core_upgrade — cost tracking + stock_movements ledger (#226).

Own Alembic branch (``inventory``): revises inv_0001, never touches
another module's chain. Adds ``unit_cost`` / ``is_active`` to
inventory_items and creates the append-only ``stock_movements`` ledger.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "inv_0002"
down_revision = "inv_0001"
branch_labels = ("inventory",)
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_items",
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "stock_movements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "clinic_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clinics.id"),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("inventory_items.id"),
            nullable=False,
        ),
        sa.Column("delta", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("reference_type", sa.String(length=30), nullable=True),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_stock_movements_clinic_created", "stock_movements", ["clinic_id", "created_at"]
    )
    op.create_index(
        "ix_stock_movements_item_created",
        "stock_movements",
        ["inventory_item_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_movements_item_created", table_name="stock_movements")
    op.drop_index("ix_stock_movements_clinic_created", table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_column("inventory_items", "is_active")
    op.drop_column("inventory_items", "unit_cost")
