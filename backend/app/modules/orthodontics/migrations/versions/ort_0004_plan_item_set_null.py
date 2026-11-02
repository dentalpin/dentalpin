"""Orthodontics: a removed plan item unlinks the case instead of blocking (#750).

``fk_ortho_cases_item`` had no ``ondelete``, so removing the linked item
from a draft plan failed the DELETE with a 500. ``treatment_plan`` cannot
see this module (the dependency is one-way), and the case already treats
a missing item as "no installments", so the reference is cleared instead.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "ort_0004"
down_revision: str | None = "ort_0003"
branch_labels: str | Sequence[str] | None = None
# Recreates the FK into treatment_plan's table; same target as ort_0002.
depends_on: str | Sequence[str] | None = ("tp_0006",)


def upgrade() -> None:
    op.drop_constraint("fk_ortho_cases_item", "ortho_cases", type_="foreignkey")
    op.create_foreign_key(
        "fk_ortho_cases_item",
        "ortho_cases",
        "planned_treatment_items",
        ["plan_item_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_ortho_cases_item", "ortho_cases", type_="foreignkey")
    op.create_foreign_key(
        "fk_ortho_cases_item",
        "ortho_cases",
        "planned_treatment_items",
        ["plan_item_id"],
        ["id"],
    )
