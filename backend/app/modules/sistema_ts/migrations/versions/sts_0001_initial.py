"""sistema_ts: initial schema.

Four tables on the module's own Alembic branch ``sistema_ts`` (ADR 0002):
    - ``sistema_ts_settings`` — per-clinic credentials and identity.
    - ``sistema_ts_documents`` — one operation per fiscal document.
    - ``sistema_ts_patient_opposition`` — the patient's opposizione.
    - ``sistema_ts_item_types`` — tipoSpesa per catalog item.

FKs target ``billing`` (invoices), ``patients`` and ``catalog`` (all in
``manifest.depends``), so this revision ``depends_on`` their heads.

Revision ID: sts_0001
Revises:
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "sts_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("sistema_ts",)
depends_on: str | Sequence[str] | None = ("bil_0005", "pat_0003", "cat_0004")


def upgrade() -> None:
    op.create_table(
        "sistema_ts_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("environment", sa.String(length=10), nullable=False),
        sa.Column("username", sa.String(length=16), nullable=True),
        sa.Column("password_encrypted", sa.Text(), nullable=True),
        sa.Column("pincode_encrypted", sa.Text(), nullable=True),
        sa.Column("certificate_b64", sa.Text(), nullable=True),
        sa.Column("cf_proprietario", sa.String(length=16), nullable=True),
        sa.Column("codice_regione", sa.String(length=3), nullable=True),
        sa.Column("codice_asl", sa.String(length=3), nullable=True),
        sa.Column("codice_ssa", sa.String(length=10), nullable=True),
        sa.Column("dispositivo", sa.String(length=10), nullable=False, server_default="1"),
        sa.Column("default_tipo_spesa", sa.String(length=2), nullable=False, server_default="SR"),
        sa.Column("sync_from", sa.Date(), nullable=True),
        sa.Column("last_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_send_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sistema_ts_settings_clinic_id", "sistema_ts_settings", ["clinic_id"], unique=True
    )

    op.create_table(
        "sistema_ts_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("operation", sa.String(length=14), nullable=False),
        sa.Column("p_iva", sa.String(length=11), nullable=False),
        sa.Column("data_emissione", sa.Date(), nullable=False),
        sa.Column("dispositivo", sa.String(length=10), nullable=False),
        sa.Column("num_documento", sa.String(length=60), nullable=False),
        sa.Column("data_pagamento", sa.Date(), nullable=True),
        sa.Column("tipo_documento", sa.String(length=1), nullable=False),
        sa.Column("pagamento_tracciato", sa.String(length=2), nullable=False),
        sa.Column("flag_opposizione", sa.Boolean(), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("voci", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("refers_to_id", sa.UUID(), nullable=True),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_xml", sa.Text(), nullable=True),
        sa.Column("response_xml", sa.Text(), nullable=True),
        sa.Column("esito", sa.Integer(), nullable=True),
        sa.Column("protocollo", sa.String(length=20), nullable=True),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("environment", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["refers_to_id"], ["sistema_ts_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("clinic_id", "invoice_id", "patient_id", "state", "protocollo"):
        op.create_index(f"ix_sistema_ts_documents_{col}", "sistema_ts_documents", [col])
    op.create_index(
        "idx_sistema_ts_documents_clinic_state", "sistema_ts_documents", ["clinic_id", "state"]
    )
    op.create_index(
        "idx_sistema_ts_documents_clinic_created",
        "sistema_ts_documents",
        ["clinic_id", "created_at"],
    )
    op.create_index(
        "idx_sistema_ts_documents_invoice_op", "sistema_ts_documents", ["invoice_id", "operation"]
    )

    op.create_table(
        "sistema_ts_patient_opposition",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("opposed_since", sa.Date(), nullable=False),
        sa.Column("revoked_at", sa.Date(), nullable=True),
        sa.Column("recorded_by", sa.UUID(), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "patient_id", name="uq_sistema_ts_opposition_patient"),
    )
    op.create_index(
        "ix_sistema_ts_patient_opposition_clinic_id", "sistema_ts_patient_opposition", ["clinic_id"]
    )
    op.create_index(
        "ix_sistema_ts_patient_opposition_patient_id",
        "sistema_ts_patient_opposition",
        ["patient_id"],
    )

    op.create_table(
        "sistema_ts_item_types",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("catalog_item_id", sa.UUID(), nullable=False),
        sa.Column("tipo_spesa", sa.String(length=2), nullable=False),
        sa.Column("flag_tipo_spesa", sa.String(length=1), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["catalog_item_id"], ["treatment_catalog_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "catalog_item_id", name="uq_sistema_ts_item_type"),
    )
    op.create_index("ix_sistema_ts_item_types_clinic_id", "sistema_ts_item_types", ["clinic_id"])


def downgrade() -> None:
    op.drop_table("sistema_ts_item_types")
    op.drop_table("sistema_ts_patient_opposition")
    op.drop_table("sistema_ts_documents")
    op.drop_table("sistema_ts_settings")
