"""The import re-uses a staff account whatever the case of its stored email.

Addresses written before #840 can carry capitals (``Anna.Kovacs@…``) while
the import lowercases what it reads. A case-sensitive lookup missed the
existing account and created a second one with a disabled password. Login
prefers the exact spelling, so the person typing their address in lowercase
then hit the unusable imported account and could no longer log in.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.migration_import.mappers.base import MapperContext, MappingResolver
from app.modules.migration_import.mappers.professional import ProfessionalMapper
from app.modules.migration_import.mappers.user import UserMapper
from app.modules.migration_import.models import ImportJob


async def _setup(db_session) -> tuple[Clinic, User, MapperContext]:
    clinic = Clinic(id=uuid4(), name="C", tax_id="B1")
    existing = User(
        id=uuid4(),
        email="Anna.Kovacs@clinic.example",  # written before #840
        password_hash=hash_password("RealPassword123"),
        first_name="Anna",
        last_name="Kovacs",
    )
    db_session.add_all([clinic, existing])
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), clinic_id=clinic.id, user_id=existing.id, role="admin")
    )
    job = ImportJob(
        clinic_id=clinic.id,
        created_by=existing.id,
        status="executing",
        original_filename="t.dpm",
        file_path="/tmp/t.dpm",
        file_size=0,
    )
    db_session.add(job)
    await db_session.flush()
    ctx = MapperContext(
        db=db_session,
        clinic_id=clinic.id,
        job_id=job.id,
        resolver=MappingResolver(db=db_session, clinic_id=clinic.id, job_id=job.id),
        import_fiscal_compliance=False,
        created_by=existing.id,
    )
    return clinic, existing, ctx


async def _accounts(db_session) -> list[User]:
    rows = await db_session.execute(
        select(User).where(func.lower(User.email) == "anna.kovacs@clinic.example")
    )
    return list(rows.scalars())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mapper", "entity_type"), [(UserMapper, "user"), (ProfessionalMapper, "professional")]
)
async def test_import_reuses_the_account_stored_with_capitals(
    db_session, mapper, entity_type
) -> None:
    _, existing, ctx = await _setup(db_session)

    user_id = await mapper().apply(
        ctx,
        entity_type=entity_type,
        payload={"email": "anna.kovacs@clinic.example", "given_name": "Anna", "role": "doctor"},
        raw={},
        canonical_uuid=str(uuid4()),
        source_id="1",
        source_system="gesden",
    )
    await db_session.flush()

    assert [u.id for u in await _accounts(db_session)] == [existing.id]
    assert user_id == existing.id


@pytest.mark.asyncio
async def test_staff_member_still_logs_in_lowercase_after_an_import(
    client: AsyncClient, db_session
) -> None:
    _, _, ctx = await _setup(db_session)
    await ProfessionalMapper().apply(
        ctx,
        entity_type="professional",
        payload={"email": "anna.kovacs@clinic.example", "role": "doctor"},
        raw={},
        canonical_uuid=str(uuid4()),
        source_id="1",
        source_system="gesden",
    )
    await db_session.commit()

    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "anna.kovacs@clinic.example", "password": "RealPassword123"},
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_logging_into_an_imported_account_is_refused_not_a_500(
    client: AsyncClient, db_session
) -> None:
    """Imported accounts carry ``!migration_disabled:…`` instead of a bcrypt
    hash until an admin sends a reset link; bcrypt raised on it."""
    _, _, ctx = await _setup(db_session)
    await ProfessionalMapper().apply(
        ctx,
        entity_type="professional",
        payload={"email": "new.dentist@clinic.example", "role": "doctor"},
        raw={},
        canonical_uuid=str(uuid4()),
        source_id="2",
        source_system="gesden",
    )
    await db_session.commit()

    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "new.dentist@clinic.example", "password": "AnyPassword123"},
    )
    assert r.status_code == 401, r.text
