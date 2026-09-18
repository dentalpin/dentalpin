"""treasury: initial schema.

Tables ``treasury_accounts`` + ``treasury_entries``. FKs to core
``clinics.id`` only, so down_revision is core ``0001`` with no
depends_on (staff_tasks pattern).

Lives on its own Alembic branch (``treasury``) per ADR 0002.

Revision ID: tre_0001
Revises: 0001
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "tre_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("treasury",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "treasury_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False, server_default="cash"),
        sa.Column("opening_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "name", name="uq_treasury_accounts_clinic_name"),
    )
    op.create_index("ix_treasury_accounts_clinic_id", "treasury_accounts", ["clinic_id"])

    op.create_table(
        "treasury_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["treasury_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_treasury_entries_clinic_id", "treasury_entries", ["clinic_id"])
    op.create_index("ix_treasury_entries_account_id", "treasury_entries", ["account_id"])
    op.create_index("ix_treasury_entries_group_id", "treasury_entries", ["group_id"])


def downgrade() -> None:
    op.drop_table("treasury_entries")
    op.drop_table("treasury_accounts")
