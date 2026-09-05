"""notifications: SMS channel support (#231 PR1).

Adds the per-patient SMS opt-in (``sms_enabled`` + ``sms_opt_in_at``,
mirroring WhatsApp) and the per-clinic SMS daily cap
(``sms_daily_limit``). No data migration: new columns default so
existing rows stay reachable and uncapped until an admin changes them.

Revision ID: notif_0005
Revises: notif_0004
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "notif_0005"
down_revision: str | None = "notif_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "notification_preferences",
        sa.Column("sms_opt_in_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "clinic_notification_settings",
        sa.Column("sms_daily_limit", sa.Integer(), nullable=False, server_default="100"),
    )


def downgrade() -> None:
    op.drop_column("clinic_notification_settings", "sms_daily_limit")
    op.drop_column("notification_preferences", "sms_opt_in_at")
    op.drop_column("notification_preferences", "sms_enabled")
