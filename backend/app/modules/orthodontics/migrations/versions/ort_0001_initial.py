"""Orthodontics initial schema (issue #270, slice-a: cases + controls + settings).

Single revision on purpose: the module is unshipped, so the reopen audit
column (``reopened_at``) is created inline rather than in a follow-up
migration, matching what the team did for staff_attendance and treasury
before their releases. Squashing is free before release and impossible
after it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ort_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("orthodontics",)
# Cross-module FK to patients.id: order after the patients head (newest
# precedent: prescriptions, patient_relationships). See issue #507 for the
# convention discussion; this follows the current practice.
depends_on: str | Sequence[str] | None = ("pat_0003",)


def upgrade() -> None:
    op.create_table(
        "ortho_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("appliance_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("estimated_months", sa.Integer(), nullable=True),
        sa.Column("diagnosis_notes", sa.Text(), nullable=True),
        sa.Column("current_upper_wire", sa.String(length=40), nullable=True),
        sa.Column("current_lower_wire", sa.String(length=40), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        # Reopen audit: a finished case may only be reopened to `active`,
        # and that stamps `reopened_at` instead of clearing the finish date
        # (the end-of-treatment record is never destroyed).
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ortho_cases_clinic_id", "ortho_cases", ["clinic_id"])
    op.create_index("ix_ortho_cases_patient_id", "ortho_cases", ["patient_id"])
    op.create_index("ix_ortho_cases_clinic_patient", "ortho_cases", ["clinic_id", "patient_id"])

    op.create_table(
        "ortho_controls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("performed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("upper_wire", sa.String(length=40), nullable=True),
        sa.Column("lower_wire", sa.String(length=40), nullable=True),
        sa.Column("procedures", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("procedures_other", sa.Text(), nullable=True),
        sa.Column("aligner_number", sa.Integer(), nullable=True),
        sa.Column("hygiene", sa.String(length=10), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("next_control_weeks", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["ortho_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ortho_controls_clinic_id", "ortho_controls", ["clinic_id"])
    op.create_index("ix_ortho_controls_case_id", "ortho_controls", ["case_id"])
    op.create_index(
        "ix_ortho_controls_case_performed", "ortho_controls", ["case_id", "performed_at"]
    )

    op.create_table(
        "ortho_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wires", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("procedures", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id"),
    )
    op.create_index("ix_ortho_settings_clinic_id", "ortho_settings", ["clinic_id"])


def downgrade() -> None:
    op.drop_table("ortho_settings")
    op.drop_table("ortho_controls")
    op.drop_table("ortho_cases")
