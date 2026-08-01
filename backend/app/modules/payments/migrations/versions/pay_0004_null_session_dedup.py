"""payments — repair double-charged treatments + NULL-session idempotency.

Multi-session completion booked the money twice: each session inserted
its earned row (``item_session_completed``) and, on the last session,
``treatment_plan`` finalized the item via ``TreatmentService.perform``,
whose ``odontogram.treatment.performed`` event carried the full price
again — landing an extra ``source_session_id IS NULL`` row on top of
the per-session rows. The composite unique constraint never fired
because the NULL row and the session rows have different keys.

Repair + guard, in order:

1. Delete NULL-session rows for treatments that also have session rows
   (the duplicated full price — session rows are the source of truth).
2. Dedupe multiple NULL-session rows per treatment (Postgres treats
   NULLs as distinct in a plain unique constraint, so replayed events
   inserted freely), keeping the earliest.
3. Partial unique index so 2. can never regress.

The code fix (perform(publish_price=False) on plan finalization) stops
1. from regressing.

Revision ID: pay_0004
Revises: pay_0003
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "pay_0004"
down_revision: str | None = "pay_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM patient_earned_entries pe
        WHERE pe.source_session_id IS NULL
          AND EXISTS (
              SELECT 1 FROM patient_earned_entries s
              WHERE s.treatment_id = pe.treatment_id
                AND s.source_session_id IS NOT NULL
          )
        """
    )
    op.execute(
        """
        DELETE FROM patient_earned_entries pe
        WHERE pe.source_session_id IS NULL
          AND pe.id NOT IN (
              SELECT DISTINCT ON (treatment_id) id
              FROM patient_earned_entries
              WHERE source_session_id IS NULL
              ORDER BY treatment_id, performed_at, id
          )
        """
    )
    op.create_index(
        "uq_earned_treatment_null_session",
        "patient_earned_entries",
        ["treatment_id"],
        unique=True,
        postgresql_where="source_session_id IS NULL",
    )


def downgrade() -> None:
    # Deleted duplicate rows are not restorable — downgrade only drops
    # the guard index.
    op.drop_index("uq_earned_treatment_null_session", table_name="patient_earned_entries")
