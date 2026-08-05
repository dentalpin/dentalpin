"""Polymorphic attachments + photo metadata.

Adds the ``media_attachments`` table (generic owner_type/owner_id pair)
and extends ``documents`` with photo-aware columns:

- ``media_kind``        — UI rail (photo / xray / document / scan / video)
- ``media_category``    — taxonomy bucket (intraoral / extraoral / ...)
- ``media_subtype``     — leaf taxonomy node (frontal / panoramic / ...)
- ``captured_at``       — EXIF or manual capture timestamp
- ``paired_document_id``— before/after self-reference
- ``tags``              — free-form labels (JSONB array)

The companion legacy-drop migrations (``cn_0002``, ``tp_0004``) declare
``depends_on=("meds_0001",)`` so they always run after this one.

Revision ID: meds_0001
Revises: med_0001
Create Date: 2026-05-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "meds_0001"
down_revision: str | None = "med_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # documents — new photo-aware columns
    # ------------------------------------------------------------------
    op.add_column(
        "documents",
        sa.Column(
            "media_kind",
            sa.String(length=20),
            nullable=False,
            server_default="document",
        ),
    )
    op.add_column(
        "documents",
        sa.Column("media_category", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("media_subtype", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("paired_document_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    op.create_foreign_key(
        "fk_documents_paired_document_id",
        "documents",
        "documents",
        ["paired_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_documents_pair_not_self",
        "documents",
        "paired_document_id IS NULL OR paired_document_id <> id",
    )
    op.create_index(
        "idx_documents_clinic_patient_kind_captured",
        "documents",
        ["clinic_id", "patient_id", "media_kind", "captured_at"],
        unique=False,
    )

    # Best-guess backfill of media_kind from existing mime_type so the
    # gallery shows pre-existing image documents immediately. PDFs and
    # other non-image files stay as 'document'.
    op.execute(
        """
        UPDATE documents
           SET media_kind = 'photo'
         WHERE media_kind = 'document'
           AND mime_type LIKE 'image/%'
        """
    )

    # ------------------------------------------------------------------
    # media_attachments — generic polymorphic link table
    # ------------------------------------------------------------------
    op.create_table(
        "media_attachments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("owner_type", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "owner_type",
            "owner_id",
            name="uq_media_attachments_doc_owner",
        ),
    )
    op.create_index(
        "idx_media_attachments_owner",
        "media_attachments",
        ["clinic_id", "owner_type", "owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_media_attachments_clinic_id"),
        "media_attachments",
        ["clinic_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_media_attachments_document_id"),
        "media_attachments",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_media_attachments_document_id"), table_name="media_attachments")
    op.drop_index(op.f("ix_media_attachments_clinic_id"), table_name="media_attachments")
    op.drop_index("idx_media_attachments_owner", table_name="media_attachments")
    op.drop_table("media_attachments")

    op.drop_index("idx_documents_clinic_patient_kind_captured", table_name="documents")
    op.drop_constraint("ck_documents_pair_not_self", "documents", type_="check")
    op.drop_constraint("fk_documents_paired_document_id", "documents", type_="foreignkey")
    op.drop_column("documents", "tags")
    op.drop_column("documents", "paired_document_id")
    op.drop_column("documents", "captured_at")
    op.drop_column("documents", "media_subtype")
    op.drop_column("documents", "media_category")
    op.drop_column("documents", "media_kind")
