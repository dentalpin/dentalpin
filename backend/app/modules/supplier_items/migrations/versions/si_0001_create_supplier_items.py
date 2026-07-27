"""supplier_items: create supplier_items table.

New independent branch (own module). Same shape as tcl_0001 /
supp_0001 — picks the newest confirmed head at write time and forks
its own branch_labels off it.

⚠️ down_revision below is "supp_0001" (13a's head). Run `alembic heads`
BEFORE applying — if it's no longer a head, update down_revision to
whatever IS. This starts its own branch, so it doesn't need the true
global head, just any revision that actually exists.

Revision ID: si_0001
Revises: supp_0001
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "si_0001"
down_revision = "supp_0001"
branch_labels = ("supplier_items",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False
        ),
        sa.Column(
            "supplier_contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("supplier_sku", sa.String(length=100), nullable=True),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_preferred_supplier", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint(
            "supplier_contact_id", "inventory_item_id", name="uq_supplier_item_pair"
        ),
    )
    op.create_index("idx_supplier_items_clinic", "supplier_items", ["clinic_id"])
    op.create_index("ix_supplier_items_supplier_contact_id", "supplier_items", ["supplier_contact_id"])
    op.create_index("ix_supplier_items_inventory_item_id", "supplier_items", ["inventory_item_id"])


def downgrade() -> None:
    op.drop_index("ix_supplier_items_inventory_item_id", table_name="supplier_items")
    op.drop_index("ix_supplier_items_supplier_contact_id", table_name="supplier_items")
    op.drop_index("idx_supplier_items_clinic", table_name="supplier_items")
    op.drop_table("supplier_items")
