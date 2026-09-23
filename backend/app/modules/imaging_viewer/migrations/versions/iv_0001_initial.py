"""imaging_viewer: initial schema.

Tables:
    - ``imaging_studies`` — DICOM study index rows pointing at media documents.

Lives on its own Alembic branch (``imaging_viewer``) per ADR 0002.
Depends on ``media`` (``med_0002`` head) since ``document_id`` is an FK to
``documents.id``.

Revision ID: iv_0001
Revises:
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "iv_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("imaging_viewer",)
depends_on: str | Sequence[str] | None = ("med_0002",)


def upgrade() -> None:
    op.create_table(
        "imaging_studies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("study_uid", sa.String(length=128), nullable=False),
        sa.Column("modality", sa.String(length=16), nullable=True),
        sa.Column("study_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dicom_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_imaging_studies_clinic_id", "imaging_studies", ["clinic_id"])
    op.create_index("ix_imaging_studies_patient_id", "imaging_studies", ["patient_id"])
    op.create_index("ix_imaging_studies_document_id", "imaging_studies", ["document_id"])
    op.create_index(
        "ix_imaging_studies_clinic_patient",
        "imaging_studies",
        ["clinic_id", "patient_id"],
    )
    op.create_index(
        "ix_imaging_studies_study_uid",
        "imaging_studies",
        ["clinic_id", "study_uid"],
    )


def downgrade() -> None:
    op.drop_index("ix_imaging_studies_study_uid", table_name="imaging_studies")
    op.drop_index("ix_imaging_studies_clinic_patient", table_name="imaging_studies")
    op.drop_index("ix_imaging_studies_document_id", table_name="imaging_studies")
    op.drop_index("ix_imaging_studies_patient_id", table_name="imaging_studies")
    op.drop_index("ix_imaging_studies_clinic_id", table_name="imaging_studies")
    op.drop_table("imaging_studies")
