"""patients_clinical: add reference_id to allergy/medication/systemic_disease.

Loose link to medical_reference's lookup tables — plain nullable UUID,
deliberately no FK constraint, so this (core) module keeps working
standalone if medical_reference (community) is ever removed. All existing
rows get NULL, which is exactly correct: they were entered as free text
before this column existed.

Revision ID: pc_0002
Revises: pc_0001
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "pc_0002"
down_revision: str | None = "pc_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = [
    "patients_clinical_allergy",
    "patients_clinical_medication",
    "patients_clinical_systemic_disease",
]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("reference_id", sa.UUID(), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "reference_id")
