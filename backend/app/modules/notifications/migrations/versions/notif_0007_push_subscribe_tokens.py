"""notifications: patient subscribe tokens for the WebPush patient flow.

Table ``notification_push_subscribe_tokens`` — staff-minted, single-use,
24 h random-UUID tokens redeemed by the patient's browser with its
subscription. Lives on the ``notifications`` Alembic branch (ADR 0002),
chained on ``notif_0006``.

Revision ID: notif_0007
Revises: notif_0006
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "notif_0007"
down_revision: str | None = "notif_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_push_subscribe_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_push_subscribe_tokens_clinic_id",
        "notification_push_subscribe_tokens",
        ["clinic_id"],
    )
    op.create_index(
        "ix_push_subscribe_tokens_patient_id",
        "notification_push_subscribe_tokens",
        ["patient_id"],
    )
    op.create_index(
        "uq_push_subscribe_tokens_token",
        "notification_push_subscribe_tokens",
        ["token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_push_subscribe_tokens_token", table_name="notification_push_subscribe_tokens")
    op.drop_index(
        "ix_push_subscribe_tokens_patient_id", table_name="notification_push_subscribe_tokens"
    )
    op.drop_index(
        "ix_push_subscribe_tokens_clinic_id", table_name="notification_push_subscribe_tokens"
    )
    op.drop_table("notification_push_subscribe_tokens")
