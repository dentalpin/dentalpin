"""Configurable default reception duration per visit reason."""

import sqlalchemy as sa

from alembic import op

revision = "ob_0002"
down_revision = "ob_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("first_visit_minutes", "checkup_minutes"):
        op.add_column("online_booking_settings", sa.Column(name, sa.Integer(), nullable=True))
        op.create_check_constraint(
            f"ck_ob_{name}",
            "online_booking_settings",
            f"{name} IS NULL OR {name} BETWEEN 5 AND 480",
        )


def downgrade() -> None:
    for name in ("checkup_minutes", "first_visit_minutes"):
        op.drop_constraint(f"ck_ob_{name}", "online_booking_settings", type_="check")
        op.drop_column("online_booking_settings", name)
