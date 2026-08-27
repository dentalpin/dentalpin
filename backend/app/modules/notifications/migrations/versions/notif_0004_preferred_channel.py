"""notifications: clinic preferred channel + manual send channels.

Adds the clinic-wide channel columns on ``clinic_notification_settings``:
``preferred_channel`` (default wire for auto-sends), ``fallback_enabled``
(try the other installed channel when the preferred one is not viable) and
``manual_channels`` (which Send buttons the app renders). Also flips the
``notification_preferences.whatsapp_enabled`` server default to true —
WhatsApp becomes opt-out like email. Existing rows are NOT rewritten:
live clinics stay email-only until an admin changes the new fields.

Revision ID: notif_0004
Revises: notif_0003
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "notif_0004"
down_revision: str | None = "notif_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clinic_notification_settings",
        sa.Column(
            "preferred_channel",
            sa.String(length=20),
            nullable=False,
            server_default="email",
        ),
    )
    op.add_column(
        "clinic_notification_settings",
        sa.Column(
            "fallback_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "clinic_notification_settings",
        sa.Column(
            "manual_channels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[\"email\"]'::jsonb"),
        ),
    )
    # WhatsApp is opt-out, like email. New preference rows default to enabled;
    # existing rows keep whatever they already say (no data rewrite).
    op.alter_column(
        "notification_preferences",
        "whatsapp_enabled",
        server_default=sa.true(),
    )


def downgrade() -> None:
    op.alter_column("notification_preferences", "whatsapp_enabled", server_default=None)
    op.drop_column("clinic_notification_settings", "manual_channels")
    op.drop_column("clinic_notification_settings", "fallback_enabled")
    op.drop_column("clinic_notification_settings", "preferred_channel")
