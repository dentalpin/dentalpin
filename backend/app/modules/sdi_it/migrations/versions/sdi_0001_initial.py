"""sdi_it: initial schema.

Two tables on the module's own Alembic branch ``sdi_it`` (ADR 0002):
    - ``sdi_it_settings`` — per-clinic FatturaPA/SDI configuration.
    - ``sdi_it_records`` — one FPR12 file per B2B invoice / credit note.

``invoice_id`` targets ``billing`` (in ``manifest.depends``), so this
revision ``depends_on`` billing's head for fresh-install ordering.

Revision ID: sdi_0001
Revises:
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "sdi_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("sdi_it",)
depends_on: str | Sequence[str] | None = ("bil_0005",)


def upgrade() -> None:
    op.create_table(
        "sdi_it_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("transport", sa.String(length=10), nullable=False),
        sa.Column("regime_fiscale", sa.String(length=4), nullable=False),
        sa.Column("bollo_virtuale", sa.Boolean(), nullable=False),
        sa.Column("riferimento_normativo", sa.String(length=100), nullable=False),
        sa.Column("progressivo_invio", sa.Integer(), nullable=False),
        sa.Column("last_receipt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sdi_it_settings_clinic_id", "sdi_it_settings", ["clinic_id"], unique=True)

    op.create_table(
        "sdi_it_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("tipo_documento", sa.String(length=4), nullable=False),
        sa.Column("invoice_number", sa.String(length=60), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("recipient_name", sa.String(length=200), nullable=True),
        sa.Column("recipient_tax_id", sa.String(length=20), nullable=True),
        sa.Column("codice_destinatario", sa.String(length=7), nullable=False),
        sa.Column("progressivo", sa.String(length=10), nullable=False),
        sa.Column("file_name", sa.String(length=60), nullable=False),
        sa.Column("xml_payload", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("sdi_identifier", sa.String(length=40), nullable=True),
        sa.Column("receipt_type", sa.String(length=4), nullable=True),
        sa.Column("receipt_xml", sa.Text(), nullable=True),
        sa.Column("receipt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sdi_it_records_clinic_id", "sdi_it_records", ["clinic_id"])
    op.create_index("ix_sdi_it_records_invoice_id", "sdi_it_records", ["invoice_id"])
    op.create_index("ix_sdi_it_records_file_name", "sdi_it_records", ["file_name"])
    op.create_index("ix_sdi_it_records_state", "sdi_it_records", ["state"])
    op.create_index("ix_sdi_it_records_sdi_identifier", "sdi_it_records", ["sdi_identifier"])
    op.create_index("idx_sdi_it_records_clinic_state", "sdi_it_records", ["clinic_id", "state"])
    op.create_index(
        "idx_sdi_it_records_clinic_created", "sdi_it_records", ["clinic_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("sdi_it_records")
    op.drop_table("sdi_it_settings")
