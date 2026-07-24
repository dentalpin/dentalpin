"""medical_reference: add interaction and contraindication tables.

Revision ID: mr_0003
Revises: mr_0002
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "mr_0003"
down_revision: str | None = "mr_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "medical_reference_interaction",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("medication_a_id", sa.UUID(), nullable=False),
        sa.Column("medication_b_id", sa.UUID(), nullable=False),
        sa.Column("risk_note", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["medication_a_id"], ["medical_reference_medication.id"]),
        sa.ForeignKeyConstraint(["medication_b_id"], ["medical_reference_medication.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "clinic_id",
            "medication_a_id",
            "medication_b_id",
            name="uq_medical_reference_interaction_pair",
        ),
    )
    op.create_index(
        "ix_medical_reference_interaction_clinic_id", "medical_reference_interaction", ["clinic_id"]
    )
    op.create_index(
        "ix_medical_reference_interaction_medication_a_id",
        "medical_reference_interaction",
        ["medication_a_id"],
    )
    op.create_index(
        "ix_medical_reference_interaction_medication_b_id",
        "medical_reference_interaction",
        ["medication_b_id"],
    )
    op.create_index(
        "ix_medical_reference_interaction_is_active", "medical_reference_interaction", ["is_active"]
    )

    op.create_table(
        "medical_reference_contraindication",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("disease_id", sa.UUID(), nullable=False),
        sa.Column("medication_id", sa.UUID(), nullable=False),
        sa.Column("risk_note", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["disease_id"], ["medical_reference_disease.id"]),
        sa.ForeignKeyConstraint(["medication_id"], ["medical_reference_medication.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "clinic_id",
            "disease_id",
            "medication_id",
            name="uq_medical_reference_contraindication_pair",
        ),
    )
    op.create_index(
        "ix_medical_reference_contraindication_clinic_id",
        "medical_reference_contraindication",
        ["clinic_id"],
    )
    op.create_index(
        "ix_medical_reference_contraindication_disease_id",
        "medical_reference_contraindication",
        ["disease_id"],
    )
    op.create_index(
        "ix_medical_reference_contraindication_medication_id",
        "medical_reference_contraindication",
        ["medication_id"],
    )
    op.create_index(
        "ix_medical_reference_contraindication_is_active",
        "medical_reference_contraindication",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_table("medical_reference_contraindication")
    op.drop_table("medical_reference_interaction")
