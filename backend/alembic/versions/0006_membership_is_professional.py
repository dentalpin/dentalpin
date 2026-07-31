"""core — add clinic_memberships.is_professional.

"Professional" (appears in the agenda, has working hours, can be
assigned treatments) was derived from ``role IN ('dentist',
'hygienist')`` in six queries across core/agenda/schedules/
treatment_plan. That made role and profession the same axis, so an
admin who also practises — the norm in solo clinics — could not be
scheduled without a second user account (reported by users on
2026-07-31).

This promotes the fact to a column. Backfill marks existing
dentist/hygienist memberships as professionals, preserving current
behaviour exactly; admins flip their own checkbox from the users
admin screen afterwards.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clinic_memberships",
        sa.Column(
            "is_professional",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute(
        """
        UPDATE clinic_memberships
        SET is_professional = true
        WHERE role IN ('dentist', 'hygienist');
        """
    )


def downgrade() -> None:
    op.drop_column("clinic_memberships", "is_professional")
