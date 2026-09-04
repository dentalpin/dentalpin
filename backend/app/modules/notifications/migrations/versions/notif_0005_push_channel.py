"""notifications: WebPush channel (T6).

Tables:
    - ``notification_push_subscriptions`` — patient browser subscriptions.
Columns:
    - ``notification_preferences.push_enabled`` — per-patient opt-out.

Lives on the ``notifications`` Alembic branch (ADR 0002), chained on
``notif_0004``.

Revision ID: notif_0005
Revises: notif_0004
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "notif_0005"
down_revision: str | None = "notif_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_push_subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=False),
        sa.Column("keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
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
        "ix_push_subscriptions_clinic_id",
        "notification_push_subscriptions",
        ["clinic_id"],
    )
    op.create_index(
        "ix_push_subscriptions_clinic_patient",
        "notification_push_subscriptions",
        ["clinic_id", "patient_id"],
    )
    op.create_index(
        "uq_push_subscriptions_clinic_endpoint",
        "notification_push_subscriptions",
        ["clinic_id", "endpoint"],
        unique=True,
    )
    op.add_column(
        "notification_preferences",
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("notification_preferences", "push_enabled")
    op.drop_index(
        "uq_push_subscriptions_clinic_endpoint", table_name="notification_push_subscriptions"
    )
    op.drop_index(
        "ix_push_subscriptions_clinic_patient", table_name="notification_push_subscriptions"
    )
    op.drop_index("ix_push_subscriptions_clinic_id", table_name="notification_push_subscriptions")
    op.drop_table("notification_push_subscriptions")
