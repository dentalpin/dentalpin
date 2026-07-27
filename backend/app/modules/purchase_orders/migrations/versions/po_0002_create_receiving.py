"""purchase_orders: create receiving tables.

Same branch as po_0001 (chains directly onto it — this is a follow-up
migration on an existing module, not a new branch, matching the
inv_0001 -> inv_0002 pattern from Phase 12).

Revision ID: po_0002
Revises: po_0001
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "po_0002"
down_revision = "po_0001"
branch_labels = None
depends_on = None

_QUALITY_STATUSES = ("good", "damaged", "expired", "wrong_item")


def upgrade() -> None:
    op.create_table(
        "purchase_order_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False
        ),
        sa.Column(
            "purchase_order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "received_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")
        ),
        sa.Column("received_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
    )
    op.create_index(
        "idx_po_receipts_purchase_order", "purchase_order_receipts", ["purchase_order_id"]
    )

    op.create_table(
        "purchase_order_receipt_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False
        ),
        sa.Column(
            "receipt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_order_receipts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "purchase_order_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_order_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity_received", sa.Numeric(10, 2), nullable=False),
        sa.Column("quality_status", sa.String(length=20), nullable=False, server_default="good"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "quality_status IN (" + ", ".join(f"'{s}'" for s in _QUALITY_STATUSES) + ")",
            name="ck_po_receipt_line_quality_valid",
        ),
    )
    op.create_index(
        "idx_po_receipt_lines_receipt", "purchase_order_receipt_lines", ["receipt_id"]
    )
    op.create_index(
        "idx_po_receipt_lines_po_item", "purchase_order_receipt_lines", ["purchase_order_item_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_po_receipt_lines_po_item", table_name="purchase_order_receipt_lines")
    op.drop_index("idx_po_receipt_lines_receipt", table_name="purchase_order_receipt_lines")
    op.drop_table("purchase_order_receipt_lines")

    op.drop_index("idx_po_receipts_purchase_order", table_name="purchase_order_receipts")
    op.drop_table("purchase_order_receipts")
