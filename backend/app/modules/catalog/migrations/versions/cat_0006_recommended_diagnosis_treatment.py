"""Add explicit diagnosis-to-treatment recommendations to the catalog.

Revision ID: cat_0006
Revises: cat_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cat_0006"
down_revision: str | None = "cat_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "treatment_catalog_items",
        sa.Column("recommended_treatment_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_catalog_items_recommended_treatment_id",
        "treatment_catalog_items",
        "treatment_catalog_items",
        ["recommended_treatment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_treatment_catalog_items_recommended_treatment_id",
        "treatment_catalog_items",
        ["recommended_treatment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_treatment_catalog_items_recommended_treatment_id",
        table_name="treatment_catalog_items",
    )
    op.drop_constraint(
        "fk_catalog_items_recommended_treatment_id",
        "treatment_catalog_items",
        type_="foreignkey",
    )
    op.drop_column("treatment_catalog_items", "recommended_treatment_id")
