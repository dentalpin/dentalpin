"""Add ``signer_id_document`` to consent evidence (#1171).

Nullable: evidence signed before this migration has no ID document, and the
patient may leave it blank. The service requires it for guardians and
representatives. Rows stay immutable; the column is only written on insert.
"""

import sqlalchemy as sa

from alembic import op

revision = "doc_0004"
down_revision = "doc_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consent_evidence",
        sa.Column("signer_id_document", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("consent_evidence", "signer_id_document")
