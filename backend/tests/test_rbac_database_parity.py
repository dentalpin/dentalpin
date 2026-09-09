"""Parity between DB-backed RBAC (issue #46) and the legacy static grants.

Acceptance for the refactor: once ``seed_rbac`` has populated the ``roles`` /
``permissions`` / ``role_permissions`` tables from the same inputs the legacy
:func:`app.core.auth.permissions.get_role_permissions` merged, the DB-backed
lookup must return the *identical* grant set for every system role — so there
is no parallel source of truth. A future commit can then switch
``require_permission`` and ``/me`` to DB-backed resolution with this test as
the gate.
"""

from uuid import uuid4

from sqlalchemy import select

from app.core.auth.models import (
    Clinic,
    ClinicRoleOverride,
    Permission,
    Role,
    RolePermission,
)
from app.core.auth.permissions import get_role_permissions, has_permission, permission_matches
from app.core.auth.rbac import (
    has_permission_in_clinic,
    invalidate_rbac_cache,
    resolve_granted_permissions,
)
from app.core.auth.seed_rbac import seed_rbac

ROLES = ("admin", "dentist", "hygienist", "assistant", "receptionist")


async def _seeded(db):
    invalidate_rbac_cache()
    await seed_rbac(db)
    return db


async def _make_clinic(db, name: str = "resolving clinic") -> str:
    clinic = Clinic(id=uuid4(), name=name, tax_id="B00000000")
    db.add(clinic)
    await db.flush()
    return str(clinic.id)


async def test_db_grants_parity_with_static_for_every_role(db_session):
    """DB-backed resolution == legacy static grant set for all system roles."""
    await _seeded(db_session)
    for role in ROLES:
        static = set(get_role_permissions(role))
        db_granted = await resolve_granted_permissions(db_session, None, role)
        assert db_granted == static, f"{role} parity: DB={db_granted} static={static}"


async def test_permission_resolution_parity(db_session):
    """Representative permission checks resolve identically via both paths."""
    await _seeded(db_session)
    probe = [
        ("admin", "future.module.action"),
        ("dentist", "patients.read"),
        ("dentist", "admin.users.write"),
        ("hygienist", "patients_clinical.emergency.read"),
        ("receptionist", "patients_clinical.emergency.read"),
        ("receptionist", "admin.users.write"),
        ("assistant", "patients.read"),
    ]
    for role, perm in probe:
        static = has_permission(role, perm)
        db_based = await has_permission_in_clinic(db_session, None, role, perm)
        assert db_based is static, f"{role}/{perm}: DB={db_based} static={static}"


async def test_admin_wildcard_through_db(db_session):
    """Admin's literal ``*`` wildcard resolves to any permission via the DB."""
    await _seeded(db_session)
    granted = await resolve_granted_permissions(db_session, None, "admin")
    assert "*" in granted
    assert await has_permission_in_clinic(db_session, None, "admin", "anything.at.all") is True


async def test_unknown_role_resolves_empty(db_session):
    """An unrecognised role grants nothing on the DB path."""
    await _seeded(db_session)
    assert await resolve_granted_permissions(db_session, None, "nope") == set()


async def test_clinic_override_revokes_a_permission(db_session):
    """A per-clinic ``granted=false`` override removes an exactly-held permission."""
    await _seeded(db_session)
    # ``agents.supervise`` is a core grant the dentist holds *exactly* (no
    # ``agents.*`` wildcard covers it), so a revoke is observable.
    perm = (
        (await db_session.execute(select(Permission).where(Permission.code == "agents.supervise")))
        .scalars()
        .first()
    )
    role = (await db_session.execute(select(Role).where(Role.name == "dentist"))).scalars().first()
    assert await has_permission_in_clinic(db_session, None, "dentist", "agents.supervise") is True

    clinic_id = await _make_clinic(db_session)
    db_session.add(
        ClinicRoleOverride(
            clinic_id=clinic_id,
            role_id=role.id,
            permission_id=perm.id,
            granted=False,
        )
    )
    await db_session.flush()
    invalidate_rbac_cache()

    # That clinic loses it; the bare system default is unaffected.
    assert (
        await has_permission_in_clinic(db_session, clinic_id, "dentist", "agents.supervise")
        is False
    )
    assert await has_permission_in_clinic(db_session, None, "dentist", "agents.supervise") is True


async def test_clinic_override_grants_a_permission(db_session):
    """A per-clinic ``granted=true`` override adds an exactly-lacked permission."""
    await _seeded(db_session)
    # Core ``admin.users.write``: the receptionist lacks it exactly (no wildcard).
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
    assert (
        await has_permission_in_clinic(db_session, None, "receptionist", "admin.users.write")
        is False
    )

    clinic_id = await _make_clinic(db_session)
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


async def test_clinic_override_does_not_leak_between_roles(db_session):
    """A grant override for one role never grants another role in the clinic."""
    await _seeded(db_session)
    perm = (
        (await db_session.execute(select(Permission).where(Permission.code == "admin.users.write")))
        .scalars()
        .first()
    )
    receptionist = (
        (await db_session.execute(select(Role).where(Role.name == "receptionist")))
        .scalars()
        .first()
    )

    clinic_id = await _make_clinic(db_session)
    db_session.add(
        ClinicRoleOverride(
            clinic_id=clinic_id,
            role_id=receptionist.id,
            permission_id=perm.id,
            granted=True,
        )
    )
    await db_session.flush()
    invalidate_rbac_cache()

    # Receptionist gains admin.users.write in that clinic; the dentist does not.
    assert (
        await has_permission_in_clinic(db_session, clinic_id, "receptionist", "admin.users.write")
        is True
    )
    assert (
        await has_permission_in_clinic(db_session, clinic_id, "dentist", "admin.users.write")
        is False
    )


async def test_module_wildcard_round_trips_through_db(db_session):
    """Module-level wildcard stored literally still expands via permission_matches."""
    await _seeded(db_session)
    granted = await resolve_granted_permissions(db_session, None, "dentist")
    assert any(
        permission_matches("some_module.read", g) for g in granted if g.endswith(".*")
    ) or any(".*" in g for g in granted), (
        "dentist should hold at least one module wildcard under the seeded grants"
    )
    # Every concrete permission must satisfy itself.
    for g in granted:
        assert permission_matches(g, g) is True


async def test_role_permissions_table_populated(db_session):
    """Seeding leaves role_permissions rows for the system roles."""
    await _seeded(db_session)
    roles = (await db_session.execute(select(Role))).scalars().all()
    for role in roles:
        if not role.is_system:
            continue
        rps = (
            (
                await db_session.execute(
                    select(RolePermission).where(RolePermission.role_id == role.id)
                )
            )
            .scalars()
            .all()
        )
        assert rps, f"system role {role.name} has no role_permissions rows"
