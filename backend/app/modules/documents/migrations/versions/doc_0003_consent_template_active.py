"""Add ``is_active`` to consent templates so they can be archived."""

import sqlalchemy as sa

from alembic import op

revision = "doc_0003"
down_revision = "doc_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consent_templates",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("consent_templates", "is_active")
