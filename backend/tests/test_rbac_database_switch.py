"""Runtime switch to DB-backed clinic-aware RBAC (issue #46).

With ``settings.RBAC_FROM_DB`` enabled, the ``require_permission`` gate and
``/me`` permission resolution must route through the DB-backed resolver
(``resolve_granted_permissions`` / ``has_permission_in_clinic``) rather than the
legacy static map. These tests exercise the actual ``permission_checker`` closure
returned by :func:`app.core.auth.dependencies.require_permission` and the resolver
/:func:`expand_permissions` pair ``/me`` uses, proving the DB path decides 200/403
correctly for admin vs a limited role and expands wildcards the way ``/me`` needs.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.core.auth.dependencies import ClinicContext, require_permission
from app.core.auth.models import Clinic, ClinicRoleOverride, Permission, Role
from app.core.auth.permissions import CORE_PERMISSIONS, expand_permissions
from app.core.auth.rbac import (
    has_permission_in_clinic,
    invalidate_rbac_cache,
    resolve_granted_permissions,
)
from app.core.auth.seed_rbac import seed_rbac
from app.core.plugins import module_registry


@pytest.fixture(autouse=True)
def _rbac_flag():
    """Toggle the DB-backed flag for the test and always restore it."""
    original = settings.RBAC_FROM_DB
    settings.RBAC_FROM_DB = True
    yield
    settings.RBAC_FROM_DB = original
    invalidate_rbac_cache()


async def _seeded(db):
    invalidate_rbac_cache()
    await seed_rbac(db)
    return db


async def _new_clinic(db) -> str:
    clinic = Clinic(id=uuid4(), name="switch clinic", tax_id="B00000001")
    db.add(clinic)
    await db.flush()
    return str(clinic.id)


def _ctx(clinic_id: str, role: str) -> ClinicContext:
    user = SimpleNamespace(id=uuid4())
    clinic = SimpleNamespace(id=clinic_id)
    return ClinicContext(user, clinic, role)  # type: ignore[arg-type]


async def test_direct_require_permission_allows_admin_from_db(db_session):
    """Under the flag, admin resolves ``*`` via the DB and is allowed."""
    await _seeded(db_session)
    gate = require_permission("patients.future.read")
    # No exception => the requested permission is granted for admin.
    await gate(_ctx(await _new_clinic(db_session), "admin"), db_session)


async def test_direct_require_permission_blocks_receptionist(db_session):
    """Under the flag, a receptionist is denied an admin-only permission."""
    await _seeded(db_session)
    gate = require_permission("admin.users.write")
    with pytest.raises(HTTPException) as exc_info:
        await gate(_ctx(await _new_clinic(db_session), "receptionist"), db_session)
    assert exc_info.value.status_code == 403


async def test_db_resolution_is_clinic_aware_for_gate(db_session):
    """A per-clinic grant override flips the gate for that clinic only."""
    await _seeded(db_session)
    clinic_id = await _new_clinic(db_session)
    # Receptionist lacks admin.users.write by default.
    assert (
        await has_permission_in_clinic(db_session, clinic_id, "receptionist", "admin.users.write")
        is False
    )
    perm = (
        (await db_session.execute(select(Permission).where(Permission.code == "admin.users.write")))
        .scalars()
        .first()
    )
    role = (
        (await db_session.execute(select(Role).where(Role.name == "receptionist")))
        .scalars()
        .first()
    )
    db_session.add(
        ClinicRoleOverride(
            clinic_id=clinic_id,
            role_id=role.id,
            permission_id=perm.id,
            granted=True,
        )
    )
    await db_session.flush()
    invalidate_rbac_cache()
    assert (
        await has_permission_in_clinic(db_session, clinic_id, "receptionist", "admin.users.write")
        is True
    )
    assert (
        await has_permission_in_clinic(db_session, None, "receptionist", "admin.users.write")
        is False
    )


async def test_me_resolution_expands_admin_wildcard(db_session):
    """``/me``-style resolution yields every known permission for admin."""
    await _seeded(db_session)
    role = (await db_session.execute(select(Role).where(Role.name == "admin"))).scalars().first()
    assert role is not None
    granted = set(await resolve_granted_permissions(db_session, None, "admin"))
    assert "*" in granted
    all_perms = module_registry.get_all_permissions() + CORE_PERMISSIONS
    expanded = expand_permissions(list(granted), all_perms)
    # Admin's single ``*`` grant expands to every registered permission.
    assert set(expanded) >= set(all_perms)
