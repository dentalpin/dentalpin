"""tc_0001_initial — treatment_consumables junction table.

Own Alembic branch (``treatment_consumables``): no down_revision, never
touches another module's chain. DB-level FKs into ``catalog`` and
``inventory`` tables are intentional (CI-enforced cross-module FKs per
the depends declaration) — ``depends_on = ("cat_0004", "inv_0001")``
pins migration-graph ordering so a fresh ``upgrade heads`` creates the
referenced tables first and dependent teardown is graph-visible.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "tc_0001"
down_revision = None
branch_labels = ("treatment_consumables",)
depends_on = ("cat_0004", "inv_0001")


def upgrade() -> None:
    op.create_table(
        "treatment_consumables",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "clinic_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clinics.id"),
            nullable=False,
        ),
        sa.Column(
            "catalog_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("treatment_catalog_items.id"),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("inventory_items.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "clinic_id",
            "catalog_item_id",
            "inventory_item_id",
            name="uq_treatment_consumables_link",
        ),
    )
    op.create_index("ix_treatment_consumables_clinic_id", "treatment_consumables", ["clinic_id"])
    op.create_index(
        "ix_treatment_consumables_catalog_item_id",
        "treatment_consumables",
        ["catalog_item_id"],
    )
    op.create_index(
        "ix_treatment_consumables_inventory_item_id",
        "treatment_consumables",
        ["inventory_item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_treatment_consumables_inventory_item_id", table_name="treatment_consumables")
    op.drop_index("ix_treatment_consumables_catalog_item_id", table_name="treatment_consumables")
    op.drop_index("ix_treatment_consumables_clinic_id", table_name="treatment_consumables")
    op.drop_table("treatment_consumables")
