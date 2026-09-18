"""treasury: record the acting user on each entry.

Adds nullable ``treasury_entries.created_by`` (FK ``users.id``) so every
money movement knows who recorded it. Nullable because rows written
before this column existed stay valid.

Revision ID: tre_0002
Revises: tre_0001
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "tre_0002"
down_revision: str | None = "tre_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "treasury_entries",
        sa.Column("created_by", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_treasury_entries_created_by",
        "treasury_entries",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_index("ix_treasury_entries_created_by", "treasury_entries", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_treasury_entries_created_by", table_name="treasury_entries")
    op.drop_constraint("fk_treasury_entries_created_by", "treasury_entries", type_="foreignkey")
    op.drop_column("treasury_entries", "created_by")
