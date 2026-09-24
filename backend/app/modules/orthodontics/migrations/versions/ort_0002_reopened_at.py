"""orthodontics: record case reopens without losing the finish date.

Adds nullable ``ortho_cases.reopened_at``. ``finished_at`` is now set once
on first terminal entry and never cleared, so reopening a finished case
(``finished`` -> ``active``, the only legal exit from a terminal state)
stamps ``reopened_at`` instead of destroying the end-of-treatment record.
Slice-b recall/installment logic keys off ``reopened_at``.

Revision ID: ort_0002
Revises: ort_0001
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ort_0002"
down_revision: str | None = "ort_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ortho_cases",
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ortho_cases", "reopened_at")
