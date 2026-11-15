"""Add optional assistant assignment to appointments.

Revision ID: ag_0007
Revises: ag_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ag_0007"
down_revision: str | None = "ag_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("assistant_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_appointments_assistant_id_users",
        "appointments",
        "users",
        ["assistant_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_appointments_assistant_id", "appointments", ["assistant_id"])


def downgrade() -> None:
    op.drop_index("ix_appointments_assistant_id", table_name="appointments")
    op.drop_constraint("fk_appointments_assistant_id_users", "appointments", type_="foreignkey")
    op.drop_column("appointments", "assistant_id")
