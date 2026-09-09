"""nav_online: initial schema.

Two tables (own Alembic branch ``nav_online`` per ADR 0002):
    - ``nav_online_settings`` — per-clinic technical user + software.
    - ``nav_online_records`` — one queued NAV data-report per invoice.

The ``invoice_id`` FK targets ``billing`` (in ``manifest.depends``), so
this revision ``depends_on`` billing's head for fresh-install ordering.

Revision ID: nav_0001
Revises:
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "nav_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("nav_online",)
depends_on: str | Sequence[str] | None = ("bil_0005",)


def upgrade() -> None:
    op.create_table(
        "nav_online_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("environment", sa.String(length=10), nullable=False),
        sa.Column("tax_number", sa.String(length=11), nullable=True),
        sa.Column("technical_user_login", sa.String(length=15), nullable=True),
        sa.Column("technical_user_password_encrypted", sa.Text(), nullable=True),
        sa.Column("signature_key_encrypted", sa.Text(), nullable=True),
        sa.Column("exchange_key_encrypted", sa.Text(), nullable=True),
        sa.Column("software_id", sa.String(length=18), nullable=False),
        sa.Column("software_dev_contact", sa.String(length=200), nullable=True),
        sa.Column("last_nav_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_send_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id"),
    )
    op.create_index("idx_nav_online_settings_clinic", "nav_online_settings", ["clinic_id"])

    op.create_table(
        "nav_online_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("operation", sa.String(length=10), nullable=False),
        sa.Column("invoice_number", sa.String(length=60), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("xml_payload", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_id", sa.String(length=40), nullable=True),
        sa.Column("nav_status", sa.String(length=20), nullable=True),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nav_online_records_clinic_id", "nav_online_records", ["clinic_id"])
    op.create_index("ix_nav_online_records_invoice_id", "nav_online_records", ["invoice_id"])
    op.create_index("ix_nav_online_records_state", "nav_online_records", ["state"])
    op.create_index(
        "ix_nav_online_records_transaction_id", "nav_online_records", ["transaction_id"]
    )
    op.create_index(
        "idx_nav_online_records_clinic_state", "nav_online_records", ["clinic_id", "state"]
    )
    op.create_index(
        "idx_nav_online_records_clinic_created", "nav_online_records", ["clinic_id", "created_at"]
    )


def downgrade() -> None:
    for ix in (
        "idx_nav_online_records_clinic_created",
        "idx_nav_online_records_clinic_state",
        "ix_nav_online_records_transaction_id",
        "ix_nav_online_records_state",
        "ix_nav_online_records_invoice_id",
        "ix_nav_online_records_clinic_id",
    ):
        op.drop_index(ix, table_name="nav_online_records")
    op.drop_table("nav_online_records")
    op.drop_index("idx_nav_online_settings_clinic", table_name="nav_online_settings")
    op.drop_table("nav_online_settings")
