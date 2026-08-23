"""inventory: initial schema.

Tables:
    - ``inventory_categories`` — per-clinic item grouping.
    - ``inventory_items`` — stock items with quantity tracking.

Lives on its own Alembic branch (``inventory``) per ADR 0002.

Revision ID: inv_0001
Revises:
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "inv_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("inventory",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inventory_categories_clinic_id"),
        "inventory_categories",
        ["clinic_id"],
    )
    op.create_index(
        "ix_inventory_categories_clinic_name",
        "inventory_categories",
        ["clinic_id", "name"],
        unique=True,
    )

    op.create_table(
        "inventory_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("min_quantity", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("supplier", sa.String(length=200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_low_stock", sa.Boolean(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["inventory_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inventory_items_clinic_id"),
        "inventory_items",
        ["clinic_id"],
    )
    op.create_index(
        "ix_inventory_items_clinic_code",
        "inventory_items",
        ["clinic_id", "code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_inventory_items_clinic_category"),
        "inventory_items",
        ["clinic_id", "category_id"],
    )
    op.create_index(
        op.f("ix_inventory_items_status"),
        "inventory_items",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_inventory_items_status"), table_name="inventory_items")
    op.drop_index(op.f("ix_inventory_items_clinic_category"), table_name="inventory_items")
    op.drop_index("ix_inventory_items_clinic_code", table_name="inventory_items")
    op.drop_index(op.f("ix_inventory_items_clinic_id"), table_name="inventory_items")
    op.drop_table("inventory_items")
    op.drop_index("ix_inventory_categories_clinic_name", table_name="inventory_categories")
    op.drop_index(op.f("ix_inventory_categories_clinic_id"), table_name="inventory_categories")
    op.drop_table("inventory_categories")
