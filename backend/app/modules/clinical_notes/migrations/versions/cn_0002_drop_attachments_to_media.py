"""Move clinical_note_attachments → media.media_attachments.

The polymorphic attachment plumbing now lives in the ``media`` module.
This revision:

1. Backfills every row of ``clinical_note_attachments`` into
   ``media_attachments``.
2. For rows with ``note_id`` set (provenance pointer), inserts a SECOND
   row with ``owner_type='clinical_note'`` and ``owner_id=note_id`` so
   the note still surfaces its attached documents in the new model.
3. Drops the legacy table and its indexes.

App is pre-production; no rollback path is required and the downgrade
is best-effort (recreates an empty table — historical rows can be
recovered from media_attachments by inverting the backfill).

Sits on the ``clinical_notes`` branch and declares ``depends_on=
("meds_0001",)`` so ``media_attachments`` exists before we INSERT into
it.

Revision ID: cn_0002
Revises: cn_0001
Create Date: 2026-05-02

"""

from collections.abc import Sequence

from alembic import op

revision: str = "cn_0002"
down_revision: str | None = "cn_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = ("meds_0001",)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Copy primary owner rows
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO media_attachments (
            id, clinic_id, document_id, owner_type, owner_id,
            display_order, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            cna.clinic_id,
            cna.document_id,
            cna.owner_type,
            cna.owner_id,
            cna.display_order,
            cna.created_at,
            cna.updated_at
          FROM clinical_note_attachments cna
        ON CONFLICT (document_id, owner_type, owner_id) DO NOTHING
        """
    )

    # ------------------------------------------------------------------
    # 2. Provenance: rows with note_id get a second link to the note
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO media_attachments (
            id, clinic_id, document_id, owner_type, owner_id,
            display_order, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            cna.clinic_id,
            cna.document_id,
            'clinical_note',
            cna.note_id,
            cna.display_order,
            cna.created_at,
            cna.updated_at
          FROM clinical_note_attachments cna
         WHERE cna.note_id IS NOT NULL
        ON CONFLICT (document_id, owner_type, owner_id) DO NOTHING
        """
    )

    # ------------------------------------------------------------------
    # 3. Drop legacy table + indexes
    # ------------------------------------------------------------------
    op.drop_index(
        "idx_clinical_note_attachments_owner",
        table_name="clinical_note_attachments",
    )
    op.execute("DROP INDEX IF EXISTS ix_clinical_note_attachments_clinic_id")
    op.execute("DROP INDEX IF EXISTS ix_clinical_note_attachments_document_id")
    op.execute("DROP INDEX IF EXISTS ix_clinical_note_attachments_note_id")
    op.drop_table("clinical_note_attachments")


def downgrade() -> None:
    # Pre-production app: no rollback path is required. The data now
    # lives in media_attachments; attempting to reverse-engineer the
    # legacy schema row-by-row would silently lose the second-row
    # provenance backfill.
    raise NotImplementedError(
        "cn_0002 downgrade is intentionally not implemented — pre-prod, "
        "data lives in media_attachments going forward."
    )
