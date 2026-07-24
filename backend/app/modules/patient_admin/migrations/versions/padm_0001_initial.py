"""patient_admin: initial schema.

Tables:
    - ``patient_admin_exemption_status`` — 1:1 insurance exemption status (APCI/ALD).
    - ``patient_admin_relationship`` — directed patient-to-patient link.

Both FK only to ``patients.id`` / ``clinics.id`` (core tables), no
cross-module FK, so no dependency on another module's branch.

Lives on its own Alembic branch (``patient_admin``) per ADR 0002.

Revision ID: padm_0001
Revises:
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "padm_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("patient_admin",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "patient_admin_exemption_status",
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("exemption_type", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("reference_number", sa.String(length=100), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("patient_id"),
    )
    op.create_index(
        "ix_patient_admin_exemption_status_clinic_id",
        "patient_admin_exemption_status",
        ["clinic_id"],
    )
    op.create_index(
        "ix_patient_admin_exemption_status_exemption_type",
        "patient_admin_exemption_status",
        ["exemption_type"],
    )

    op.create_table(
        "patient_admin_relationship",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("related_patient_id", sa.UUID(), nullable=False),
        sa.Column("relationship_type", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["related_patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "patient_id", "related_patient_id", name="uq_patient_admin_relationship_pair"
        ),
    )
    op.create_index(
        "ix_patient_admin_relationship_clinic_id", "patient_admin_relationship", ["clinic_id"]
    )
    op.create_index(
        "ix_patient_admin_relationship_patient_id", "patient_admin_relationship", ["patient_id"]
    )
    op.create_index(
        "ix_patient_admin_relationship_related_patient_id",
        "patient_admin_relationship",
        ["related_patient_id"],
    )


def downgrade() -> None:
    op.drop_table("patient_admin_relationship")
    op.drop_table("patient_admin_exemption_status")
