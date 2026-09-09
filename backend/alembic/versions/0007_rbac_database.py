"""core — RBAC to database (issue #46).

Permissions and role grants move from the static ``ROLE_PERMISSIONS`` dict
in ``app/core/auth/permissions.py`` into persisted tables so a clinic can
define custom roles and override a system role's permissions without a
deploy.

Tables added:
    - ``roles`` — system roles (``clinic_id IS NULL``) + per-clinic custom
      roles.
    - ``permissions`` — catalog of every permission declared by core or a
      module.
    - ``role_permissions`` — which permissions a role has.
    - ``module_default_role_permissions`` — persisted snapshot of a module's
      ``manifest.role_permissions`` (used to reconcile module defaults).
    - ``clinic_role_overrides`` — per-clinic grant/revoke overrides for the
      shared system roles.

``clinic_memberships`` gains a nullable ``role_id`` FK to ``roles`` (the
string ``role`` column is retained this release and backfilled from it).

This revision only creates the schema and backfills the member FK; the
runtime switch to DB-backed lookups happens in the code layers that consume
the tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SYSTEM_ROLES = (
    ("admin", "Full access to the clinic"),
    ("dentist", "Clinical care and patient records"),
    ("hygienist", "Hygiene and preventive care"),
    ("assistant", "Chairside assistance"),
    ("receptionist", "Front-desk and appointments"),
)


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "name", name="uq_roles_clinic_name"),
    )
    op.create_index("ix_roles_clinic_id", "roles", ["clinic_id"])

    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=True)

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])

    op.create_table(
        "module_default_role_permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module", "role", "permission_id", name="uq_module_role_permission"),
    )
    op.create_index(
        "ix_module_default_role_permissions_permission_id",
        "module_default_role_permissions",
        ["permission_id"],
    )

    op.create_table(
        "clinic_role_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "clinic_id", "role_id", "permission_id", name="uq_clinic_role_override"
        ),
    )
    op.create_index("ix_clinic_role_overrides_clinic_id", "clinic_role_overrides", ["clinic_id"])
    op.create_index(
        "ix_clinic_role_overrides_permission_id", "clinic_role_overrides", ["permission_id"]
    )
    op.create_index("ix_clinic_role_overrides_role_id", "clinic_role_overrides", ["role_id"])

    # Seed the system roles so existing memberships can point at them.
    op.execute(
        """
        INSERT INTO roles (id, clinic_id, name, is_system, description, created_at, updated_at)
        VALUES
          (gen_random_uuid(), NULL, 'admin',       true, 'Full access to the clinic', now(), now()),
          (gen_random_uuid(), NULL, 'dentist',     true, 'Clinical care and patient records', now(), now()),
          (gen_random_uuid(), NULL, 'hygienist',   true, 'Hygiene and preventive care', now(), now()),
          (gen_random_uuid(), NULL, 'assistant',   true, 'Chairside assistance', now(), now()),
          (gen_random_uuid(), NULL, 'receptionist', true, 'Front-desk and appointments', now(), now());
        """
    )

    # Backfill clinic_memberships.role_id from the seeded system roles.
    op.add_column(
        "clinic_memberships",
        sa.Column("role_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        """
        UPDATE clinic_memberships cm
        SET role_id = r.id
        FROM roles r
        WHERE r.clinic_id IS NULL AND r.name = cm.role;
        """
    )
    op.create_index("ix_clinic_memberships_role_id", "clinic_memberships", ["role_id"])
    op.create_foreign_key(
        "fk_clinic_memberships_role_id", "clinic_memberships", "roles", ["role_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_clinic_memberships_role_id", "clinic_memberships", type_="foreignkey")
    op.drop_index("ix_clinic_memberships_role_id", table_name="clinic_memberships")
    op.drop_column("clinic_memberships", "role_id")

    op.drop_table("clinic_role_overrides")
    op.drop_table("module_default_role_permissions")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
