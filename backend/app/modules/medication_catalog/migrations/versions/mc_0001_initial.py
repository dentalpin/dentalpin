"""mc_0001_initial — medication_catalog_items.

Own Alembic branch (``medication_catalog``): no down_revision, never
touches another module's chain. The case-insensitive unique name guard
is enforced with a functional unique index so the concurrent-create
race is closed at the database level.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "mc_0001"
down_revision = None
branch_labels = ("medication_catalog",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medication_catalog_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "clinic_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clinics.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("dose", sa.String(length=50), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("form", sa.String(length=20), nullable=False, server_default="tablet"),
        sa.Column("requires_prescription", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_medication_catalog_clinic_id", "medication_catalog_items", ["clinic_id"])
    op.create_index(
        "uq_medication_catalog_clinic_name_ci",
        "medication_catalog_items",
        # clinic_id MUST be part of the index: names are unique PER CLINIC,
        # not globally — two clinics can both stock "Amoxicillin 500 mg".
        ["clinic_id", sa.text("lower(btrim(name))")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_medication_catalog_clinic_name_ci", table_name="medication_catalog_items")
    op.drop_index("ix_medication_catalog_clinic_id", table_name="medication_catalog_items")
    op.drop_table("medication_catalog_items")
