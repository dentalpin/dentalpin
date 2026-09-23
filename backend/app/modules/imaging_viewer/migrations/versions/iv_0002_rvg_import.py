"""imaging_viewer: RVG auto-import queue (T1).

Tables:
    - ``imaging_rvg_links`` — approved DICOM-identity → patient bindings.
    - ``imaging_rvg_imports`` — scanned files + approval-queue state.

Lives on the ``imaging_viewer`` Alembic branch (ADR 0002), chained on
``iv_0001``. FKs stay inside declared deps (patients, media documents).

Revision ID: iv_0002
Revises: iv_0001
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "iv_0002"
down_revision: str | None = "iv_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = ("med_0002",)


def upgrade() -> None:
    op.create_table(
        "imaging_rvg_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("dicom_patient_id", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_imaging_rvg_links_clinic_id", "imaging_rvg_links", ["clinic_id"])
    op.create_index("ix_imaging_rvg_links_patient_id", "imaging_rvg_links", ["patient_id"])
    op.create_index(
        "ix_imaging_rvg_links_clinic_dicom",
        "imaging_rvg_links",
        ["clinic_id", "dicom_patient_id"],
        unique=True,
    )

    op.create_table(
        "imaging_rvg_imports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=True),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("study_id", sa.UUID(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("identity_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("suggested_patient_id", sa.UUID(), nullable=True),
        sa.Column("match_score", sa.Integer(), nullable=True),
        sa.Column("match_reason", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["study_id"], ["imaging_studies.id"]),
        sa.ForeignKeyConstraint(["suggested_patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_imaging_rvg_imports_clinic_id", "imaging_rvg_imports", ["clinic_id"])
    op.create_index(
        "ix_imaging_rvg_imports_clinic_hash",
        "imaging_rvg_imports",
        ["clinic_id", "content_hash"],
        unique=True,
    )
    op.create_index(
        "ix_imaging_rvg_imports_clinic_status",
        "imaging_rvg_imports",
        ["clinic_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_imaging_rvg_imports_clinic_status", table_name="imaging_rvg_imports")
    op.drop_index("ix_imaging_rvg_imports_clinic_hash", table_name="imaging_rvg_imports")
    op.drop_index("ix_imaging_rvg_imports_clinic_id", table_name="imaging_rvg_imports")
    op.drop_table("imaging_rvg_imports")
    op.drop_index("ix_imaging_rvg_links_clinic_dicom", table_name="imaging_rvg_links")
    op.drop_index("ix_imaging_rvg_links_patient_id", table_name="imaging_rvg_links")
    op.drop_index("ix_imaging_rvg_links_clinic_id", table_name="imaging_rvg_links")
    op.drop_table("imaging_rvg_links")
