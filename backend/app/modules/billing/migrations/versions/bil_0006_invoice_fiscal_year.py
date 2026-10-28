"""billing — key the per-series sequential by its fiscal year (#689).

``bil_0005`` made ``(series_id, sequential_number)`` unique over a
series' whole lifetime, while ``generate_number`` restarts the counter at
1 every calendar year when ``reset_yearly`` (the default) is set. The
first invoice of a new year therefore collided with last year's first
invoice and answered 500.

The year the number was drawn in now lives on the invoice
(``fiscal_year``, the same year the rendered number carries), and the
backstop becomes ``(series_id, fiscal_year, sequential_number)``.
``NULLS NOT DISTINCT`` keeps a numbered row without a year under the old
lifetime rule instead of letting it escape the index.

Backfill: the year in the rendered number (``PREFIX-YYYY-NNNN``), else
the issue date's year, else the creation year.

Downgrade restores the lifetime index. Once a year has been reset it
fails loudly on ``CREATE UNIQUE INDEX`` — that is intended, the old
index cannot represent that data.

Revision ID: bil_0006
Revises: bil_0005
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "bil_0006"
down_revision: str | None = "bil_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("fiscal_year", sa.Integer(), nullable=True))
    op.execute(
        r"""
        UPDATE invoices
        SET fiscal_year = COALESCE(
            substring(invoice_number from '-(\d{4})-\d+$')::int,
            EXTRACT(YEAR FROM issue_date)::int,
            EXTRACT(YEAR FROM created_at)::int
        )
        WHERE sequential_number IS NOT NULL
        """
    )
    op.drop_index("ix_invoices_series_sequential_unique", table_name="invoices")
    op.create_index(
        "ix_invoices_series_year_sequential_unique",
        "invoices",
        ["series_id", "fiscal_year", "sequential_number"],
        unique=True,
        postgresql_where="series_id IS NOT NULL AND sequential_number IS NOT NULL",
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_series_year_sequential_unique", table_name="invoices")
    op.create_index(
        "ix_invoices_series_sequential_unique",
        "invoices",
        ["series_id", "sequential_number"],
        unique=True,
        postgresql_where="series_id IS NOT NULL AND sequential_number IS NOT NULL",
    )
    op.drop_column("invoices", "fiscal_year")
