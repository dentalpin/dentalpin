"""staff_attendance: initial schema.

Single table ``attendance_events`` (clock in/out punches). FKs to core
``clinics.id`` / ``users.id`` only, so down_revision is core ``0001``
with no depends_on (staff_tasks pattern).

``created_by`` (the acting user, FK ``users.id``) ships in this
revision, NOT NULL — the module went out in a single release, so the
former ``satt_0002_created_by`` was folded back in (post-merge squash
per maintainer review on #492). Dev databases that already applied
``satt_0002`` must re-stamp the branch before upgrading.

Lives on its own Alembic branch (``staff_attendance``) per ADR 0002.

Revision ID: satt_0001
Revises: 0001
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "satt_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("staff_attendance",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attendance_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_attendance_events_created_by"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attendance_events_clinic_id", "attendance_events", ["clinic_id"])
    op.create_index("ix_attendance_events_user_id", "attendance_events", ["user_id"])
    op.create_index("ix_attendance_events_created_by", "attendance_events", ["created_by"])


def downgrade() -> None:
    op.drop_table("attendance_events")
