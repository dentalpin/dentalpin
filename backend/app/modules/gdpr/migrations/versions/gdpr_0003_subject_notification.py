"""gdpr: Art. 34 data-subject notification record on breaches.

Adds ``notified_subjects_at`` + ``notified_subjects_count`` to
``data_breaches`` (#562 SEC-02): the register tracked authority
notification only, with no column for whether/when affected people
were told. Both nullable (existing rows predate the record), set
explicitly via PATCH — no auto-stamp rule, that scope decision is
parked with the maintainer.

Lives on the module's own Alembic branch (``gdpr``), no depends_on
(cross-branch threading breaks uninstall roundtrips, M6).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "gdpr_0003"
down_revision: str | Sequence[str] | None = "gdpr_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "data_breaches",
        sa.Column("notified_subjects_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "data_breaches",
        sa.Column("notified_subjects_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("data_breaches", "notified_subjects_count")
    op.drop_column("data_breaches", "notified_subjects_at")
