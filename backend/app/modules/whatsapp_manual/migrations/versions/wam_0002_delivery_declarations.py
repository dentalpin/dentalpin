"""whatsapp_manual: store staff delivery declarations."""

import sqlalchemy as sa

from alembic import op

revision = "wam_0002"
down_revision = "wam_0001"
branch_labels = None
depends_on = "notif_0001"


def upgrade() -> None:
    op.create_table(
        "whatsapp_manual_delivery_declarations",
        sa.Column("message_id", sa.UUID(), primary_key=True),
        sa.Column("marked_by_user_id", sa.UUID(), nullable=False),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["communication_messages.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("whatsapp_manual_delivery_declarations")
