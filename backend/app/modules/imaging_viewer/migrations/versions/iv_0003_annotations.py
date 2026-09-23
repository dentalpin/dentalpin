"""imaging_viewer: human annotation overlays (T2).

Tables:
    - ``imaging_annotations`` — ruler/freehand/note overlays on studies.
      Normalized 0-1 coordinates + optional mm values; originals immutable.

Lives on the ``imaging_viewer`` Alembic branch (ADR 0002), chained on
``iv_0002``. Display rules follow ``docs/technical/pano-overlay-design.md``
(toggleable layers, visualization-aid caption, dentist-write/read-view).

Revision ID: iv_0003
Revises: iv_0002
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "iv_0003"
down_revision: str | None = "iv_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = ("med_0002",)


def upgrade() -> None:
    op.create_table(
        "imaging_annotations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("study_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("spacing_mm", sa.Float(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["study_id"], ["imaging_studies.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_imaging_annotations_clinic_id", "imaging_annotations", ["clinic_id"])
    op.create_index("ix_imaging_annotations_patient_id", "imaging_annotations", ["patient_id"])
    op.create_index("ix_imaging_annotations_study_id", "imaging_annotations", ["study_id"])
    op.create_index(
        "ix_imaging_annotations_study",
        "imaging_annotations",
        ["clinic_id", "study_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_imaging_annotations_study", table_name="imaging_annotations")
    op.drop_index("ix_imaging_annotations_study_id", table_name="imaging_annotations")
    op.drop_index("ix_imaging_annotations_patient_id", table_name="imaging_annotations")
    op.drop_index("ix_imaging_annotations_clinic_id", table_name="imaging_annotations")
    op.drop_table("imaging_annotations")
