"""leads: initial schema.

Tables:
    - leads — one row per enquiry that did not match an existing patient.
    - leads_intake_keys — exactly one key per clinic (SHA-256 hash only).
    - leads_settings — per-clinic daily cap + today's counter (PK is
      clinic_id: one row per clinic, like recalls.recall_settings).

Lives on its own Alembic branch (leads) per ADR 0002 — an isolated branch
is what makes manifest.removable=True legal.

clinics.id is core (created by "0001" itself); patients.id lives on the
pat_0001 -> pat_0002 -> pat_0003 chain with no branch label of its own,
so depends_on pins that chain before the FK is created (same pattern as
pseg_0001). There is deliberately **no** FK to recalls: a matched
enquiry's record is the recall itself, deduped inside the recalls module
on (patient, reason).

Revision ID: leads_0001
Revises: 0001
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "leads_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("leads",)
depends_on: str | Sequence[str] | None = ("pat_0003",)


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("motive", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("availability", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        # SET NULL: deleting a patient chart must not delete the enquiry
        # history that produced it.
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_clinic_id", "leads", ["clinic_id"])
    op.create_index("ix_leads_patient_id", "leads", ["patient_id"])
    # The list page's default query shape: status filter + created_at sort,
    # always scoped to one clinic.
    op.create_index(
        "ix_leads_clinic_status_created",
        "leads",
        ["clinic_id", "status", "created_at"],
    )

    op.create_table(
        "leads_intake_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=12), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", name="uq_leads_intake_keys_clinic"),
    )
    op.create_index("ix_leads_intake_keys_clinic_id", "leads_intake_keys", ["clinic_id"])
    op.create_index("ix_leads_intake_keys_key_hash", "leads_intake_keys", ["key_hash"], unique=True)

    op.create_table(
        "leads_settings",
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("daily_cap", sa.Integer(), server_default="200", nullable=False),
        sa.Column("day_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("day_count_date", sa.Date(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("clinic_id"),
    )


def downgrade() -> None:
    # Reverse order — settings and keys first, leads last.
    op.drop_table("leads_settings")
    op.drop_index("ix_leads_intake_keys_key_hash", table_name="leads_intake_keys")
    op.drop_index("ix_leads_intake_keys_clinic_id", table_name="leads_intake_keys")
    op.drop_table("leads_intake_keys")
    op.drop_index("ix_leads_clinic_status_created", table_name="leads")
    op.drop_index("ix_leads_patient_id", table_name="leads")
    op.drop_index("ix_leads_clinic_id", table_name="leads")
    op.drop_table("leads")
