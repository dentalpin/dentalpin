"""supplier_ratings: initial schema.

Tables:
    - ``supplier_reviews`` — manual 1-5 communication rating per supplier.

Lives on its own Alembic branch (``supplier_ratings``) per ADR 0002.
Depends on ``contacts`` since the supplier FK points at ``contacts.id``.
Delivery/quality metrics are computed on demand from purchase order
history (runtime reads, no persisted tables), which is why the migration
only needs ``contacts`` even though the module also declares a dependency
on ``purchase_orders``.

Revision ID: rat_0001
Revises:
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "rat_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("supplier_ratings",)
depends_on: str | Sequence[str] | None = ("con_0001",)


def upgrade() -> None:
    op.create_table(
        "supplier_reviews",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("supplier_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("score >= 1 AND score <= 5", name="ck_supplier_reviews_score_range"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["contacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "supplier_id", name="uq_supplier_reviews_clinic_supplier"),
    )
    op.create_index("ix_supplier_reviews_clinic_id", "supplier_reviews", ["clinic_id"])
    op.create_index("ix_supplier_reviews_supplier_id", "supplier_reviews", ["supplier_id"])
    op.create_index(
        "ix_supplier_reviews_supplier_clinic", "supplier_reviews", ["supplier_id", "clinic_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_reviews_supplier_clinic", table_name="supplier_reviews")
    op.drop_index("ix_supplier_reviews_supplier_id", table_name="supplier_reviews")
    op.drop_index("ix_supplier_reviews_clinic_id", table_name="supplier_reviews")
    op.drop_table("supplier_reviews")
