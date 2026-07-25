"""create treatment_consumables table

Revision ID: tcl_0001
Revises: med_0002
Create Date: 2026-07-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# NOTE: down_revision assumes med_0002 is still the effective head for
# this branch. Run `alembic heads` before applying and update this if a
# different revision is now the head (per PHASE11_INSTALL_GUIDE.md).
revision = "tcl_0001"
down_revision = "med_0002"
branch_labels = ("treatment_consumables",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "treatment_consumables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False
        ),
        sa.Column(
            "treatment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("treatment_catalog_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity_needed", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "treatment_id", "inventory_item_id", name="uq_treatment_consumable_pair"
        ),
    )
    op.create_index(
        "idx_treatment_consumables_clinic", "treatment_consumables", ["clinic_id"]
    )
    op.create_index(
        "idx_treatment_consumables_treatment", "treatment_consumables", ["treatment_id"]
    )
    op.create_index(
        "idx_treatment_consumables_item", "treatment_consumables", ["inventory_item_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_treatment_consumables_item", table_name="treatment_consumables")
    op.drop_index("idx_treatment_consumables_treatment", table_name="treatment_consumables")
    op.drop_index("idx_treatment_consumables_clinic", table_name="treatment_consumables")
    op.drop_table("treatment_consumables")
