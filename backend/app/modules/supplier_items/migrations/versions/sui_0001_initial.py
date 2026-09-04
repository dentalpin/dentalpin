"""supplier_items: initial schema.

Tables:
    - ``supplier_items`` - supplier <-> inventory item links with SKU and price.

Lives on its own Alembic branch (``supplier_items``) per ADR 0002.
Depends on the ``suppliers`` and ``inventory`` migrations since the FKs
point into both tables.

Revision ID: sui_0001
Revises:
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "sui_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("supplier_items",)
depends_on: str | Sequence[str] | None = ("supp_0001", "inv_0002")


def upgrade() -> None:
    op.create_table(
        "supplier_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("supplier_id", sa.UUID(), nullable=False),
        sa.Column("inventory_item_id", sa.UUID(), nullable=False),
        sa.Column("supplier_sku", sa.String(length=100), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=True),
        # Soft delete (L7): a removed link keeps its row for history.
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "supplier_id", "inventory_item_id", name="uq_supplier_items_supplier_item"
        ),
    )
    op.create_index("ix_supplier_items_clinic_id", "supplier_items", ["clinic_id"])
    op.create_index("ix_supplier_items_supplier_id", "supplier_items", ["supplier_id"])
    op.create_index("ix_supplier_items_inventory_item_id", "supplier_items", ["inventory_item_id"])


def downgrade() -> None:
    op.drop_index("ix_supplier_items_inventory_item_id", table_name="supplier_items")
    op.drop_index("ix_supplier_items_supplier_id", table_name="supplier_items")
    op.drop_index("ix_supplier_items_clinic_id", table_name="supplier_items")
    op.drop_table("supplier_items")
