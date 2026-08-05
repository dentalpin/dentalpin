"""migration_import — initial schema.

Five tables on the dedicated ``migration_import`` Alembic branch:

- ``migration_import_jobs``            — one row per uploaded DPMF
- ``migration_import_entity_mappings`` — idempotency keystone
- ``migration_import_file_stagings``   — ``_files`` manifest staging
- ``migration_import_warnings``        — DPMF warnings + ours
- ``migration_import_raw_entities``    — forward-compat catch-all

``depends_on=("meds_0001",)`` because ``file_stagings.resolved_document_id``
points at ``media.documents`` and that table must exist before us.

Revision ID: mig_0001
Revises: 0001
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "mig_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("migration_import",)
depends_on: str | Sequence[str] | None = ("meds_0001",)


def upgrade() -> None:
    op.create_table(
        "migration_import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="uploaded"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("source_system", sa.String(length=50), nullable=True),
        sa.Column("source_adapter_version", sa.String(length=30), nullable=True),
        sa.Column("exporter_tool", sa.String(length=50), nullable=True),
        sa.Column("exporter_version", sa.String(length=30), nullable=True),
        sa.Column("format_version", sa.String(length=20), nullable=True),
        sa.Column("tenant_label", sa.String(length=255), nullable=True),
        sa.Column("integrity_hash_declared", sa.String(length=128), nullable=True),
        sa.Column("integrity_hash_computed", sa.String(length=128), nullable=True),
        sa.Column("total_entities", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_entities", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_checkpoint", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "import_fiscal_compliance",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('uploaded','validating','validated','previewing',"
            "'executing','completed','failed')",
            name="ck_migration_import_job_status",
        ),
    )
    op.create_index(
        op.f("ix_migration_import_jobs_clinic_id"),
        "migration_import_jobs",
        ["clinic_id"],
    )

    op.create_table(
        "migration_import_entity_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_system", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("source_canonical_uuid", sa.String(length=36), nullable=False),
        sa.Column("dentalpin_table", sa.String(length=60), nullable=False),
        sa.Column("dentalpin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["migration_import_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "clinic_id",
            "source_system",
            "entity_type",
            "source_canonical_uuid",
            name="uq_migration_entity_mapping_lookup",
        ),
    )
    op.create_index(
        op.f("ix_migration_import_entity_mappings_clinic_id"),
        "migration_import_entity_mappings",
        ["clinic_id"],
    )
    op.create_index(
        op.f("ix_migration_import_entity_mappings_job_id"),
        "migration_import_entity_mappings",
        ["job_id"],
    )
    op.create_index(
        "ix_migration_entity_mapping_clinic_entity",
        "migration_import_entity_mappings",
        ["clinic_id", "entity_type"],
    )

    op.create_table(
        "migration_import_file_stagings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_uuid", sa.String(length=36), nullable=False),
        sa.Column("parent_entity_type", sa.String(length=50), nullable=False),
        sa.Column("parent_canonical_uuid", sa.String(length=36), nullable=False),
        sa.Column("relative_path", sa.String(length=1024), nullable=False),
        sa.Column("declared_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("mime_hint", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["migration_import_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "canonical_uuid", name="uq_migration_file_staging_canonical"),
        sa.CheckConstraint(
            "status IN ('pending','received','missing')",
            name="ck_migration_file_staging_status",
        ),
    )
    op.create_index(
        op.f("ix_migration_import_file_stagings_clinic_id"),
        "migration_import_file_stagings",
        ["clinic_id"],
    )
    op.create_index(
        op.f("ix_migration_import_file_stagings_job_id"),
        "migration_import_file_stagings",
        ["job_id"],
    )
    op.create_index(
        "ix_migration_file_staging_lookup",
        "migration_import_file_stagings",
        ["job_id", "sha256"],
    )

    op.create_table(
        "migration_import_warnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.String(length=100), nullable=True),
        sa.Column("severity", sa.String(length=10), nullable=False, server_default="info"),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["migration_import_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "severity IN ('info','warn','error')",
            name="ck_migration_import_warning_severity",
        ),
    )
    op.create_index(
        op.f("ix_migration_import_warnings_job_id"),
        "migration_import_warnings",
        ["job_id"],
    )

    op.create_table(
        "migration_import_raw_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("canonical_uuid", sa.String(length=36), nullable=False),
        sa.Column("source_system", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_source_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["migration_import_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id", "entity_type", "canonical_uuid", name="uq_migration_raw_entity"
        ),
    )
    op.create_index(
        op.f("ix_migration_import_raw_entities_clinic_id"),
        "migration_import_raw_entities",
        ["clinic_id"],
    )
    op.create_index(
        op.f("ix_migration_import_raw_entities_job_id"),
        "migration_import_raw_entities",
        ["job_id"],
    )
    op.create_index(
        "ix_migration_raw_entity_clinic_type",
        "migration_import_raw_entities",
        ["clinic_id", "entity_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_migration_raw_entity_clinic_type", table_name="migration_import_raw_entities")
    op.drop_index(
        op.f("ix_migration_import_raw_entities_job_id"),
        table_name="migration_import_raw_entities",
    )
    op.drop_index(
        op.f("ix_migration_import_raw_entities_clinic_id"),
        table_name="migration_import_raw_entities",
    )
    op.drop_table("migration_import_raw_entities")

    op.drop_index(
        op.f("ix_migration_import_warnings_job_id"), table_name="migration_import_warnings"
    )
    op.drop_table("migration_import_warnings")

    op.drop_index("ix_migration_file_staging_lookup", table_name="migration_import_file_stagings")
    op.drop_index(
        op.f("ix_migration_import_file_stagings_job_id"),
        table_name="migration_import_file_stagings",
    )
    op.drop_index(
        op.f("ix_migration_import_file_stagings_clinic_id"),
        table_name="migration_import_file_stagings",
    )
    op.drop_table("migration_import_file_stagings")

    op.drop_index(
        "ix_migration_entity_mapping_clinic_entity",
        table_name="migration_import_entity_mappings",
    )
    op.drop_index(
        op.f("ix_migration_import_entity_mappings_job_id"),
        table_name="migration_import_entity_mappings",
    )
    op.drop_index(
        op.f("ix_migration_import_entity_mappings_clinic_id"),
        table_name="migration_import_entity_mappings",
    )
    op.drop_table("migration_import_entity_mappings")

    op.drop_index(op.f("ix_migration_import_jobs_clinic_id"), table_name="migration_import_jobs")
    op.drop_table("migration_import_jobs")
