"""create payroll tables

Revision ID: payr_0001
Revises: 0001
Create Date: 2026-07-25

down_revision is "0001" (the confirmed real root, from patients'
pat_0001) — NOT chained onto any other module's branch. The project
already runs ~29 independent alembic heads (`alembic upgrade heads`,
plural, is the established norm), so a brand-new standalone module does
not need to descend from "the current head" of anything; it only needs
a down_revision that's a real, existing revision. "0001" is confirmed
real. This sidesteps the placeholder-guessing bug that affected two
previous phases (sact_0001/tcl_0001 both shipped with a fake "med_0002"
placeholder that had to be manually fixed after the fact).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "payr_0001"
down_revision = "0001"
branch_labels = ("payroll",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_payroll_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column("base_salary", sa.Numeric(10, 2), nullable=True),
        sa.Column("tax_regime", sa.String(length=50), nullable=True),
        sa.Column("bank_account_encrypted", sa.Text(), nullable=True),
        sa.Column("tax_id_encrypted", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_staff_payroll_profiles_user_id"),
    )
    op.create_index(
        "ix_staff_payroll_profiles_clinic_id", "staff_payroll_profiles", ["clinic_id"]
    )
    op.create_index(
        "ix_staff_payroll_profiles_user_id", "staff_payroll_profiles", ["user_id"]
    )

    op.create_table(
        "payroll_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "clinic_id", "month", "year", name="uq_payroll_period_clinic_month_year"
        ),
    )
    op.create_index("ix_payroll_periods_clinic_id", "payroll_periods", ["clinic_id"])

    op.create_table(
        "payroll_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column(
            "period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payroll_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "staff_payroll_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("staff_payroll_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gross_pay", sa.Numeric(10, 2), nullable=False),
        sa.Column("deductions", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("net_pay", sa.Numeric(10, 2), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "period_id", "staff_payroll_profile_id", name="uq_payroll_entry_period_staff"
        ),
    )
    op.create_index("ix_payroll_entries_clinic_id", "payroll_entries", ["clinic_id"])
    op.create_index("ix_payroll_entries_period_id", "payroll_entries", ["period_id"])
    op.create_index(
        "ix_payroll_entries_staff_payroll_profile_id",
        "payroll_entries",
        ["staff_payroll_profile_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_payroll_entries_staff_payroll_profile_id", table_name="payroll_entries")
    op.drop_index("ix_payroll_entries_period_id", table_name="payroll_entries")
    op.drop_index("ix_payroll_entries_clinic_id", table_name="payroll_entries")
    op.drop_table("payroll_entries")

    op.drop_index("ix_payroll_periods_clinic_id", table_name="payroll_periods")
    op.drop_table("payroll_periods")

    op.drop_index("ix_staff_payroll_profiles_user_id", table_name="staff_payroll_profiles")
    op.drop_index("ix_staff_payroll_profiles_clinic_id", table_name="staff_payroll_profiles")
    op.drop_table("staff_payroll_profiles")
