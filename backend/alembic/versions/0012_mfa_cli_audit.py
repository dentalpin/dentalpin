"""Represent CLI MFA resets without inventing a staff actor.

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("auth_mfa_audit", "actor_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    # The older schema requires a UUID. Preserve audit rows with a reserved
    # actor value for deployment-operator resets.
    op.execute(
        "UPDATE auth_mfa_audit SET actor_id = '00000000-0000-0000-0000-000000000000' "
        "WHERE actor_id IS NULL"
    )
    op.alter_column("auth_mfa_audit", "actor_id", existing_type=sa.Uuid(), nullable=False)
