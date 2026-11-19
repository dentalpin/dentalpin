"""Patient access recording, tenant-scoped review and retention."""

import asyncio
import csv
from datetime import UTC, datetime
from io import StringIO
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.requests import Request

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import create_access_token
from app.core.patient_access import AccessRecorder, PatientAccessLog
from app.core.patient_access_retention import purge_expired_access
from app.database import engine
from app.modules.patients.models import Patient

API = "/api/v1/gdpr/access-log"


async def test_patient_read_records_once_and_does_not_confirm_unknown_patients(
    client, db_session, auth_headers, test_patient
):
    path = f"/api/v1/patients/{test_patient.id}"
    for suffix in ("", "/extended", ""):
        response = await client.get(path + suffix, headers=auth_headers)
        assert response.status_code == 200, response.text
    unknown = await client.get(f"/api/v1/patients/{uuid4()}", headers=auth_headers)
    assert unknown.status_code == 404

    observed = await db_session.scalar(select(PatientAccessLog))
    entries = (await db_session.scalars(select(PatientAccessLog))).all()
    assert len(entries) == 1
    assert observed.patient_id == test_patient.id
    assert observed.resource == "patient_record"
    assert observed.action == "view"


async def test_concurrent_reads_deduplicate_by_window_and_downloads_are_individual(
    monkeypatch, db_session, test_patient
):
    from app.core import patient_access

    class Clock(datetime):
        instant = datetime(2026, 11, 18, 10, 0, 1, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            return cls.instant

    monkeypatch.setattr(patient_access, "datetime", Clock)
    ctx = SimpleNamespace(clinic_id=test_patient.clinic_id, user_id=uuid4())
    request = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 80)})
    make_session = async_sessionmaker(engine, expire_on_commit=False)

    async def record(resource="odontogram", action="view"):
        async with make_session() as db:
            await AccessRecorder(db, ctx, request)(test_patient.id, resource, action=action)

    # Same SQL index conflict from independent transactions; no read-before-write.
    await asyncio.wait_for(asyncio.gather(*(record() for _ in range(30))), timeout=15)
    Clock.instant = Clock.instant.replace(minute=9, second=59)
    await record()
    Clock.instant = Clock.instant.replace(minute=10, second=0)
    await record()
    await record("medical_history")
    await record("document_pdf", action="download")
    await record("document_pdf", action="download")
    observed = (
        await db_session.execute(
            select(PatientAccessLog.resource, func.count()).group_by(PatientAccessLog.resource)
        )
    ).all()
    assert dict(observed) == {"odontogram": 2, "medical_history": 1, "document_pdf": 2}


def entry(clinic_id, user_id, patient_id, instant, **metadata):
    return PatientAccessLog(
        clinic_id=clinic_id,
        user_id=user_id,
        patient_id=patient_id,
        resource="medical_history",
        action="view",
        occurred_at=instant,
        window_start=instant,
        **metadata,
    )


async def test_query_and_csv_filter_clinic_subject_and_clinic_calendar(
    client, db_session, auth_headers, test_patient, test_clinic
):
    user = await db_session.scalar(select(User).where(User.email == "test@example.com"))
    other_clinic = Clinic(name="Synthetic second clinic", tax_id="SYN2")
    db_session.add(other_clinic)
    await db_session.flush()
    other_patient = Patient(clinic_id=other_clinic.id, first_name="Other", last_name="Synthetic")
    db_session.add(other_patient)
    await db_session.flush()
    # The same user ID has entries in two clinics; filtering by user is still scoped.
    first = datetime(2026, 1, 3, 23, 30, tzinfo=UTC)  # 04 Jan in Madrid.
    db_session.add_all(
        [
            entry(test_clinic.id, user.id, test_patient.id, first, user_agent="=2+2"),
            entry(test_clinic.id, user.id, test_patient.id, first.replace(hour=22)),
            entry(other_clinic.id, user.id, other_patient.id, first),
        ]
    )
    await db_session.commit()

    params = {"user_id": str(user.id), "start": "2026-01-04", "end": "2026-01-04"}
    response = await client.get(API, params=params, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["total"] == 1
    assert response.json()["data"][0]["patient_id"] == str(test_patient.id)
    scoped = await client.get(
        API, params={"patient_id": str(other_patient.id)}, headers=auth_headers
    )
    assert scoped.json()["data"] == []
    assert (await client.get(API, headers=auth_headers)).status_code == 422
    assert (
        await client.get(API + "/csv", params={"user_id": str(user.id)}, headers=auth_headers)
    ).status_code == 422
    exported = await client.get(API + "/csv", params=params, headers=auth_headers)
    assert exported.status_code == 200, exported.text
    rows = list(csv.DictReader(StringIO(exported.text.lstrip("\ufeff"))))
    assert len(rows) == 1
    assert rows[0]["patient_id"] == str(test_patient.id)
    assert rows[0]["user_agent"] == "'=2+2"

    limited = User(
        email="limited@example.test",
        password_hash="unused",
        first_name="Synthetic",
        last_name="Limited",
    )
    db_session.add(limited)
    await db_session.flush()
    db_session.add(
        ClinicMembership(user_id=limited.id, clinic_id=test_clinic.id, role="receptionist")
    )
    await db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(limited.id, token_version=0)}"}
    for endpoint in (API, API + "/csv", API + "/users"):
        assert (await client.get(endpoint, params=params, headers=headers)).status_code == 403


async def test_retention_is_clinic_specific_and_patient_erasure_keeps_rows(
    client, db_session, auth_headers, test_patient, test_clinic
):
    settings = await client.get(API + "/retention", headers=auth_headers)
    assert settings.json()["data"]["years"] == 5
    changed = await client.put(API + "/retention", json={"years": 2}, headers=auth_headers)
    assert changed.status_code == 200, changed.text
    assert test_clinic.settings["slot_duration_min"] == 15

    second = Clinic(name="Synthetic other clinic", tax_id="SYN03")
    db_session.add(second)
    await db_session.flush()
    date = datetime(2022, 11, 18, tzinfo=UTC)
    user_id = uuid4()
    db_session.add_all(
        [
            entry(test_clinic.id, user_id, test_patient.id, date),
            entry(test_clinic.id, user_id, test_patient.id, date.replace(year=2025)),
            entry(second.id, user_id, uuid4(), date),
        ]
    )
    await db_session.commit()
    patient_id = test_patient.id
    await db_session.delete(test_patient)
    await db_session.commit()

    now = datetime(2026, 11, 18, tzinfo=UTC)
    await purge_expired_access(db_session, now=now)
    rows = (await db_session.scalars(select(PatientAccessLog))).all()
    assert len(rows) == 2
    assert {row.clinic_id for row in rows} == {test_clinic.id, second.id}
    assert any(row.patient_id == patient_id for row in rows)
