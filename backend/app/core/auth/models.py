"""Core authentication and authorization models."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

from .permissions import PROFESSIONAL_ROLES

if TYPE_CHECKING:
    from app.modules.agenda.models import Appointment, Cabinet
    from app.modules.patients.models import Patient


class Clinic(Base, TimestampMixin):
    """Clinic entity - the main organizational unit."""

    __tablename__ = "clinics"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    tax_id: Mapped[str] = mapped_column(String(20))  # CIF/NIF
    legal_name: Mapped[str | None] = mapped_column(String(200), default=None)
    address: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    # IANA timezone id (e.g. "Europe/Madrid"). Single source of truth
    # for any module that needs local-time semantics — schedules,
    # reports, future billing date-windows, etc.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Europe/Madrid"
    )
    # ISO 4217 currency code. Single source of truth for any module
    # that renders money — budgets, invoices, catalog, reports.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="EUR")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    memberships: Mapped[list["ClinicMembership"]] = relationship(
        back_populates="clinic", cascade="all, delete-orphan"
    )
    patients: Mapped[list["Patient"]] = relationship(back_populates="clinic")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="clinic")
    cabinets: Mapped[list["Cabinet"]] = relationship(
        back_populates="clinic",
        cascade="all, delete-orphan",
        order_by="Cabinet.display_order",
    )


class User(Base, TimestampMixin):
    """User account for authentication."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    professional_id: Mapped[str | None] = mapped_column(String(50))  # Colegiado number
    is_active: Mapped[bool] = mapped_column(default=True)
    token_version: Mapped[int] = mapped_column(default=0)  # For token revocation

    # Relationships
    memberships: Mapped[list["ClinicMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Role(Base, TimestampMixin):
    """A role a clinic member can hold.

    ``clinic_id IS NULL`` marks a **system** role (the standard five:
    admin / dentist / hygienist / assistant / receptionist), shared by all
    clinics. A non-null ``clinic_id`` is a clinic-created custom role, which
    can be granted permissions directly (issue #46).
    """

    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinics.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(50))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # System roles are unique by name (clinic_id NULL); custom roles are
        # unique per clinic.
        UniqueConstraint("clinic_id", "name", name="uq_roles_clinic_name"),
    )


class Permission(Base, TimestampMixin):
    """Catalog of every permission a module (or core) declares."""

    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    module: Mapped[str] = mapped_column(String(100))  # core OR the module name
    code: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)


class RolePermission(Base, TimestampMixin):
    """Which permissions a role has."""

    __tablename__ = "role_permissions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), index=True)
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), index=True
    )

    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)


class ModuleDefaultRolePermission(Base, TimestampMixin):
    """Idempotent record of a module's ``manifest.role_permissions``.

    Lets the seeder reconcile a module's declared defaults against the DB
    without storing the mapping back in code (the module still declares it in
    its manifest; this table is the persisted snapshot used at runtime).
    """

    __tablename__ = "module_default_role_permissions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    module: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50))  # standard role name
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), index=True
    )

    __table_args__ = (
        UniqueConstraint("module", "role", "permission_id", name="uq_module_role_permission"),
    )


class ClinicRoleOverride(Base, TimestampMixin):
    """Per-clinic deviation from a system role's default grant set.

    ``granted`` toggles whether the permission is present in that clinic (a
    clinic can add or revoke a specific permission for a standard role without
    affecting other clinics). Custom (per-clinic) roles express their grants
    directly via ``role_permissions``; overrides exist for the shared system
    roles.
    """

    __tablename__ = "clinic_role_overrides"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), index=True
    )
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), index=True)
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), index=True
    )
    granted: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("clinic_id", "role_id", "permission_id", name="uq_clinic_role_override"),
    )


def _derive_is_professional(context) -> bool:  # noqa: ANN001 — SQLAlchemy ExecutionContext
    """Insert-time default: dentists/hygienists are professionals."""
    params = context.get_current_parameters()
    return params.get("role") in PROFESSIONAL_ROLES


class ClinicMembership(Base, TimestampMixin):
    """Association between users and clinics with role."""

    __tablename__ = "clinic_memberships"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    # DB-backed role (issue #46). The string ``role`` column is retained this
    # release as the read path and insert default; ``role_id`` is the FK to
    # ``roles`` and is the future authority. A follow-up drops ``role``.
    role_id: Mapped[UUID | None] = mapped_column(ForeignKey("roles.id"), nullable=True, index=True)
    role: Mapped[str] = mapped_column(
        String(20)
    )  # admin, dentist, hygienist, assistant, receptionist
    # Whether this member appears in the agenda, holds working hours and
    # can be assigned treatments. Decoupled from ``role`` so an admin can
    # also practise (solo clinics) — professional-ness is a fact about
    # the person, the role is about permissions. When not set explicitly,
    # it derives from the role at insert time, so plain
    # ``ClinicMembership(role="dentist")`` keeps behaving as before.
    is_professional: Mapped[bool] = mapped_column(
        default=_derive_is_professional, server_default=text("false"), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="memberships")
    clinic: Mapped["Clinic"] = relationship(back_populates="memberships")
    role_ref: Mapped["Role | None"] = relationship(foreign_keys=[role_id])


class RefreshToken(Base):
    """One row per issued refresh token (ADR 0023): the server-side state
    that makes rotation and per-token revocation possible.

    ``id`` is the JWT's ``jti``; ``family_id`` groups the chain a login
    started (rotation keeps the family, reuse of a revoked token burns
    the whole family). ``token_version`` on the user stays the
    log-out-everywhere hammer; this table is the scalpel.
    """

    __tablename__ = "auth_refresh_tokens"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    family_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    replaced_by: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), default=None)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    last_ip: Mapped[str | None] = mapped_column(String(64), default=None)
