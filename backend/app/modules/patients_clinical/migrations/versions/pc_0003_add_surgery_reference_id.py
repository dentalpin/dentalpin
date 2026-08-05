"""patients_clinical: add reference_id to surgical_history.

Same rationale as pc_0002 — plain nullable UUID, no FK constraint, so this
(core) module keeps working standalone if medical_reference (community)
is ever removed.

This closes a real gap found while auditing the repo for the continuity
doc: the frontend (MedicalHistoryForm.vue) and medical_reference module
were already built expecting this column — the ORM model and this
migration were the missing piece. Because the Pydantic schema also never
declared reference_id until this same patch, the gap was silent rather
than a hard error: FastAPI dropped the field from every request instead
of crashing, so surgical history entries saved fine, they just never
persisted their reference_id link.

Revision ID: pc_0003
Revises: pc_0002
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "pc_0003"
down_revision: str | None = "pc_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "patients_clinical_surgical_history", sa.Column("reference_id", sa.UUID(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("patients_clinical_surgical_history", "reference_id")
