"""Optional booking quotas, form questions, redirect and hold buffers."""

import sqlalchemy as sa

from alembic import op

revision = "ob_0007"
down_revision = "ob_0006"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("daily_limit", "weekly_limit", "active_patient_limit"):
        op.add_column("online_booking_settings", sa.Column(name, sa.Integer(), nullable=True))
    op.add_column("online_booking_settings", sa.Column("redirect_url", sa.String(500)))
    for name in ("ask_existing_patient", "allow_comment"):
        op.add_column(
            "online_booking_settings",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    for name in ("buffer_before", "buffer_after"):
        op.add_column(
            "online_booking_requests",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
        )
    op.add_column("online_booking_requests", sa.Column("contact_first_name", sa.String(60)))
    op.add_column("online_booking_requests", sa.Column("contact_last_name", sa.String(59)))
    op.add_column("online_booking_requests", sa.Column("existing_patient", sa.Boolean()))
    op.add_column("online_booking_requests", sa.Column("comment", sa.String(500)))


def downgrade():
    for name in (
        "comment",
        "existing_patient",
        "contact_last_name",
        "contact_first_name",
        "buffer_after",
        "buffer_before",
    ):
        op.drop_column("online_booking_requests", name)
    for name in (
        "allow_comment",
        "ask_existing_patient",
        "redirect_url",
        "active_patient_limit",
        "weekly_limit",
        "daily_limit",
    ):
        op.drop_column("online_booking_settings", name)
