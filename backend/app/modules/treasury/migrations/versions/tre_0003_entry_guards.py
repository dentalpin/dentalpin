"""treasury: table-level guards on entry kind and amount.

``kind`` is restricted to the five known movement kinds and ``amount``
must be positive (payments precedent) — unknown kinds previously
contributed zero to balances silently.

Revision ID: tre_0003
Revises: tre_0002
Create Date: 2026-09-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "tre_0003"
down_revision: str | None = "tre_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_treasury_entries_kind",
        "treasury_entries",
        "kind IN ('transfer_out', 'transfer_in', 'correction_in', 'correction_out', 'opening')",
    )
    op.create_check_constraint(
        "ck_treasury_entries_amount_positive",
        "treasury_entries",
        "amount > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_treasury_entries_amount_positive",
        "treasury_entries",
        type_="check",
    )
    op.drop_constraint("ck_treasury_entries_kind", "treasury_entries", type_="check")
