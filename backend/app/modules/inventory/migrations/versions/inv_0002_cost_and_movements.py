"""inventory: cost tracking + movement audit trail.

Tables:
    - ``inventory_items`` — adds ``unit_cost`` (last purchase cost) and
      ``average_cost`` (moving average / AVCO cost).
    - ``inventory_movements`` (new) — append-only audit trail of every
      quantity change, with a reason, signed delta, and a denormalized
      quantity_after snapshot.

Automatic deduction from treatments is deferred to Phase 11
(TreatmentConsumable) and is NOT part of this migration.

Revision ID: inv_0002
Revises: inv_0001
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "inv_0002"
down_revision: str | None = "inv_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REASONS = ("purchase", "return", "donation", "adjustment", "damaged", "expired", "lost", "used")


def upgrade() -> None:
    op.add_column("inventory_items", sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True))
    op.add_column("inventory_items", sa.Column("average_cost", sa.Numeric(10, 2), nullable=True))

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity_after", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "movement_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "reason IN (" + ", ".join(f"'{r}'" for r in _REASONS) + ")",
            name="ck_inventory_movement_reason_valid",
        ),
    )
    op.create_index("ix_inventory_movements_clinic_id", "inventory_movements", ["clinic_id"])
    op.create_index("ix_inventory_movements_item_id", "inventory_movements", ["item_id"])
    op.create_index("ix_inventory_movements_reason", "inventory_movements", ["reason"])
    op.create_index(
        "ix_inventory_movements_item_movement_date",
        "inventory_movements",
        ["item_id", "movement_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_movements_item_movement_date", table_name="inventory_movements"
    )
    op.drop_index("ix_inventory_movements_reason", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_item_id", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_clinic_id", table_name="inventory_movements")
    op.drop_table("inventory_movements")

    op.drop_column("inventory_items", "average_cost")
    op.drop_column("inventory_items", "unit_cost")
