"""core — add clinics.timezone column.

DentalPin is global software and clinic-local times (opening hours,
appointment slots, billing date windows) need a timezone anchor that
modules can rely on. Previously the schedules module stored this under
``clinics.settings.timezone`` (JSONB), coupling a core concern to one
optional module's data blob.

This migration promotes timezone to a first-class, typed column on
``clinics`` with IANA default ``Europe/Madrid``. Existing rows backfill
from the JSONB key when present; the JSONB key is left intact for
now so a rollback is lossless.

Revision ID: 0002
Revises: notif_0001
Create Date: 2026-04-21

Legacy threading (#533): core 0002..0008 descend from the
notifications branch, so any downgrade crossing notif_0001 drags them
along. Safe only because every module on that spine is
removable=False (pinned by test_core_spine_modules_are_not_removable).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "notif_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clinics",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Europe/Madrid",
        ),
    )
    # Backfill from the pre-existing JSONB key where it was a valid
    # IANA id (contains a slash, e.g. "Europe/Madrid"). Bare values
    # like "Madrid" stay as the default — zoneinfo wouldn't resolve
    # them anyway.
    op.execute(
        """
        UPDATE clinics
        SET timezone = settings->>'timezone'
        WHERE settings ? 'timezone'
          AND settings->>'timezone' LIKE '%/%';
        """
    )


def downgrade() -> None:
    op.drop_column("clinics", "timezone")
