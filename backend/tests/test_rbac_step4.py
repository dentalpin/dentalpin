"""Step 4 of issue #46: ``role_id`` written on membership paths + flag-aware callers.

Covers the two halves of the maintainer's follow-up:

1. ``resolve_role_id`` maps a membership role name to its ``roles`` row
   (clinic-custom first, system fallback, ``None`` for unknown), and the
   HTTP membership paths persist it.
2. Every sync ``has_permission(ctx.role, ...)`` caller outside
   ``require_permission`` now resolves flag-aware: schedules professional
   gate, verifactu promote check, copilot history filter + nudges +
   agent contexts, and the plugins nav filter.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

from app.config import settings
from app.core.auth.dependencies import ClinicContext
from app.core.auth.models import (
    Clinic,
    ClinicMembership,
    ClinicRoleOverride,
    Permission,
    Role,
    RolePermission,
)
from app.core.auth.permissions import get_role_permissions, has_permission
from app.core.auth.rbac import (
    granted_permissions_for,
    has_permission_for,
    invalidate_rbac_cache,
    resolve_role_id,
)
from app.core.auth.seed_rbac import seed_rbac


@pytest.fixture(autouse=True)
def _flag_off():
    """Default to the static map; tests opt into the DB path explicitly."""
    original = settings.RBAC_FROM_DB
    settings.RBAC_FROM_DB = False
    yield
    settings.RBAC_FROM_DB = original
    invalidate_rbac_cache()


async def _seeded(db):
    invalidate_rbac_cache()
    await seed_rbac(db)
    return db


async def _new_clinic(db, name: str = "step4 clinic") -> str:
    clinic = Clinic(id=uuid4(), name=name, tax_id="B00000002")
    db.add(clinic)
    await db.flush()
    return str(clinic.id)


def _ctx(clinic_id: str, role: str, user_id=None) -> ClinicContext:
    user = SimpleNamespace(id=user_id or uuid4())
    clinic = SimpleNamespace(id=clinic_id)
    return ClinicContext(user, clinic, role)  # type: ignore[arg-type]


async def _custom_role(db, clinic_id: str, name: str = "scheduler") -> Role:
    role = Role(id=uuid4(), clinic_id=clinic_id, name=name, is_system=False)
    db.add(role)
    await db.flush()
    return role


async def _grant(db, role: Role, code: str) -> None:
    perm = (await db.execute(select(Permission).where(Permission.code == code))).scalars().first()
    assert perm is not None, f"seeded permissions lack {code}"
    db.add(RolePermission(id=uuid4(), role_id=role.id, permission_id=perm.id))
    await db.flush()
    invalidate_rbac_cache()


# --- resolve_role_id ----------------------------------------------------


async def test_resolve_role_id_system_role(db_session):
    await _seeded(db_session)
    system_admin = (
        (await db_session.execute(select(Role).where(Role.name == "admin"))).scalars().first()
    )
    assert await resolve_role_id(db_session, await _new_clinic(db_session), "admin") == (
        system_admin.id
    )


async def test_resolve_role_id_unknown_is_none(db_session):
    await _seeded(db_session)
    assert await resolve_role_id(db_session, await _new_clinic(db_session), "nope") is None


async def test_resolve_role_id_prefers_clinic_custom(db_session):
    await _seeded(db_session)
    clinic_id = await _new_clinic(db_session)
    custom = await _custom_role(db_session, clinic_id, name="dentist")
    assert await resolve_role_id(db_session, clinic_id, "dentist") == custom.id


# --- flag-aware helpers -------------------------------------------------


async def test_flag_off_matches_static_map(db_session):
    await _seeded(db_session)
    clinic_id = await _new_clinic(db_session)
    for role in ("admin", "dentist", "hygienist", "assistant", "receptionist"):
        assert set(await granted_permissions_for(db_session, clinic_id, role)) == set(
            get_role_permissions(role)
        )
    probe = [
        ("dentist", "patients.read", True),
        ("dentist", "admin.users.write", False),
        ("receptionist", "patients_clinical.emergency.read", True),
    ]
    for role, perm, expected in probe:
        assert await has_permission_for(db_session, clinic_id, role, perm) is expected
        assert has_permission(role, perm) is expected


async def test_flag_on_honors_override_and_custom_role(db_session):
    await _seeded(db_session)
    settings.RBAC_FROM_DB = True
    clinic_id = await _new_clinic(db_session)
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
            clinic_id=clinic_id, role_id=role.id, permission_id=perm.id, granted=True
        )
    )
    await db_session.flush()
    invalidate_rbac_cache()
    assert (
        await has_permission_for(db_session, clinic_id, "receptionist", "admin.users.write") is True
    )
    assert await has_permission_for(db_session, None, "receptionist", "admin.users.write") is False

    custom = await _custom_role(db_session, clinic_id)
    await _grant(db_session, custom, "schedules.professional.read")
    assert (
        await has_permission_for(db_session, clinic_id, "scheduler", "schedules.professional.read")
        is True
    )
    assert (
        await has_permission_for(db_session, clinic_id, "scheduler", "admin.users.write") is False
    )


# --- migrated callers ---------------------------------------------------


async def test_schedules_gate_honors_custom_role_when_flag_on(db_session):
    from app.modules.schedules.router import _require_professional_access

    await _seeded(db_session)
    settings.RBAC_FROM_DB = True
    clinic_id = await _new_clinic(db_session)
    custom = await _custom_role(db_session, clinic_id)
    await _grant(db_session, custom, "schedules.professional.read")
    ctx = _ctx(clinic_id, "scheduler")
    # No exception: the custom grant satisfies the general permission.
    await _require_professional_access(db_session, ctx, uuid4(), "read")
    # Without the grant the gate still refuses.
    with pytest.raises(HTTPException) as exc_info:
        await _require_professional_access(db_session, ctx, uuid4(), "write")
    assert exc_info.value.status_code == 403


async def test_schedules_gate_own_permission_still_scoped_to_self(db_session):
    from app.modules.schedules.router import _require_professional_access

    await _seeded(db_session)
    settings.RBAC_FROM_DB = True
    clinic_id = await _new_clinic(db_session)
    custom = await _custom_role(db_session, clinic_id)
    await _grant(db_session, custom, "schedules.professional.own.read")
    me = uuid4()
    await _require_professional_access(db_session, _ctx(clinic_id, "scheduler", me), me, "read")
    with pytest.raises(HTTPException):
        await _require_professional_access(
            db_session, _ctx(clinic_id, "scheduler", me), uuid4(), "read"
        )


async def test_nav_filter_uses_effective_grants(db_session):
    from app.core.plugins.router import _nav_visible

    await _seeded(db_session)
    settings.RBAC_FROM_DB = True
    clinic_id = await _new_clinic(db_session)
    custom = await _custom_role(db_session, clinic_id)
    await _grant(db_session, custom, "schedules.professional.read")
    granted = await granted_permissions_for(db_session, clinic_id, "scheduler")
    assert _nav_visible({"permission": "schedules.professional.read"}, granted) is True
    assert _nav_visible({"permission": "admin.users.write"}, granted) is False
    assert _nav_visible({"label": "no gate"}, granted) is True


async def test_copilot_nudges_filtered_by_effective_grants(db_session):
    from app.modules.copilot.models import CopilotNudge
    from app.modules.copilot.service import NudgeService

    await _seeded(db_session)
    settings.RBAC_FROM_DB = True
    clinic_id = await _new_clinic(db_session)
    custom = await _custom_role(db_session, clinic_id)
    await _grant(db_session, custom, "schedules.professional.read")
    from datetime import timedelta

    future = datetime.now(UTC) + timedelta(days=1)
    db_session.add_all(
        [
            CopilotNudge(
                clinic_id=clinic_id,
                kind="a",
                dedupe_key="a",
                required_permission="schedules.professional.read",
                expires_at=future,
            ),
            CopilotNudge(
                clinic_id=clinic_id,
                kind="b",
                dedupe_key="b",
                required_permission="admin.users.write",
                expires_at=future,
            ),
            CopilotNudge(
                clinic_id=clinic_id,
                kind="c",
                dedupe_key="c",
                expires_at=future,
            ),
        ]
    )
    await db_session.flush()

    visible = await NudgeService.list_active(db_session, clinic_id, role="scheduler")
    assert {n.kind for n in visible} == {"a", "c"}


# --- membership write paths ---------------------------------------------


async def test_create_user_persists_role_id(client, auth_headers, test_clinic, db_session):
    """POST /auth/users stores the roles-row FK alongside the role string."""
    await _seeded(db_session)
    payload = {
        "email": "roleid@test.clinic",
        "password": "Str0ngPassw0rd!!",
        "first_name": "R",
        "last_name": "I",
        "role": "dentist",
    }
    resp = await client.post("/api/v1/auth/users", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    membership = (
        (
            await db_session.execute(
                select(ClinicMembership).where(
                    ClinicMembership.clinic_id == test_clinic.id,
                    ClinicMembership.role == "dentist",
                )
            )
        )
        .scalars()
        .all()
    )
    assert membership, "membership row missing"
    system_dentist = (
        (await db_session.execute(select(Role).where(Role.name == "dentist"))).scalars().first()
    )
    assert all(m.role_id == system_dentist.id for m in membership)


async def test_create_user_with_custom_role_persists_custom_role_id(
    client, auth_headers, test_clinic, db_session
):
    """A clinic-custom assignment stores the custom row, not the system one."""
    await _seeded(db_session)
    created = (
        await client.post(
            "/api/v1/roles",
            json={"name": "roleidcustom", "permissions": []},
            headers=auth_headers,
        )
    ).json()["data"]
    settings.RBAC_FROM_DB = True
    try:
        resp = await client.post(
            "/api/v1/auth/users",
            json={
                "email": "customroleid@test.clinic",
                "password": "Str0ngPassw0rd!!",
                "first_name": "C",
                "last_name": "U",
                "role": "roleidcustom",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
    finally:
        settings.RBAC_FROM_DB = False
    membership = (
        (
            await db_session.execute(
                select(ClinicMembership).where(
                    ClinicMembership.clinic_id == test_clinic.id,
                    ClinicMembership.role == "roleidcustom",
                )
            )
        )
        .scalars()
        .one()
    )
    assert str(membership.role_id) == created["id"]


async def test_update_user_rewrites_role_id(client, auth_headers, test_clinic, db_session):
    """PUT /auth/users/{id} keeps the FK in step with the role string."""
    await _seeded(db_session)
    created_user = (
        await client.post(
            "/api/v1/auth/users",
            json={
                "email": "rewrite@test.clinic",
                "password": "Str0ngPassw0rd!!",
                "first_name": "W",
                "last_name": "R",
                "role": "receptionist",
            },
            headers=auth_headers,
        )
    ).json()["data"]
    resp = await client.put(
        f"/api/v1/auth/users/{created_user['id']}",
        json={"role": "assistant"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    membership = (
        (
            await db_session.execute(
                select(ClinicMembership).where(
                    ClinicMembership.clinic_id == test_clinic.id,
                    ClinicMembership.role == "assistant",
                )
            )
        )
        .scalars()
        .one()
    )
    system_assistant = (
        (await db_session.execute(select(Role).where(Role.name == "assistant"))).scalars().first()
    )
    assert membership.role_id == system_assistant.id


async def test_delete_role_blocked_by_role_id_holders(
    client, auth_headers, test_clinic, db_session
):
    """The delete guard sees FK-held memberships, not just the role string."""
    await _seeded(db_session)
    created = (
        await client.post(
            "/api/v1/roles",
            json={"name": "fkheld", "permissions": []},
            headers=auth_headers,
        )
    ).json()["data"]
    # The FK holder is a SECOND user: adding a second membership row for
    # the signed-in admin would make get_clinic_context resolve either
    # row (unordered memberships[0]) and flake 403 vs 409.
    holder = (
        await client.post(
            "/api/v1/auth/users",
            json={
                "email": "fkholder@test.clinic",
                "password": "Str0ngPassw0rd!!",
                "first_name": "F",
                "last_name": "K",
                "role": "receptionist",
            },
            headers=auth_headers,
        )
    ).json()["data"]
    await db_session.execute(
        update(ClinicMembership)
        .where(
            ClinicMembership.clinic_id == test_clinic.id,
            ClinicMembership.user_id == holder["id"],
        )
        .values(role_id=created["id"])
    )
    await db_session.commit()
    resp = await client.delete(f"/api/v1/roles/{created['id']}", headers=auth_headers)
    assert resp.status_code == 409
