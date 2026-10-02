"""Orthodontics: one plan links to at most one case (issue #270 review).

A nullable unique constraint: transfer patients without a plan (NULL)
are unaffected, while a second link to the same plan fails at the
database instead of racing to a 500.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "ort_0003"
down_revision: str | None = "ort_0002"
branch_labels: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_ortho_cases_plan_link", "ortho_cases", ["treatment_plan_id"])


def downgrade() -> None:
    op.drop_constraint("uq_ortho_cases_plan_link", "ortho_cases", type_="unique")
