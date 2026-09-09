"""gdpr: initial schema.

Tables:
    - ``gdpr_requests`` — data-subject requests (Art. 15-21) with a 30-day SLA.
    - ``patient_consents`` — per-patient consent / withdrawal records (Art. 7-8).
    - ``retention_policies`` — per-clinic retention rules gating erasure (Art. 5).
    - ``gdpr_erasure_audit_logs`` — immutable partial-erasure accountability (Art. 17).
    - ``data_breaches`` — reportable breach register (Art. 33-34).

Lives on the module's own Alembic branch (``gdpr``) per ADR 0002 and waits
for the patients migration tip before creating the cross-branch FK.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "gdpr_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("gdpr",)
depends_on: str | Sequence[str] | None = ("pat_0003",)


def upgrade() -> None:
    op.create_table(
        "gdpr_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("requester_name", sa.String(length=200), nullable=False),
        sa.Column("requester_email", sa.String(length=255), nullable=False),
        sa.Column("request_type", sa.String(length=20), nullable=False),
        # received | in_progress | completed | rejected
        sa.Column("status", sa.String(length=20), nullable=False, server_default="received"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gdpr_requests_clinic_id", "gdpr_requests", ["clinic_id"])
    op.create_index("ix_gdpr_requests_patient_id", "gdpr_requests", ["patient_id"])

    op.create_table(
        "patient_consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=100), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provided_text", sa.Text(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_consents_clinic_id", "patient_consents", ["clinic_id"])
    op.create_index("ix_patient_consents_patient_id", "patient_consents", ["patient_id"])

    op.create_table(
        "retention_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("data_category", sa.String(length=100), nullable=False),
        sa.Column("retention_years", sa.Integer(), nullable=False),
        sa.Column("legal_hold_until", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retention_policies_clinic_id", "retention_policies", ["clinic_id"])

    op.create_table(
        "gdpr_erasure_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=True),
        sa.Column("erased_categories", sa.JSON(), nullable=False),
        sa.Column("fields_blanked", sa.JSON(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_gdpr_erasure_audit_logs_clinic_id", "gdpr_erasure_audit_logs", ["clinic_id"]
    )
    op.create_index(
        "ix_gdpr_erasure_audit_logs_patient_id", "gdpr_erasure_audit_logs", ["patient_id"]
    )

    op.create_table(
        "data_breaches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("data_involved", sa.JSON(), nullable=False),
        sa.Column("affected_people", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="under_review"),
        sa.Column("notified_authority_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reported", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_breaches_clinic_id", "data_breaches", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("ix_data_breaches_clinic_id", table_name="data_breaches")
    op.drop_table("data_breaches")
    op.drop_index("ix_gdpr_erasure_audit_logs_patient_id", table_name="gdpr_erasure_audit_logs")
    op.drop_index("ix_gdpr_erasure_audit_logs_clinic_id", table_name="gdpr_erasure_audit_logs")
    op.drop_table("gdpr_erasure_audit_logs")
    op.drop_index("ix_retention_policies_clinic_id", table_name="retention_policies")
    op.drop_table("retention_policies")
    op.drop_index("ix_patient_consents_patient_id", table_name="patient_consents")
    op.drop_index("ix_patient_consents_clinic_id", table_name="patient_consents")
    op.drop_table("patient_consents")
    op.drop_index("ix_gdpr_requests_patient_id", table_name="gdpr_requests")
    op.drop_index("ix_gdpr_requests_clinic_id", table_name="gdpr_requests")
    op.drop_table("gdpr_requests")
