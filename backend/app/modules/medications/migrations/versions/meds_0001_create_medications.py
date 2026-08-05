"""create medications table

Revision ID: meds_0001
Revises: 0005
Create Date: 2026-07-24

NOTE: this file is a REFERENCE COPY matching what's already live in the
real repo (confirmed via `Get-Content` from the user on 2026-07-25). The
real migration was hand-edited to resolve a revision conflict — down_revision
is "0005", not the "0001" this phase doc originally specified. DO NOT
apply/extract this file over the real one; it's included only so the
zip's contents stay internally consistent with what's actually running.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "meds_0001"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = ("medications",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    medication_unit_type = postgresql.ENUM(
        "mg", "g", "ml", "UI", "%", "other",
        name="medication_unit_type",
    )
    medication_form = postgresql.ENUM(
        "tablet", "capsule", "syrup", "gel", "mouthwash", "injection", "cream", "other",
        name="medication_form",
    )
    bind = op.get_bind()
    medication_unit_type.create(bind, checkfirst=True)
    medication_form.create(bind, checkfirst=True)

    op.create_table(
        "medications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("dose", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "unit",
            postgresql.ENUM(
                "mg", "g", "ml", "UI", "%", "other",
                name="medication_unit_type", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "form",
            postgresql.ENUM(
                "tablet", "capsule", "syrup", "gel", "mouthwash", "injection", "cream", "other",
                name="medication_form", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("times_per_day", sa.Integer(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("is_prescribed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_medications_clinic_id"), "medications", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_medications_name"), "medications", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_medications_name"), table_name="medications")
    op.drop_index(op.f("ix_medications_clinic_id"), table_name="medications")
    op.drop_table("medications")
    postgresql.ENUM(name="medication_form").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="medication_unit_type").drop(op.get_bind(), checkfirst=True)
