"""gdpr: canonicalize stored consent purposes.

``ConsentService`` compares purposes through ``normalize_purpose``
(``strip().lower()``), so a withdrawal stored as ``"Marketing"`` is
invisible to a later grant for ``"marketing"`` and the ledger treats them
as two purposes (#562 CONS-05). New rows are normalized on write; this
backfills the rows written before that rule, so the single key the service
looks up finds every row for the purpose.

Lives on the module's own Alembic branch (``gdpr``).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "gdpr_0004"
down_revision: str | Sequence[str] | None = "gdpr_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Canonicalize in place: the service's lookup key is
    # ``lower(btrim(purpose))``, so any row still holding the original
    # casing or padding is unreachable under the key a later write uses
    # (#562 CONS-05). The WHERE keeps the statement off already-canonical
    # rows.
    op.execute(
        sa.text(
            "UPDATE patient_consents SET purpose = lower(btrim(purpose)) "
            "WHERE purpose <> lower(btrim(purpose))"
        )
    )


def downgrade() -> None:
    # Canonicalization is lossy - the original casing is not retained - so
    # there is nothing to restore; the data stays canonical on downgrade.
    pass
