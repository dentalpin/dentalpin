"""tasks: initial schema.

Tables:
    - ``tasks`` — staff handoff notes (assign, mark done).

FKs to ``users.id`` reference a core table, not another module, so no
cross-module dependency is involved.

Lives on its own Alembic branch (``tasks``) per ADR 0002.

Revision ID: task_0001
Revises:
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "task_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("tasks",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=10), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="open"),
        sa.Column("assigned_to", sa.UUID(), nullable=True),
        sa.Column("assigned_by", sa.UUID(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_clinic_id", "tasks", ["clinic_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_assigned_to", "tasks", ["assigned_to"])


def downgrade() -> None:
    op.drop_index("ix_tasks_assigned_to", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_clinic_id", table_name="tasks")
    op.drop_table("tasks")
