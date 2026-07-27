"""purchase_orders: create purchase_orders + purchase_order_items.

New independent branch. Same shape as every prior new-module
migration in this project.

⚠️ down_revision is "si_0001" (13b's head). Run `alembic heads` BEFORE
applying — if it's no longer a head, update down_revision to whatever
IS. This starts its own branch, so it just needs to point at a
revision that exists.

Revision ID: po_0001
Revises: si_0001
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "po_0001"
down_revision = "si_0001"
branch_labels = ("purchase_orders",)
depends_on = None

_STATUSES = (
    "draft",
    "sent",
    "confirmed",
    "partially_received",
    "fully_received",
    "cancelled",
)


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False
        ),
        sa.Column("po_number", sa.String(length=50), nullable=False),
        sa.Column(
            "supplier_contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("order_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("shipping_cost", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in _STATUSES) + ")",
            name="ck_purchase_order_status_valid",
        ),
        sa.UniqueConstraint("clinic_id", "po_number", name="uq_purchase_order_clinic_number"),
    )
    op.create_index("idx_purchase_orders_clinic_status", "purchase_orders", ["clinic_id", "status"])
    op.create_index("idx_purchase_orders_supplier", "purchase_orders", ["supplier_contact_id"])

    op.create_table(
        "purchase_order_items",
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
            "inventory_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_items.id"),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("quantity_received", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
    )
    op.create_index("idx_po_items_purchase_order", "purchase_order_items", ["purchase_order_id"])
    op.create_index("idx_po_items_inventory_item", "purchase_order_items", ["inventory_item_id"])


def downgrade() -> None:
    op.drop_index("idx_po_items_inventory_item", table_name="purchase_order_items")
    op.drop_index("idx_po_items_purchase_order", table_name="purchase_order_items")
    op.drop_table("purchase_order_items")

    op.drop_index("idx_purchase_orders_supplier", table_name="purchase_orders")
    op.drop_index("idx_purchase_orders_clinic_status", table_name="purchase_orders")
    op.drop_table("purchase_orders")
