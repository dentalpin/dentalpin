"""leads: availability becomes structured (days + optional slot).

The external form used to send one free-text line. The front desk reads
availability as a week strip and the lead card shows which days are open at
a glance, which free text cannot do — so it is now a JSONB list of day codes
(mon..sun) plus an optional slot (morning | afternoon | evening).

Data note: the old free-text value cannot be parsed into days, so the column
is **dropped** rather than converted. This module has not shipped, so only
development rows are affected; re-post an enquiry to get the new shape. A
backfill would have to guess, and guessing a call window is worse than asking
the person again.

Lives on the module's own branch (``leads``); only the first revision
carries ``branch_labels``, so both stay None here.

Revision ID: leads_0002
Revises: leads_0001
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "leads_0002"
down_revision: str | None = "leads_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("availability_days", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column("availability_slot", sa.String(length=20), nullable=True),
    )
    op.drop_column("leads", "availability")


def downgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("availability", sa.String(length=200), nullable=True),
    )
    op.drop_column("leads", "availability_slot")
    op.drop_column("leads", "availability_days")
