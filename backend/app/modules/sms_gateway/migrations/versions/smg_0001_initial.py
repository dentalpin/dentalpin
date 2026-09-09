"""sms_gateway: initial schema.

Tables:
    - ``sms_gateway_settings`` — per-clinic provider configuration.

Lives on its own Alembic branch (``sms_gateway``). No ``depends_on``:
like ``whatsapp_kapso`` it references core auth only.

Revision ID: smg_0001
Revises:
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "smg_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("sms_gateway",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sms_gateway_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="log"),
        sa.Column("account_sid_encrypted", sa.Text(), nullable=True),
        sa.Column("auth_token_encrypted", sa.Text(), nullable=True),
        sa.Column("from_number", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", name="uq_sms_gateway_settings_clinic"),
    )
    op.create_index("ix_sms_gateway_settings_clinic_id", "sms_gateway_settings", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("ix_sms_gateway_settings_clinic_id", table_name="sms_gateway_settings")
    op.drop_table("sms_gateway_settings")
