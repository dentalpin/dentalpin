"""gdpr: mark consent entries recorded together with verified evidence.

Adds ``patient_consents.managed`` (default false). A module that records an
entry together with its own evidence sets it, and the staff consent endpoint
then refuses manual entries for that patient and purpose.

Lives on the module's own Alembic branch (``gdpr``), no depends_on.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "gdpr_0005"
down_revision: str | Sequence[str] | None = "gdpr_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "patient_consents",
        sa.Column("managed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("patient_consents", "managed")
