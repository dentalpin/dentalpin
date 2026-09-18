"""staff_attendance: record the acting user on each punch.

Adds nullable ``attendance_events.created_by`` (FK ``users.id``) so a
working-time record always knows who recorded it. Nullable because rows
written before this column existed stay valid.

Revision ID: satt_0002
Revises: satt_0001
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "satt_0002"
down_revision: str | None = "satt_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "attendance_events",
        sa.Column("created_by", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_attendance_events_created_by",
        "attendance_events",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_index("ix_attendance_events_created_by", "attendance_events", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_attendance_events_created_by", table_name="attendance_events")
    op.drop_constraint("fk_attendance_events_created_by", "attendance_events", type_="foreignkey")
    op.drop_column("attendance_events", "created_by")
