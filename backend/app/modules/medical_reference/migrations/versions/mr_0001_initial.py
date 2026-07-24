"""medical_reference: initial schema — three lookup tables.

Revision ID: mr_0001
Revises:
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "mr_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("medical_reference",)
depends_on: str | Sequence[str] | None = None


def _create_lookup_table(name: str, extra_columns: list[sa.Column] | None = None) -> None:
    columns = [
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        *(extra_columns or []),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]
    op.create_table(
        name,
        *columns,
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "name", name=f"uq_{name}_clinic_name"),
    )
    op.create_index(f"ix_{name}_clinic_id", name, ["clinic_id"])
    op.create_index(f"ix_{name}_is_active", name, ["is_active"])


def upgrade() -> None:
    _create_lookup_table("medical_reference_allergy")
    _create_lookup_table("medical_reference_medication")
    _create_lookup_table(
        "medical_reference_disease",
        extra_columns=[sa.Column("is_apci", sa.Boolean(), nullable=False, server_default=sa.false())],
    )
    op.create_index(
        "ix_medical_reference_disease_is_apci", "medical_reference_disease", ["is_apci"]
    )


def downgrade() -> None:
    op.drop_table("medical_reference_disease")
    op.drop_table("medical_reference_medication")
    op.drop_table("medical_reference_allergy")
