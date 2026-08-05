"""notifications: add sms_enabled consent flag.

Part of Phase 6 (SMS gateway). Adds the opt-in flag SMS needs, mirroring
``whatsapp_enabled``. Chains onto the notifications module's own branch
(notif_0003 was the prior head) — this is a patch to an existing upstream
module, not a new module's first migration, so no new branch_labels.

Revision ID: notif_0004
Revises: notif_0003
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "notif_0004"
down_revision: str | None = "notif_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("notification_preferences", "sms_enabled")
