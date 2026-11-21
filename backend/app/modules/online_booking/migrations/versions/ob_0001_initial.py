"""Online booking request and per-clinic settings (removable module)."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ob_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("online_booking",)
depends_on: str | Sequence[str] | None = ("ag_0001", "pat_0001")


def upgrade() -> None:
    op.create_table(
        "online_booking_rate_limits",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_table(
        "online_booking_settings",
        sa.Column(
            "clinic_id",
            sa.UUID(),
            sa.ForeignKey("clinics.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("public_url", sa.String(500)),
        sa.Column("professional_id", sa.UUID(), sa.ForeignKey("users.id")),
        sa.Column("slot_minutes", sa.Integer(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("min_notice_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("slot_minutes BETWEEN 5 AND 480", name="ck_ob_slot_minutes"),
        sa.CheckConstraint("window_days BETWEEN 1 AND 365", name="ck_ob_window_days"),
        sa.CheckConstraint("min_notice_minutes BETWEEN 0 AND 525600", name="ck_ob_notice"),
    )
    op.create_table(
        "online_booking_requests",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "clinic_id", sa.UUID(), sa.ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("contact_name", sa.String(120)),
        sa.Column("contact_email", sa.String(254)),
        sa.Column("contact_phone", sa.String(40)),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True),
        sa.Column("confirmation_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column(
            "appointment_id", sa.UUID(), sa.ForeignKey("appointments.id", ondelete="SET NULL")
        ),
        sa.Column("patient_id", sa.UUID(), sa.ForeignKey("patients.id", ondelete="SET NULL")),
        sa.Column("rejection_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_time > start_time", name="ck_ob_request_interval"),
        sa.CheckConstraint(
            "status IN ('pending_confirmation','confirmed','accepted','rejected','expired')",
            name="ck_ob_request_status",
        ),
        sa.CheckConstraint("reason IN ('first_visit','checkup')", name="ck_ob_request_reason"),
    )
    op.create_index(
        "ix_online_booking_requests_clinic_id", "online_booking_requests", ["clinic_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_online_booking_requests_clinic_id", table_name="online_booking_requests")
    op.drop_table("online_booking_requests")
    op.drop_table("online_booking_settings")
    op.drop_table("online_booking_rate_limits")
