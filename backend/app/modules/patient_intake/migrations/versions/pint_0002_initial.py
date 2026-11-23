"""Create versioned intake definitions, submissions and consent provenance."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "pint_0002"
down_revision = "pint_0001"
branch_labels = None
# Intake links to the GDPR ledger by UUID. Runtime module dependencies live in the manifest.
depends_on = "pat_0003"


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "patient_intake_form_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("clinic_id", sa.Uuid(), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("published_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("definition", JSONB(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("clinic_id", "locale", "version"),
    )
    op.create_index(
        "ix_patient_intake_form_versions_clinic_id", "patient_intake_form_versions", ["clinic_id"]
    )
    op.create_table(
        "patient_intake_submissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("clinic_id", sa.Uuid(), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column(
            "form_id", sa.Uuid(), sa.ForeignKey("patient_intake_form_versions.id"), nullable=False
        ),
        sa.Column("issued_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("representative", JSONB()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True)),
        sa.Column("answers", JSONB()),
        sa.Column("administrative_review", JSONB()),
        sa.Column("clinical_review", JSONB()),
        sa.Column("discarded_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index(
        "ix_patient_intake_submissions_clinic_id", "patient_intake_submissions", ["clinic_id"]
    )
    op.create_index(
        "ix_patient_intake_submissions_patient_id", "patient_intake_submissions", ["patient_id"]
    )
    op.create_table(
        "patient_intake_consent_provenance",
        sa.Column("consent_id", sa.Uuid(), primary_key=True),
        sa.Column("clinic_id", sa.Uuid(), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("intake_id", sa.Uuid(), sa.ForeignKey("patient_intake_submissions.id")),
        sa.Column("recorded_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index(
        "ix_patient_intake_consent_provenance_clinic_id",
        "patient_intake_consent_provenance",
        ["clinic_id"],
    )


def downgrade() -> None:
    op.drop_table("patient_intake_consent_provenance")
    op.drop_table("patient_intake_submissions")
    op.drop_table("patient_intake_form_versions")
