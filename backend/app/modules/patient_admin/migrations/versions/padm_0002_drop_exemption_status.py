"""patient_admin: drop exemption status table.

APCI turned out to mean "on the reference list of fully-covered
conditions" — a computed flag off systemic disease data, not a
manually-entered exemption record. See models.py docstring.

Revision ID: padm_0002
Revises: padm_0001
Create Date: 2026-07-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "padm_0002"
down_revision: str | None = "padm_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("patient_admin_exemption_status")


def downgrade() -> None:
    # Recreate matching padm_0001's original shape, in case of rollback.
    import sqlalchemy as sa

    op.create_table(
        "patient_admin_exemption_status",
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("exemption_type", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("reference_number", sa.String(length=100), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("patient_id"),
    )
