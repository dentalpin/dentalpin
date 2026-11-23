"""Add verified consent gates for explicitly enrolled patients."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "notif_0009"
down_revision = "notif_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notification_preferences", sa.Column("verified_consents", JSONB()))


def downgrade() -> None:
    op.drop_column("notification_preferences", "verified_consents")
