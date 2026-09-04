"""payments: idempotency key + partial unique index (#365).

``upi`` / ``netbanking`` are string values in ``payments.method`` (no DB
enum), so the method additions need no schema change; this revision
adds the caller-supplied ``idempotency_key`` and the per-clinic partial
unique index that makes ``record_payment`` retry-safe.

Revision ID: pay_0005
Revises: pay_0004
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "pay_0005"
down_revision: str | None = "pay_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("idempotency_key", sa.String(length=100), nullable=True))
    op.create_index(
        "uq_payments_clinic_idempotency",
        "payments",
        ["clinic_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_payments_clinic_idempotency", table_name="payments")
    op.drop_column("payments", "idempotency_key")
