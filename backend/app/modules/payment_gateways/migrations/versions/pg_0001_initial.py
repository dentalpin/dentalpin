"""payment_gateways module — initial schema.

Creates ``payment_requests`` (the pre-payment async lifecycle of a
gateway collection attempt) and ``gateway_refund_requests`` (the async
lifecycle of a gateway refund attempt). Both FK into ``payments``
(``payment_id`` / ``refund_id``), so this branch anchors on the core ``0001``
like every other removable module and declares ``depends_on`` on the
``payments`` head — never ``down_revision`` onto another module's chain,
which would fork that branch (issue #56).

Revision ID: pg_0001
Revises: 0001 (depends_on pay_0005)
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "pg_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("payment_gateways",)
depends_on: str | Sequence[str] | None = ("pay_0005",)


def upgrade() -> None:
    op.create_table(
        "payment_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("provider_key", sa.String(length=50), nullable=False),
        sa.Column("requested_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("requested_method", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("allocation_input", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("context", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("provider_reference", sa.String(length=100), nullable=True),
        sa.Column("provider_payment_reference", sa.String(length=100), nullable=True),
        sa.Column("checkout_payload_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("raw_status_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("payment_id", sa.UUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("requested_amount > 0", name="ck_payment_requests_amount_positive"),
        sa.UniqueConstraint(
            "clinic_id", "idempotency_key", name="uq_payment_requests_clinic_idempotency"
        ),
    )
    op.create_index(
        "idx_payment_requests_clinic_patient", "payment_requests", ["clinic_id", "patient_id"]
    )
    op.create_index("idx_payment_requests_clinic_state", "payment_requests", ["clinic_id", "state"])
    op.create_index("ix_payment_requests_clinic_id", "payment_requests", ["clinic_id"])
    op.create_index("ix_payment_requests_patient_id", "payment_requests", ["patient_id"])
    op.create_index("ix_payment_requests_state", "payment_requests", ["state"])
    op.create_index("ix_payment_requests_payment_id", "payment_requests", ["payment_id"])
    op.create_index(
        "uq_payment_requests_provider_reference",
        "payment_requests",
        ["provider_key", "provider_reference"],
        unique=True,
        postgresql_where=sa.text("provider_reference IS NOT NULL"),
    )
    op.create_index(
        "uq_payment_requests_provider_payment_reference",
        "payment_requests",
        ["provider_key", "provider_payment_reference"],
        unique=True,
        postgresql_where=sa.text("provider_payment_reference IS NOT NULL"),
    )

    op.create_table(
        "gateway_refund_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("payment_request_id", sa.UUID(), nullable=False),
        sa.Column("provider_key", sa.String(length=50), nullable=False),
        sa.Column("provider_payment_reference", sa.String(length=100), nullable=False),
        sa.Column("requested_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason_code", sa.String(length=30), nullable=False),
        sa.Column("reason_note", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="requested"),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("provider_refund_reference", sa.String(length=100), nullable=True),
        sa.Column("raw_status_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("refund_id", sa.UUID(), nullable=True),
        sa.Column("requested_by", sa.UUID(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["payment_request_id"], ["payment_requests.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["refund_id"], ["refunds.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("requested_amount > 0", name="ck_gateway_refunds_amount_positive"),
        sa.UniqueConstraint(
            "clinic_id", "idempotency_key", name="uq_gateway_refunds_clinic_idempotency"
        ),
    )
    op.create_index(
        "idx_gateway_refunds_clinic_payment", "gateway_refund_requests", ["clinic_id", "payment_id"]
    )
    op.create_index(
        "ix_gateway_refund_requests_clinic_id", "gateway_refund_requests", ["clinic_id"]
    )
    op.create_index(
        "ix_gateway_refund_requests_payment_id", "gateway_refund_requests", ["payment_id"]
    )
    op.create_index(
        "ix_gateway_refund_requests_payment_request_id",
        "gateway_refund_requests",
        ["payment_request_id"],
    )
    op.create_index("ix_gateway_refund_requests_state", "gateway_refund_requests", ["state"])
    op.create_index(
        "ix_gateway_refund_requests_refund_id", "gateway_refund_requests", ["refund_id"]
    )
    op.create_index(
        "uq_gateway_refunds_provider_reference",
        "gateway_refund_requests",
        ["provider_key", "provider_refund_reference"],
        unique=True,
        postgresql_where=sa.text("provider_refund_reference IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("gateway_refund_requests")
    op.drop_table("payment_requests")
