"""Core TOTP credentials, challenges, recovery codes and audit records."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clinics",
        sa.Column("mfa_policy", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column(
        "users", sa.Column("mfa_failed_attempts", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("users", sa.Column("mfa_locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("mfa_reenroll_required", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "auth_mfa_totp",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("last_counter", sa.Integer(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "auth_mfa_recovery_codes",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("code_hash", sa.String(64), primary_key=True),
    )
    op.create_table(
        "auth_mfa_challenges",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=True),
    )
    op.create_table(
        "auth_mfa_audit",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event", sa.String(32), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_mfa_audit_user_id", "auth_mfa_audit", ["user_id"])


def downgrade() -> None:
    op.drop_table("auth_mfa_audit")
    op.drop_table("auth_mfa_challenges")
    op.drop_table("auth_mfa_recovery_codes")
    op.drop_table("auth_mfa_totp")
    op.drop_column("users", "mfa_reenroll_required")
    op.drop_column("users", "mfa_locked_until")
    op.drop_column("users", "mfa_failed_attempts")
    op.drop_column("clinics", "mfa_policy")
