"""Orthodontics slice-b links (issue #270): plan, item, appointment, session pointer."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ort_0002"
down_revision: str | None = "ort_0001"
branch_labels: str | Sequence[str] | None = None
# Cross-module FK targets must exist first: depend on the target branch
# heads (depends_on must reference resolvable head revisions).
depends_on: str | Sequence[str] | None = ("tp_0006", "ag_0006")


def upgrade() -> None:
    op.add_column(
        "ortho_cases",
        sa.Column("treatment_plan_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "ortho_cases",
        sa.Column("plan_item_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_ortho_cases_plan", "ortho_cases", "treatment_plans", ["treatment_plan_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_ortho_cases_item",
        "ortho_cases",
        "planned_treatment_items",
        ["plan_item_id"],
        ["id"],
    )
    op.add_column(
        "ortho_controls",
        sa.Column("appointment_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "ortho_controls",
        sa.Column("session_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_ortho_controls_appointment",
        "ortho_controls",
        "appointments",
        ["appointment_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_ortho_controls_appointment", "ortho_controls", type_="foreignkey")
    op.drop_column("ortho_controls", "session_id")
    op.drop_column("ortho_controls", "appointment_id")
    op.drop_constraint("fk_ortho_cases_item", "ortho_cases", type_="foreignkey")
    op.drop_constraint("fk_ortho_cases_plan", "ortho_cases", type_="foreignkey")
    op.drop_column("ortho_cases", "plan_item_id")
    op.drop_column("ortho_cases", "treatment_plan_id")
