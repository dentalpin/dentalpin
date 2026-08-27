"""Initial schema for the documents module.

Creates the ``generated_documents`` table on the ``documents`` Alembic
branch.  Chains off the core ``0001`` anchor (ADR 0002).  No
cross-module foreign keys — ``patients.id`` and ``users.id`` are
referenced but this migration does not ``depends_on`` those branches;
FKs are enforced at the application level and via the ``depends``
manifest declaration.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "doc_0001"
down_revision = "0001"
branch_labels = ("documents",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generated_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "clinic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinics.id"),
            nullable=False,
        ),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "content",
            postgresql.JSONB(),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_generated_documents_clinic",
        "generated_documents",
        ["clinic_id"],
    )
    op.create_index(
        "ix_generated_documents_patient",
        "generated_documents",
        ["patient_id"],
    )
    op.create_index(
        "ix_generated_documents_clinic_type",
        "generated_documents",
        ["clinic_id", "document_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_generated_documents_clinic_type",
        table_name="generated_documents",
    )
    op.drop_index(
        "ix_generated_documents_patient",
        table_name="generated_documents",
    )
    op.drop_index(
        "ix_generated_documents_clinic",
        table_name="generated_documents",
    )
    op.drop_table("generated_documents")
