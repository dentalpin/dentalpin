"""prescriptions: initial schema.

Tables ``prescriptions`` + ``prescription_items`` + ``prescription_templates``
+ ``prescriber_profiles``. FK to ``patients.id`` needs patients' chain
first — ``depends_on = ("pat_0003",)`` (patients has no branch label of
its own; same pattern as recalls/rec_0001).

Lives on its own Alembic branch (``prescriptions``) per ADR 0002.

Revision ID: psc_0001
Revises: 0001
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "psc_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("prescriptions",)
depends_on: str | Sequence[str] | None = ("pat_0003",)


def upgrade() -> None:
    op.create_table(
        "prescriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("prescriber_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("locale", sa.String(length=8), nullable=False, server_default="es"),
        sa.Column("prescriber_name", sa.String(length=200), nullable=True),
        sa.Column("license_number", sa.String(length=100), nullable=True),
        sa.Column("signature_document_id", sa.UUID(), nullable=True),
        sa.Column(
            "compliance_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prescriber_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prescriptions_clinic_id", "prescriptions", ["clinic_id"])
    op.create_index("ix_prescriptions_patient_id", "prescriptions", ["patient_id"])
    op.create_index("ix_prescriptions_prescriber_id", "prescriptions", ["prescriber_id"])

    op.create_table(
        "prescription_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("prescription_id", sa.UUID(), nullable=False),
        sa.Column("catalog_ref", sa.UUID(), nullable=True),
        sa.Column("medication_name", sa.String(length=150), nullable=False),
        sa.Column("dosage", sa.String(length=50), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("route", sa.String(length=50), nullable=True),
        sa.Column("frequency", sa.String(length=100), nullable=True),
        sa.Column("duration", sa.String(length=100), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["prescription_id"], ["prescriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_prescription_items_prescription_id", "prescription_items", ["prescription_id"]
    )
    op.create_index("ix_prescription_items_clinic_id", "prescription_items", ["clinic_id"])

    op.create_table(
        "prescription_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "items",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "name", name="uq_prescription_templates_clinic_name"),
    )
    op.create_index("ix_prescription_templates_clinic_id", "prescription_templates", ["clinic_id"])

    op.create_table(
        "prescriber_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("license_number", sa.String(length=100), nullable=True),
        sa.Column("signature_document_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "user_id", name="uq_prescriber_profiles_clinic_user"),
    )
    op.create_index("ix_prescriber_profiles_clinic_id", "prescriber_profiles", ["clinic_id"])
    op.create_index("ix_prescriber_profiles_user_id", "prescriber_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_table("prescriber_profiles")
    op.drop_table("prescription_templates")
    op.drop_table("prescription_items")
    op.drop_table("prescriptions")
