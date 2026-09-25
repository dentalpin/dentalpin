"""Shared helpers for the leads test suite.

Fixtures from the repo-wide `tests/conftest.py` (`db_session`,
`client`, `auth_headers`, `test_clinic`, `test_patient`) cover the
common ground; this file adds what only the leads tests need: a second
clinic (tenancy), a role-scoped staff member, and a way to take a
permission away from a role so the cross-module permission dependencies
are actually exercised.
"""

from __future__ import annotations

import contextlib
from uuid import UUID, uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.permissions import invalidate_role_permissions_cache
from app.core.auth.service import create_access_token
from app.core.plugins.registry import module_registry
from app.modules.patients.models import Patient

# The receptionist holds leads.read + leads.write (from the leads
# manifest) and is the role most of the permission tests are built on.
STAFF_ROLE = "receptionist"


async def make_clinic(db: AsyncSession, name: str = "Other Clinic") -> Clinic:
    clinic = Clinic(
        id=uuid4(),
        name=name,
        tax_id="B87654321",
        address={"street": "Other St", "city": "Madrid"},
        settings={},
    )
    db.add(clinic)
    await db.commit()
    return clinic


async def make_patient(db: AsyncSession, clinic_id: UUID, **overrides) -> Patient:
    """A patient whose phone matches no test enquiry by default."""
    data = {
        "first_name": "Known",
        "last_name": "Patient",
        "phone": "600000001",
        "email": "known@example.com",
    }
    data.update(overrides)
    patient = Patient(clinic_id=clinic_id, **data)
    db.add(patient)
    await db.commit()
    return patient


async def make_headers(db: AsyncSession, clinic_id: UUID, role: str = STAFF_ROLE) -> dict[str, str]:
    """A staff member of `clinic_id` with `role`, as bearer headers."""
    user = User(
        id=uuid4(),
        email=f"staff-{uuid4().hex[:8]}@test.clinic",
        password_hash="not-a-real-hash",
        first_name="Staff",
        last_name="Member",
    )
    db.add(user)
    await db.flush()
    db.add(ClinicMembership(user_id=user.id, clinic_id=clinic_id, role=role))
    await db.commit()
    token = create_access_token(user.id, token_version=user.token_version)
    return {"Authorization": f"Bearer {token}"}


@contextlib.contextmanager
def role_grants(role: str, perms: list[str], module_name: str = "patients"):
    """Temporarily replace one role's grants in a module's manifest.

    Every built-in role holds `patients.read` / `patients.write`, so the
    cross-module permission dependencies (POST / needs patients.read,
    /convert needs patients.write) can only be exercised by taking one
    away — which is what this does, then puts it back.
    """
    module = module_registry.get(module_name)
    assert module is not None, f"module {module_name} is not registered"
    manifest = module.manifest
    original = manifest["role_permissions"].get(role)
    manifest["role_permissions"][role] = perms
    invalidate_role_permissions_cache()
    try:
        yield
    finally:
        if original is None:
            manifest["role_permissions"].pop(role, None)
        else:
            manifest["role_permissions"][role] = original
        invalidate_role_permissions_cache()


@pytest_asyncio.fixture
async def other_clinic(db_session: AsyncSession) -> Clinic:
    """A second clinic — nothing in it is visible to `test_clinic`."""
    return await make_clinic(db_session)


@pytest_asyncio.fixture
async def staff_headers(db_session: AsyncSession, test_clinic: Clinic) -> dict[str, str]:
    """Headers for a receptionist of `test_clinic` (leads read + write)."""
    return await make_headers(db_session, test_clinic.id)
