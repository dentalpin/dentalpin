"""documents module — initial tables (letterhead, generated documents)

Revision ID: doc_0001
Revises: Pat-0003
Create Date: 2026-07-25

IMPORTANT: replace `down_revision` below with whatever the current
alembic head is on your branch at merge time (`alembic heads`), and
confirm `backend/alembic.ini` has this module's versions dir appended
to `version_locations` (bug #3 in the handoff doc) or this migration
will not be picked up at all.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "doc_0001"
down_revision = "pat_0003"
branch_labels = ("documents",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents_letterhead",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False, unique=True),
        sa.Column("practice_name", sa.String(255), nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=True),
        sa.Column("address", postgresql.JSONB, nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("registration_number", sa.String(100), nullable=True),
        sa.Column("footer_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "documents_generated",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("media_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_generated_clinic_id", "documents_generated", ["clinic_id"])
    op.create_index("ix_documents_generated_patient_id", "documents_generated", ["patient_id"])
    op.create_index("ix_documents_generated_document_type", "documents_generated", ["document_type"])


def downgrade() -> None:
    op.drop_index("ix_documents_generated_document_type", table_name="documents_generated")
    op.drop_index("ix_documents_generated_patient_id", table_name="documents_generated")
    op.drop_index("ix_documents_generated_clinic_id", table_name="documents_generated")
    op.drop_table("documents_generated")
    op.drop_table("documents_letterhead")
