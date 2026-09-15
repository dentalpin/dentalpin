"""staff_attendance: clock rules, state, report, tenancy, HTTP codes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.staff_attendance.service import AttendanceService


async def _member(db_session, clinic_id, role="receptionist"):
    user = User(
        id=uuid4(),
        email=f"s-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="S",
        last_name="T",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic_id, role=role))
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_clock_in_out_and_double_punch_is_409(db_session: AsyncSession, test_clinic: Clinic):
    user = await _member(db_session, test_clinic.id)
    row = await AttendanceService.clock(db_session, test_clinic.id, user.id, "in")
    await db_session.commit()
    assert row.kind == "in"
    with pytest.raises(HTTPException) as exc:
        await AttendanceService.clock(db_session, test_clinic.id, user.id, "in")
    assert exc.value.status_code == 409
    await AttendanceService.clock(db_session, test_clinic.id, user.id, "out")
    await db_session.commit()
    state, _ = await AttendanceService.get_status(db_session, test_clinic.id, user.id)
    assert state == "out"


@pytest.mark.asyncio
async def test_status_defaults_out(db_session: AsyncSession, test_clinic: Clinic):
    user = await _member(db_session, test_clinic.id)
    state, since = await AttendanceService.get_status(db_session, test_clinic.id, user.id)
    assert (state, since) == ("out", None)


@pytest.mark.asyncio
async def test_non_member_clock_is_404(db_session: AsyncSession, test_clinic: Clinic):
    with pytest.raises(HTTPException) as exc:
        await AttendanceService.clock(db_session, test_clinic.id, uuid4(), "in")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_report_pairs_and_flags_open(db_session: AsyncSession, test_clinic: Clinic):
    user = await _member(db_session, test_clinic.id)
    day = datetime(2026, 5, 4, tzinfo=UTC).date()
    t0 = datetime(2026, 5, 4, 8, 0, tzinfo=UTC)
    await AttendanceService.clock(db_session, test_clinic.id, user.id, "in", at=t0)
    await AttendanceService.clock(
        db_session, test_clinic.id, user.id, "out", at=t0 + timedelta(hours=8)
    )
    await AttendanceService.clock(
        db_session, test_clinic.id, user.id, "in", at=t0 + timedelta(hours=9)
    )
    await db_session.commit()
    rows = await AttendanceService.daily_report(
        db_session, test_clinic.id, day, now=t0 + timedelta(hours=10)
    )
    assert len(rows) == 1
    assert rows[0]["seconds"] == 8 * 3600 + 3600
    assert rows[0]["open"] is True


@pytest.mark.asyncio
async def test_http_codes(client, auth_headers, test_clinic: Clinic):
    members = await client.get("/api/v1/staff_attendance/members", headers=auth_headers)
    assert members.status_code == 200
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    admin_id = me.json()["data"]["user"]["id"]

    created = await client.post(
        "/api/v1/staff_attendance/events",
        json={"user_id": admin_id, "kind": "in"},
        headers=auth_headers,
    )
    assert created.status_code == 201

    dup = await client.post(
        "/api/v1/staff_attendance/events",
        json={"user_id": admin_id, "kind": "in"},
        headers=auth_headers,
    )
    assert dup.status_code == 409

    bad_kind = await client.post(
        "/api/v1/staff_attendance/events",
        json={"user_id": admin_id, "kind": "break"},
        headers=auth_headers,
    )
    assert bad_kind.status_code == 422

    stranger = await client.post(
        "/api/v1/staff_attendance/events",
        json={"user_id": str(uuid4()), "kind": "in"},
        headers=auth_headers,
    )
    assert stranger.status_code == 404

    status = await client.get(f"/api/v1/staff_attendance/status/{admin_id}", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["data"]["state"] == "in"

    report = await client.get(
        "/api/v1/staff_attendance/report",
        params={"day": "2026-05-04"},
        headers=auth_headers,
    )
    assert report.status_code == 200


@pytest.mark.asyncio
async def test_denies_roles_without_staff_attendance_grant(
    client, db_session: AsyncSession, test_clinic: Clinic
):
    """A clinic member whose role lacks staff_attendance gets 403 on every route."""
    from app.core.auth.service import create_access_token

    user = User(
        id=uuid4(),
        email=f"no-grant-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="N",
        last_name="G",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(),
            user_id=user.id,
            clinic_id=test_clinic.id,
            role="guest",
        )
    )
    await db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, token_version=0)}"}

    assert (
        await client.get("/api/v1/staff_attendance/members", headers=headers)
    ).status_code == 403
    assert (await client.get("/api/v1/staff_attendance/events", headers=headers)).status_code == 403
    assert (
        await client.post(
            "/api/v1/staff_attendance/events",
            json={"user_id": str(user.id), "kind": "in"},
            headers=headers,
        )
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/staff_attendance/status/{user.id}", headers=headers)
    ).status_code == 403
    assert (
        await client.get(
            "/api/v1/staff_attendance/report", params={"day": "2026-05-04"}, headers=headers
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_isolation_between_clinics(
    client, db_session: AsyncSession, test_clinic: Clinic, auth_headers: dict
):
    """Events in one clinic never leak into another clinic's report/members."""
    from app.core.auth.service import create_access_token

    user = await _member(db_session, test_clinic.id)
    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B87654321",
        address={"street": "Other St", "city": "Valencia"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other_clinic)
    await db_session.flush()
    other_member = User(
        id=uuid4(),
        email=f"other-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="O",
        last_name="M",
        is_active=True,
    )
    db_session.add(other_member)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(), user_id=other_member.id, clinic_id=other_clinic.id, role="dentist"
        )
    )
    await db_session.commit()

    other_headers = {
        "Authorization": f"Bearer {create_access_token(other_member.id, token_version=0)}"
    }
    await client.post(
        "/api/v1/staff_attendance/events",
        json={"user_id": str(other_member.id), "kind": "in"},
        headers=other_headers,
    )

    members = await client.get("/api/v1/staff_attendance/members", headers=auth_headers)
    member_ids = [m["id"] for m in members.json()["data"]]
    assert str(user.id) in member_ids
    assert str(other_member.id) not in member_ids

    report = await client.get(
        "/api/v1/staff_attendance/report", params={"day": "2026-05-04"}, headers=auth_headers
    )
    assert report.json()["data"]["rows"] == []
