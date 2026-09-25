"""imaging_ai: initial schema.

Tables:
    - ``imaging_ai_jobs`` — on-demand AI segmentation job queue + audit trail.

Lives on its own Alembic branch (``imaging_ai``) per ADR 0002.
Depends on ``media`` (``med_0002`` head): artifacts land as media documents.
``document_id`` / ``series_document_ids`` stay FK-free UUIDs (no dependency
on the local-only ``imaging_viewer`` branch): resolution is clinic-scoped
at execution time.

Revision ID: aij_0001
Revises:
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "aij_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("imaging_ai",)
depends_on: str | Sequence[str] | None = ("med_0002",)


def upgrade() -> None:
    op.create_table(
        "imaging_ai_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column(
            "series_document_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("backend", sa.String(length=40), nullable=False, server_default="pano"),
        sa.Column(
            "model_id",
            sa.String(length=200),
            nullable=False,
            server_default="dental-pano-ai",
        ),
        sa.Column(
            "model_version", sa.String(length=40), nullable=False, server_default="s3-weights"
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("queued_by", sa.UUID(), nullable=True),
        sa.Column(
            "review_status", sa.String(length=20), nullable=False, server_default="pending_review"
        ),
        sa.Column("confirmed_by", sa.UUID(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("log_excerpt", sa.String(length=4000), nullable=True),
        sa.Column("error", sa.String(length=1000), nullable=True),
        sa.Column(
            "artifact_document_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["queued_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_imaging_ai_jobs_clinic_id", "imaging_ai_jobs", ["clinic_id"])
    op.create_index("ix_imaging_ai_jobs_patient_id", "imaging_ai_jobs", ["patient_id"])
    op.create_index(
        "ix_imaging_ai_jobs_clinic_patient",
        "imaging_ai_jobs",
        ["clinic_id", "patient_id"],
    )
    op.create_index(
        "ix_imaging_ai_jobs_status",
        "imaging_ai_jobs",
        ["clinic_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_imaging_ai_jobs_status", table_name="imaging_ai_jobs")
    op.drop_index("ix_imaging_ai_jobs_clinic_patient", table_name="imaging_ai_jobs")
    op.drop_index("ix_imaging_ai_jobs_patient_id", table_name="imaging_ai_jobs")
    op.drop_index("ix_imaging_ai_jobs_clinic_id", table_name="imaging_ai_jobs")
    op.drop_table("imaging_ai_jobs")
