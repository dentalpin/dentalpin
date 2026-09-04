"""payroll: initial schema.

Tables:
    - ``payroll_profiles`` — per-staff payroll profile, bank/tax encrypted.
    - ``payroll_periods`` — monthly periods with a status lifecycle.
    - ``payroll_entries`` — per-employee raw entries per period.

Lives on its own Alembic branch (``payroll``). The only cross-module
references are FKs into core auth (``clinics.id``, ``users.id``), which
need no ``depends`` entry (core is not a module) — same pattern as
``staff_tasks``.

Revision ID: payr_0001
Revises:
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "payr_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("payroll",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payroll_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("payment_type", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("base_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("bank_account_encrypted", sa.Text(), nullable=True),
        sa.Column("tax_id_encrypted", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "user_id", name="uq_payroll_profiles_clinic_user"),
    )
    op.create_index("ix_payroll_profiles_clinic_id", "payroll_profiles", ["clinic_id"])
    op.create_index("ix_payroll_profiles_user_id", "payroll_profiles", ["user_id"])
    op.create_table(
        "payroll_periods",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "month", name="uq_payroll_periods_clinic_month"),
    )
    op.create_index("ix_payroll_periods_clinic_id", "payroll_periods", ["clinic_id"])
    op.create_table(
        "payroll_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("period_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("gross", sa.Numeric(12, 2), nullable=False),
        sa.Column("deductions", sa.Numeric(12, 2), nullable=False),
        sa.Column("net", sa.Numeric(12, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["payroll_periods.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_id", "user_id", name="uq_payroll_entries_period_user"),
    )
    op.create_index("ix_payroll_entries_clinic_id", "payroll_entries", ["clinic_id"])
    op.create_index("ix_payroll_entries_period_id", "payroll_entries", ["period_id"])


def downgrade() -> None:
    op.drop_index("ix_payroll_entries_period_id", table_name="payroll_entries")
    op.drop_index("ix_payroll_entries_clinic_id", table_name="payroll_entries")
    op.drop_table("payroll_entries")
    op.drop_index("ix_payroll_periods_clinic_id", table_name="payroll_periods")
    op.drop_table("payroll_periods")
    op.drop_index("ix_payroll_profiles_user_id", table_name="payroll_profiles")
    op.drop_index("ix_payroll_profiles_clinic_id", table_name="payroll_profiles")
    op.drop_table("payroll_profiles")
