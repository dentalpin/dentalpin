"""medical_reference: add surgery reference table.

Revision ID: mr_0002
Revises: mr_0001
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "mr_0002"
down_revision: str | None = "mr_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "medical_reference_surgery",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "clinic_id", "name", name="uq_medical_reference_surgery_clinic_name"
        ),
    )
    op.create_index(
        "ix_medical_reference_surgery_clinic_id", "medical_reference_surgery", ["clinic_id"]
    )
    op.create_index(
        "ix_medical_reference_surgery_is_active", "medical_reference_surgery", ["is_active"]
    )


def downgrade() -> None:
    op.drop_table("medical_reference_surgery")
