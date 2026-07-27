"""supplier_ratings: create supplier_ratings table.

New independent branch.

⚠️ down_revision is "po_0002" (the newest confirmed head at write
time, from 13d). Run `alembic heads` BEFORE applying — if it's no
longer a head, update down_revision to whatever IS. This starts its
own branch, so it just needs to point at a revision that exists.

Revision ID: sr_0001
Revises: po_0002
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "sr_0001"
down_revision = "po_0002"
branch_labels = ("supplier_ratings",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False
        ),
        sa.Column(
            "supplier_contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id"),
            nullable=False,
        ),
        sa.Column("communication_score", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("rated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "rated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "communication_score >= 1 AND communication_score <= 5",
            name="ck_supplier_rating_score_range",
        ),
    )
    op.create_index("idx_supplier_ratings_supplier", "supplier_ratings", ["supplier_contact_id"])


def downgrade() -> None:
    op.drop_index("idx_supplier_ratings_supplier", table_name="supplier_ratings")
    op.drop_table("supplier_ratings")
