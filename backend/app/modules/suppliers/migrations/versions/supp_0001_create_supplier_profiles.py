"""suppliers: create supplier_profiles table.

New independent branch — first migration for the brand-new `suppliers`
module, following the same shape as `treatment_consumables`' tcl_0001:
picks whatever revision was the effective head of *some* branch at
write time and forks its own ``branch_labels`` off it. Multiple heads
across the whole project is expected; apply with ``alembic upgrade
heads`` (plural), not ``head``.

⚠️ down_revision below is set to "inv_0002" (the newest confirmed head
at the time this was written, from Phase 12). Run `alembic heads`
BEFORE applying this — if inv_0002 is no longer a head (e.g. a later
inventory migration landed after this), update down_revision to
whatever IS currently head. Since this starts its own branch, it does
NOT need to point at the true global head — any single existing
revision works — but it does need to point at a revision that
actually exists, or Alembic will refuse to build the graph.

Revision ID: supp_0001
Revises: inv_0002
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "supp_0001"
down_revision = "inv_0002"
branch_labels = ("suppliers",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_profiles",
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False
        ),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("payment_terms", sa.String(length=100), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_supplier_profiles_clinic_id", "supplier_profiles", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("ix_supplier_profiles_clinic_id", table_name="supplier_profiles")
    op.drop_table("supplier_profiles")
