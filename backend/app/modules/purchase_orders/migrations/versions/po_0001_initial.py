"""purchase_orders: initial schema.

Tables:
    - ``purchase_orders`` - PO header (supplier, status, expected date).
    - ``purchase_order_lines`` - per-line item + ordered/received quantities.
    - ``purchase_receipts`` - delivery batches (partial receives).
    - ``purchase_receipt_lines`` - per-line received quantity + quality.

Lives on its own Alembic branch (``purchase_orders``) per ADR 0002.
Depends on ``contacts`` (suppliers are contacts) and ``inventory``
(the PO lines target ``inventory_items``).

Revision ID: po_0001
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "po_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("purchase_orders",)
depends_on: str | Sequence[str] | None = ("con_0001", "inv_0002")


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("supplier_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_orders_clinic_id", "purchase_orders", ["clinic_id"])
    op.create_index("ix_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"])
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"])

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("purchase_order_id", sa.UUID(), nullable=False),
        sa.Column("inventory_item_id", sa.UUID(), nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("quantity_received", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("purchase_order_id", "inventory_item_id", name="uq_po_line_item"),
    )
    op.create_index("ix_purchase_order_lines_clinic_id", "purchase_order_lines", ["clinic_id"])
    op.create_index(
        "ix_purchase_order_lines_purchase_order_id", "purchase_order_lines", ["purchase_order_id"]
    )
    op.create_index(
        "ix_purchase_order_lines_inventory_item_id", "purchase_order_lines", ["inventory_item_id"]
    )

    op.create_table(
        "purchase_receipts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("purchase_order_id", sa.UUID(), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("received_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"]),
        sa.ForeignKeyConstraint(["received_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_receipts_clinic_id", "purchase_receipts", ["clinic_id"])
    op.create_index(
        "ix_purchase_receipts_purchase_order_id", "purchase_receipts", ["purchase_order_id"]
    )

    op.create_table(
        "purchase_receipt_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("receipt_id", sa.UUID(), nullable=False),
        sa.Column("purchase_order_line_id", sa.UUID(), nullable=False),
        sa.Column("quantity_received", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("quality", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["receipt_id"], ["purchase_receipts.id"]),
        sa.ForeignKeyConstraint(["purchase_order_line_id"], ["purchase_order_lines.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_receipt_lines_clinic_id", "purchase_receipt_lines", ["clinic_id"])
    op.create_index(
        "ix_purchase_receipt_lines_receipt_id", "purchase_receipt_lines", ["receipt_id"]
    )
    op.create_index(
        "ix_purchase_receipt_lines_purchase_order_line_id",
        "purchase_receipt_lines",
        ["purchase_order_line_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_purchase_receipt_lines_purchase_order_line_id", table_name="purchase_receipt_lines"
    )
    op.drop_index("ix_purchase_receipt_lines_receipt_id", table_name="purchase_receipt_lines")
    op.drop_index("ix_purchase_receipt_lines_clinic_id", table_name="purchase_receipt_lines")
    op.drop_table("purchase_receipt_lines")
    op.drop_index("ix_purchase_receipts_purchase_order_id", table_name="purchase_receipts")
    op.drop_index("ix_purchase_receipts_clinic_id", table_name="purchase_receipts")
    op.drop_table("purchase_receipts")
    op.drop_index("ix_purchase_order_lines_inventory_item_id", table_name="purchase_order_lines")
    op.drop_index("ix_purchase_order_lines_purchase_order_id", table_name="purchase_order_lines")
    op.drop_index("ix_purchase_order_lines_clinic_id", table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")
    op.drop_index("ix_purchase_orders_status", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_supplier_id", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_clinic_id", table_name="purchase_orders")
    op.drop_table("purchase_orders")
