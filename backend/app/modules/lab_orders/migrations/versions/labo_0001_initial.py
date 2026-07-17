"""lab_orders: initial schema.

Tables:
    - ``lab_orders`` — work orders sent to external labs for a patient.

Cross-branch FKs to ``patients`` and ``contacts`` are safe here: both are
declared in this module's ``manifest.depends``, so the module loader
installs them first (ADR 0002).

Lives on its own Alembic branch (``lab_orders``) per ADR 0002.

Revision ID: labo_0001
Revises:
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "labo_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("lab_orders",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lab_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("lab_contact_id", sa.UUID(), nullable=False),
        sa.Column("work_type", sa.String(length=20), nullable=False),
        sa.Column("tooth_reference", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="sent"),
        sa.Column("sent_date", sa.Date(), nullable=False),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("received_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["lab_contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lab_orders_clinic_id", "lab_orders", ["clinic_id"])
    op.create_index("ix_lab_orders_patient_id", "lab_orders", ["patient_id"])
    op.create_index("ix_lab_orders_lab_contact_id", "lab_orders", ["lab_contact_id"])
    op.create_index("ix_lab_orders_work_type", "lab_orders", ["work_type"])
    op.create_index("ix_lab_orders_status", "lab_orders", ["status"])


def downgrade() -> None:
    op.drop_index("ix_lab_orders_status", table_name="lab_orders")
    op.drop_index("ix_lab_orders_work_type", table_name="lab_orders")
    op.drop_index("ix_lab_orders_lab_contact_id", table_name="lab_orders")
    op.drop_index("ix_lab_orders_patient_id", table_name="lab_orders")
    op.drop_index("ix_lab_orders_clinic_id", table_name="lab_orders")
    op.drop_table("lab_orders")
