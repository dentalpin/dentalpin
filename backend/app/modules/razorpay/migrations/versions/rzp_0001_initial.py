"""razorpay module — initial schema.

Creates ``razorpay_settings`` (one row per clinic): mode, credentials
(Fernet-encrypted at rest), and webhook health fields. Only depends on
``clinics``, so this branch chains off the bare core anchor.

Revision ID: rzp_0001
Revises: 0001
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "rzp_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("razorpay",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "razorpay_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False, server_default="test"),
        sa.Column("key_id", sa.String(length=100), nullable=True),
        sa.Column("key_secret_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("webhook_secret_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_webhook_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_webhook_processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_webhook_event_type", sa.String(length=50), nullable=True),
        sa.Column("last_webhook_error", sa.Text(), nullable=True),
        sa.Column("last_webhook_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", name="uq_razorpay_settings_clinic"),
    )
    op.create_index("idx_razorpay_settings_clinic", "razorpay_settings", ["clinic_id"])


def downgrade() -> None:
    op.drop_table("razorpay_settings")
