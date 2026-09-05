"""patients_clinical: soft-delete status on clinical + contact rows.

Deletes used to hard-delete allergy/medication/disease/surgery/contact
rows, contradicting the house rule (never hard-delete patient data) and
leaving no recovery path. This adds ``status`` (``active``/``archived``,
house convention mirroring ``patients.status``) to the six deletable
tables; existing rows backfill to ``active`` via the server default.

Revision ID: pc_0003
Revises: pc_0002
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "pc_0003"
down_revision: str | None = "pc_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "patients_clinical_allergy",
    "patients_clinical_medication",
    "patients_clinical_systemic_disease",
    "patients_clinical_surgical_history",
    "patients_clinical_emergency_contact",
    "patients_clinical_legal_guardian",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, "status")
