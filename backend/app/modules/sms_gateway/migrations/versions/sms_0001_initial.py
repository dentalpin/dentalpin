"""sms_gateway: initial schema.

Tables:
    - ``sms_gateway_settings`` — per-clinic provider config.
    - ``sms_outbox_log`` — every send attempt, placeholder or real.

Lives on its own Alembic branch (``sms_gateway``) per ADR 0002.

Revision ID: sms_0001
Revises:
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "sms_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("sms_gateway",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sms_gateway_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("provider_name", sa.String(length=50), nullable=False, server_default="placeholder"),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("sender_id", sa.String(length=50), nullable=True),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", name="uq_sms_gateway_settings_clinic"),
    )
    op.create_table(
        "sms_outbox_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("to_address", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider_name", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sms_gateway_settings_clinic_id", "sms_gateway_settings", ["clinic_id"])
    op.create_index("ix_sms_outbox_log_clinic_id", "sms_outbox_log", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("ix_sms_outbox_log_clinic_id", table_name="sms_outbox_log")
    op.drop_index("ix_sms_gateway_settings_clinic_id", table_name="sms_gateway_settings")
    op.drop_table("sms_outbox_log")
    op.drop_table("sms_gateway_settings")
