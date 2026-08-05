"""Move treatment_media → media.media_attachments + tag documents.

The per-plan-item attachment table is replaced by the generic
``media_attachments`` polymorphic owner pattern (``owner_type='plan_item'``).
The category/before/after semantics that used to live on
``treatment_media.media_type`` move onto the document itself via the
new ``media_kind`` / ``media_category`` / ``media_subtype`` columns:

| legacy media_type | new media_kind | media_category | media_subtype |
|-------------------|----------------|----------------|---------------|
| before            | photo          | clinical       | before        |
| after             | photo          | clinical       | after         |
| reference         | photo          | clinical       | reference     |
| xray              | xray           | xray           | panoramic*    |

* `xray → panoramic` is a rough default; the clinic re-classifies via
  `PATCH /documents/{id}/photo-metadata` if the original was bitewing,
  periapical, etc.

The legacy ``treatment_media.notes`` column is concatenated onto
``documents.description`` so no clinical narrative is lost.

Revision ID: tp_0004
Revises: tp_0003
Create Date: 2026-05-02

"""

from collections.abc import Sequence

from alembic import op

revision: str = "tp_0004"
down_revision: str | None = "tp_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = ("meds_0001",)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Update Document classification from legacy media_type
    # ------------------------------------------------------------------
    op.execute(
        """
        UPDATE documents d
           SET media_kind = 'photo',
               media_category = 'clinical',
               media_subtype = tm.media_type
          FROM treatment_media tm
         WHERE tm.document_id = d.id
           AND tm.media_type IN ('before', 'after', 'reference')
        """
    )
    op.execute(
        """
        UPDATE documents d
           SET media_kind = 'xray',
               media_category = 'xray',
               media_subtype = 'panoramic'
          FROM treatment_media tm
         WHERE tm.document_id = d.id
           AND tm.media_type = 'xray'
        """
    )

    # 1b. Preserve the per-row notes by appending to documents.description
    #     (one document may be referenced by multiple treatment_media
    #     rows in theory; in practice the unique-by-doc semantics held).
    op.execute(
        """
        UPDATE documents d
           SET description = COALESCE(d.description || E'\\n', '') || tm.notes
          FROM treatment_media tm
         WHERE tm.document_id = d.id
           AND tm.notes IS NOT NULL
           AND tm.notes <> ''
        """
    )

    # ------------------------------------------------------------------
    # 2. Backfill media_attachments rows with owner_type='plan_item'
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO media_attachments (
            id, clinic_id, document_id, owner_type, owner_id,
            display_order, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            tm.clinic_id,
            tm.document_id,
            'plan_item',
            tm.planned_treatment_item_id,
            tm.display_order,
            tm.created_at,
            tm.updated_at
          FROM treatment_media tm
        ON CONFLICT (document_id, owner_type, owner_id) DO NOTHING
        """
    )

    # ------------------------------------------------------------------
    # 3. Drop the legacy table and its indexes
    # ------------------------------------------------------------------
    op.execute("DROP INDEX IF EXISTS idx_treatment_media_document")
    op.execute("DROP INDEX IF EXISTS idx_treatment_media_item")
    op.execute("DROP INDEX IF EXISTS ix_treatment_media_clinic_id")
    op.execute("DROP INDEX IF EXISTS ix_treatment_media_document_id")
    op.execute("DROP INDEX IF EXISTS ix_treatment_media_planned_treatment_item_id")
    op.drop_table("treatment_media")


def downgrade() -> None:
    raise NotImplementedError(
        "tp_0004 downgrade is intentionally not implemented — pre-prod, "
        "treatment_media data lives in media_attachments going forward."
    )
