"""create staff_activity_logs table

Revision ID: sact_0001
Revises: med_0002
Create Date: 2026-07-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# NOTE: down_revision below is a placeholder. Run `alembic heads` in
# backend/ against your current branch and paste the result in, per
# PHASE10_INSTALL_GUIDE.md step 5.
revision = "sact_0001"
down_revision = "meds_0001"
branch_labels = ("staff_activity",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_activity_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinics.id"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_staff_activity_logs_clinic_id", "staff_activity_logs", ["clinic_id"])
    op.create_index("ix_staff_activity_logs_user_id", "staff_activity_logs", ["user_id"])
    op.create_index("ix_staff_activity_logs_action_type", "staff_activity_logs", ["action_type"])
    op.create_index("ix_staff_activity_logs_timestamp", "staff_activity_logs", ["timestamp"])
    op.create_index(
        "ix_staff_activity_logs_clinic_ts", "staff_activity_logs", ["clinic_id", "timestamp"]
    )


def downgrade() -> None:
    op.drop_index("ix_staff_activity_logs_clinic_ts", table_name="staff_activity_logs")
    op.drop_index("ix_staff_activity_logs_timestamp", table_name="staff_activity_logs")
    op.drop_index("ix_staff_activity_logs_action_type", table_name="staff_activity_logs")
    op.drop_index("ix_staff_activity_logs_user_id", table_name="staff_activity_logs")
    op.drop_index("ix_staff_activity_logs_clinic_id", table_name="staff_activity_logs")
    op.drop_table("staff_activity_logs")
