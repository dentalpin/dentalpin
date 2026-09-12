"""sdi_it: PEC transport columns.

Per-clinic PEC mailbox (SMTP out to the SDI, IMAP in for the receipts)
on ``sdi_it_settings``; ``transport`` / ``message_id`` / ``next_attempt_at``
on ``sdi_it_records`` so the worker can retry with backoff and the UI can
show how a file reached the SDI.

Revision ID: sdi_0002
Revises: sdi_0001
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "sdi_0002"
down_revision: str | None = "sdi_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sdi_it_settings", sa.Column("pec_address", sa.String(length=255), nullable=True))
    op.add_column(
        "sdi_it_settings",
        sa.Column(
            "sdi_pec_address",
            sa.String(length=255),
            nullable=False,
            server_default="sdi01@pec.fatturapa.it",
        ),
    )
    op.add_column("sdi_it_settings", sa.Column("smtp_host", sa.String(length=255), nullable=True))
    op.add_column(
        "sdi_it_settings",
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="465"),
    )
    op.add_column(
        "sdi_it_settings", sa.Column("smtp_username", sa.String(length=255), nullable=True)
    )
    op.add_column("sdi_it_settings", sa.Column("smtp_password_encrypted", sa.Text(), nullable=True))
    op.add_column("sdi_it_settings", sa.Column("imap_host", sa.String(length=255), nullable=True))
    op.add_column(
        "sdi_it_settings",
        sa.Column("imap_port", sa.Integer(), nullable=False, server_default="993"),
    )
    op.add_column(
        "sdi_it_settings",
        sa.Column("imap_folder", sa.String(length=100), nullable=False, server_default="INBOX"),
    )
    op.add_column(
        "sdi_it_settings", sa.Column("last_pec_poll_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "sdi_it_settings", sa.Column("next_send_after", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "sdi_it_records", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("sdi_it_records", sa.Column("transport", sa.String(length=10), nullable=True))
    op.add_column("sdi_it_records", sa.Column("message_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    for col in ("message_id", "transport", "next_attempt_at"):
        op.drop_column("sdi_it_records", col)
    for col in (
        "next_send_after",
        "last_pec_poll_at",
        "imap_folder",
        "imap_port",
        "imap_host",
        "smtp_password_encrypted",
        "smtp_username",
        "smtp_port",
        "smtp_host",
        "sdi_pec_address",
        "pec_address",
    ):
        op.drop_column("sdi_it_settings", col)
