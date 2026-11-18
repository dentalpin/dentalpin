"""Add the core patient access audit.

Revision ID: 0011
Revises: 0009
"""

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_access_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "clinic_id", sa.Uuid(), sa.ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("resource", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
    )
    op.create_index(
        "uq_patient_access_view_window",
        "patient_access_logs",
        ["clinic_id", "user_id", "patient_id", "resource", "window_start"],
        unique=True,
    )
    op.create_index(
        "ix_patient_access_patient",
        "patient_access_logs",
        ["clinic_id", "patient_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_patient_access_user",
        "patient_access_logs",
        ["clinic_id", "user_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_patient_access_retention",
        "patient_access_logs",
        ["clinic_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("patient_access_logs")
