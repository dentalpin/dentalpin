"""Only publish logos re-encoded by the bounded raster sanitizer."""

import sqlalchemy as sa

from alembic import op

revision = "ob_0006"
down_revision = "ob_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "online_booking_settings",
        sa.Column("logo_sanitized", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("online_booking_settings", "logo_sanitized")
