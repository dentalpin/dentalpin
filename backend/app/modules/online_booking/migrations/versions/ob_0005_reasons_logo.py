"""Configurable visit reasons and clinic-owned logo."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "ob_0005"
down_revision = "ob_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("online_booking_settings", sa.Column("reasons", postgresql.JSONB, nullable=True))
    op.add_column(
        "online_booking_settings", sa.Column("logo_data", sa.LargeBinary(), nullable=True)
    )
    op.add_column(
        "online_booking_settings", sa.Column("logo_content_type", sa.String(50), nullable=True)
    )
    op.execute("""UPDATE online_booking_settings SET reasons = jsonb_build_array(
        jsonb_build_object('id','first_visit','name_es','Primera visita','name_en','First visit',
          'duration_minutes',COALESCE(first_visit_minutes,slot_minutes),'active',true),
        jsonb_build_object('id','checkup','name_es','Revisión','name_en','Check-up',
          'duration_minutes',COALESCE(checkup_minutes,slot_minutes),'active',true))""")
    op.alter_column("online_booking_settings", "reasons", nullable=False)
    op.drop_constraint("ck_ob_request_reason", "online_booking_requests", type_="check")


def downgrade():
    # Unknown reasons cannot be represented by the previous schema without data loss.
    bind = op.get_bind()
    if bind.execute(
        sa.text(
            "SELECT 1 FROM online_booking_requests WHERE reason NOT IN ('first_visit','checkup') LIMIT 1"
        )
    ).first():
        raise RuntimeError("Cannot downgrade while requests use custom booking reasons")
    op.create_check_constraint(
        "ck_ob_request_reason", "online_booking_requests", "reason IN ('first_visit','checkup')"
    )
    op.drop_column("online_booking_settings", "logo_content_type")
    op.drop_column("online_booking_settings", "logo_data")
    op.drop_column("online_booking_settings", "reasons")
