"""Add clinic templates, signing links and immutable consent evidence."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "doc_0002"
down_revision = "doc_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "consent_templates",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("clinic_id", uuid, sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_consent_templates_clinic_id", "consent_templates", ["clinic_id"])
    op.create_table(
        "consent_signing_links",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("clinic_id", uuid, sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column(
            "document_id",
            uuid,
            sa.ForeignKey("generated_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("purpose", sa.String(12), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False, server_default="es"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("purpose IN ('sign', 'revoke')", name="ck_consent_link_purpose"),
    )
    op.create_index("ix_consent_signing_links_clinic_id", "consent_signing_links", ["clinic_id"])
    op.create_index(
        "ix_consent_signing_links_document_id", "consent_signing_links", ["document_id"]
    )
    op.create_table(
        "consent_evidence",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("clinic_id", uuid, sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column(
            "document_id",
            uuid,
            sa.ForeignKey("generated_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(12), nullable=False),
        sa.Column("signer_name", sa.String(200), nullable=False),
        sa.Column("relationship_to_patient", sa.String(30), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.CheckConstraint("purpose IN ('sign', 'revoke')", name="ck_consent_evidence_purpose"),
    )
    op.create_index("ix_consent_evidence_clinic_id", "consent_evidence", ["clinic_id"])
    op.create_index("ix_consent_evidence_document_id", "consent_evidence", ["document_id"])
    op.create_index(
        "uq_consent_evidence_document_purpose",
        "consent_evidence",
        ["document_id", "purpose"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("consent_evidence")
    op.drop_table("consent_signing_links")
    op.drop_table("consent_templates")
