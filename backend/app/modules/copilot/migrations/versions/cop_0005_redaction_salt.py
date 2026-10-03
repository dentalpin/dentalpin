"""copilot module — per-conversation redaction salt (#586).

Unsalted token hashes are reversible by dictionary attack for
low-cardinality fields (a birth date falls in ~40ms), and the party
holding the token is the LLM provider redaction exists to protect
against. Each conversation now carries its own random salt beside the
context blob (never inside it, never logged); tokens are
``sha256(salt:real)[:12]``, stable inside the conversation and
unrelated across conversations.

Revision ID: cop_0005
Revises: cop_0004
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cop_0005"
down_revision: str | None = "cop_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "copilot_conversations",
        sa.Column("redaction_salt", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("copilot_conversations", "redaction_salt")
