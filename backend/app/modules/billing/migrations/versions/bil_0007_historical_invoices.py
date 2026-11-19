"""Add a historical marker for invoices created by the migration importer."""

import sqlalchemy as sa

from alembic import op

revision = "bil_0007"
down_revision = "bil_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("is_historical", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("invoices", "is_historical")
