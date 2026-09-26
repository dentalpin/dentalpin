"""imaging_viewer: initial schema.

Tables:
    - ``imaging_studies`` — DICOM study index rows pointing at media documents.
    - ``imaging_rvg_links`` - approved DICOM-identity → patient bindings.
    - ``imaging_rvg_imports`` - scanned files + approval-queue state.
    - ``imaging_annotations`` - ruler/freehand/note overlays on studies.

Single revision: the module ships in one release (squashed per review —
``iv_0002``/``iv_0003`` folded back in, same as #501/#502).

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
    # Idempotent indexing: one ACTIVE row per document (a shared
    # StudyInstanceUID across RVG frames must never duplicate rows).
    # Partial so archived rows keep their history (pay_0005 precedent).
    op.create_index(
        "uq_imaging_studies_clinic_document",
        "imaging_studies",
        ["clinic_id", "document_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

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
    op.drop_index("ix_imaging_rvg_imports_clinic_status", table_name="imaging_rvg_imports")
    op.drop_index("ix_imaging_rvg_imports_clinic_hash", table_name="imaging_rvg_imports")
    op.drop_index("ix_imaging_rvg_imports_clinic_id", table_name="imaging_rvg_imports")
    op.drop_table("imaging_rvg_imports")
    op.drop_index("ix_imaging_rvg_links_clinic_dicom", table_name="imaging_rvg_links")
    op.drop_index("ix_imaging_rvg_links_patient_id", table_name="imaging_rvg_links")
    op.drop_index("ix_imaging_rvg_links_clinic_id", table_name="imaging_rvg_links")
    op.drop_table("imaging_rvg_links")
    op.drop_index("uq_imaging_studies_clinic_document", table_name="imaging_studies")
    op.drop_index("ix_imaging_studies_study_uid", table_name="imaging_studies")
    op.drop_index("ix_imaging_studies_clinic_patient", table_name="imaging_studies")
    op.drop_index("ix_imaging_studies_document_id", table_name="imaging_studies")
    op.drop_index("ix_imaging_studies_patient_id", table_name="imaging_studies")
    op.drop_index("ix_imaging_studies_clinic_id", table_name="imaging_studies")
    op.drop_table("imaging_studies")
