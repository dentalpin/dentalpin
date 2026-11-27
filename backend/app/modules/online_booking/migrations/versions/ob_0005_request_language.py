"""Store the language the requester booked in on each request (#1208)."""

import sqlalchemy as sa

from alembic import op

revision = "ob_0005"
down_revision = "ob_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("online_booking_requests", sa.Column("language", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("online_booking_requests", "language")
