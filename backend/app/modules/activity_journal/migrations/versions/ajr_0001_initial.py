"""ajr_0001_initial — activity_journal_entries.

Own Alembic branch (``ajr``): no down_revision, never touches another
module's chain.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "ajr_0001"
down_revision = None
branch_labels = ("activity_journal",)
# NOTE (audit ARCH-01, reverted 2026-09-06): depends_on = ("0001",) was
# tried to order clinics first, but a depends_on edge also means
# "downgrade drags me" to the M6 roundtrip helper — and Alembic never
# downgrades core 0001 on a branch uninstall, so the helper wrongly
# expected these tables gone (inventory roundtrip red on CI). Bare-schema
# upgrade applies deterministically today; the ordering risk stays
# documented-latent instead of breaking a green gate.
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_journal_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "clinic_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clinics.id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("patient_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_table", sa.String(length=50), nullable=False),
        sa.Column("source_entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_activity_journal_clinic_id", "activity_journal_entries", ["clinic_id"])
    op.create_index(
        "ix_activity_journal_clinic_occurred",
        "activity_journal_entries",
        ["clinic_id", "occurred_at"],
    )
    op.create_index(
        "ix_activity_journal_clinic_event",
        "activity_journal_entries",
        ["clinic_id", "event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_activity_journal_clinic_event", table_name="activity_journal_entries")
    op.drop_index("ix_activity_journal_clinic_occurred", table_name="activity_journal_entries")
    op.drop_index("ix_activity_journal_clinic_id", table_name="activity_journal_entries")
    op.drop_table("activity_journal_entries")
