"""Public booking page: branding, visit reasons, logo, quotas and form questions."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "ob_0004"
down_revision = "ob_0003"
branch_labels = None
depends_on = None

BRAND_COLUMNS = (
    ("accent_color", 7),
    ("title_es", 120),
    ("intro_es", 300),
    ("title_en", 120),
    ("intro_en", 300),
)
LIMIT_COLUMNS = ("daily_limit", "weekly_limit", "active_patient_limit")
FLAG_COLUMNS = ("ask_existing_patient", "allow_comment")
REQUEST_BUFFERS = ("buffer_before", "buffer_after")
REQUEST_NAMES = (
    ("contact_first_name", 60),
    ("contact_last_name", 59),
)


def upgrade():
    for name, length in BRAND_COLUMNS:
        op.add_column("online_booking_settings", sa.Column(name, sa.String(length), nullable=True))
    op.add_column("online_booking_settings", sa.Column("reasons", postgresql.JSONB, nullable=True))
    op.add_column(
        "online_booking_settings", sa.Column("logo_data", sa.LargeBinary(), nullable=True)
    )
    op.execute("""UPDATE online_booking_settings SET reasons = jsonb_build_array(
        jsonb_build_object('id','first_visit','name_es','Primera visita','name_en','First visit',
          'duration_minutes',COALESCE(first_visit_minutes,slot_minutes),'active',true),
        jsonb_build_object('id','checkup','name_es','Revisión','name_en','Check-up',
          'duration_minutes',COALESCE(checkup_minutes,slot_minutes),'active',true))""")
    op.alter_column("online_booking_settings", "reasons", nullable=False)
    for name in LIMIT_COLUMNS:
        op.add_column("online_booking_settings", sa.Column(name, sa.Integer(), nullable=True))
    op.add_column("online_booking_settings", sa.Column("redirect_url", sa.String(500)))
    op.add_column("online_booking_settings", sa.Column("privacy_url", sa.String(500)))
    op.add_column(
        "online_booking_settings",
        sa.Column(
            "embed_origins", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
    )
    for name in FLAG_COLUMNS:
        op.add_column(
            "online_booking_settings",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    op.drop_constraint("ck_ob_request_reason", "online_booking_requests", type_="check")
    for name in REQUEST_BUFFERS:
        op.add_column(
            "online_booking_requests",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
        )
    for name, length in REQUEST_NAMES:
        op.add_column("online_booking_requests", sa.Column(name, sa.String(length)))
    op.add_column("online_booking_requests", sa.Column("existing_patient", sa.Boolean()))
    op.add_column("online_booking_requests", sa.Column("comment", sa.String(500)))


def downgrade():
    # Unknown reasons cannot be represented by the previous schema without data loss.
    bind = op.get_bind()
    if bind.execute(
        sa.text(
            "SELECT 1 FROM online_booking_requests "
            "WHERE reason NOT IN ('first_visit','checkup') LIMIT 1"
        )
    ).first():
        raise RuntimeError("Cannot downgrade while requests use custom booking reasons")
    for name in ("comment", "existing_patient"):
        op.drop_column("online_booking_requests", name)
    for name, _ in reversed(REQUEST_NAMES):
        op.drop_column("online_booking_requests", name)
    for name in reversed(REQUEST_BUFFERS):
        op.drop_column("online_booking_requests", name)
    op.create_check_constraint(
        "ck_ob_request_reason", "online_booking_requests", "reason IN ('first_visit','checkup')"
    )
    for name in reversed(FLAG_COLUMNS):
        op.drop_column("online_booking_settings", name)
    op.drop_column("online_booking_settings", "embed_origins")
    op.drop_column("online_booking_settings", "privacy_url")
    op.drop_column("online_booking_settings", "redirect_url")
    for name in reversed(LIMIT_COLUMNS):
        op.drop_column("online_booking_settings", name)
    op.drop_column("online_booking_settings", "reasons")
    op.drop_column("online_booking_settings", "logo_data")
    for name, _ in reversed(BRAND_COLUMNS):
        op.drop_column("online_booking_settings", name)
