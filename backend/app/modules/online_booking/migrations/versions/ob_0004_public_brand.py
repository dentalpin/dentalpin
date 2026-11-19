"""Public page identity and copy per clinic."""

import sqlalchemy as sa

from alembic import op

revision = "ob_0004"
down_revision = "ob_0003"
branch_labels = None
depends_on = None

COLUMNS = (
    ("logo_url", 500),
    ("accent_color", 7),
    ("title_es", 120),
    ("intro_es", 300),
    ("title_en", 120),
    ("intro_en", 300),
)


def upgrade():
    for name, length in COLUMNS:
        op.add_column("online_booking_settings", sa.Column(name, sa.String(length), nullable=True))


def downgrade():
    for name, _ in reversed(COLUMNS):
        op.drop_column("online_booking_settings", name)
