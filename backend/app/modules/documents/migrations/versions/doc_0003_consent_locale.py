"""Persist the selected language for each consent signing link."""

import sqlalchemy as sa

from alembic import op

revision = "doc_0003"
down_revision = "doc_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consent_signing_links",
        sa.Column("locale", sa.String(10), nullable=False, server_default="es"),
    )


def downgrade() -> None:
    op.drop_column("consent_signing_links", "locale")
