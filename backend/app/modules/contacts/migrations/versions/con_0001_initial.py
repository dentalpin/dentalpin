"""contacts: initial schema.

Tables:
    - ``contacts`` — external labs, suppliers, and other provider contacts.

Lives on its own Alembic branch (``contacts``) per ADR 0002.

Revision ID: con_0001
Revises:
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "con_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("contacts",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("contact_type", sa.String(length=20), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contacts_clinic_id", "contacts", ["clinic_id"])
    op.create_index("ix_contacts_contact_type", "contacts", ["contact_type"])


def downgrade() -> None:
    op.drop_index("ix_contacts_contact_type", table_name="contacts")
    op.drop_index("ix_contacts_clinic_id", table_name="contacts")
    op.drop_table("contacts")
