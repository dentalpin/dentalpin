"""patients CSV import: validation, dry-run, commit, endpoint, isolation."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.patients.csv_import import (
    CsvImportError,
    import_patients,
    validate_patient_csv,
)
from app.modules.patients.models import Patient

VALID_CSV = (
    "first_name,last_name,phone,email,date_of_birth,do_not_contact,national_id\n"
    "Ana,García,+34600111222,ana@example.com,1990-05-01,no,12345678A\n"
    "Luis,Pérez,,,,,\n"
)

BAD_ROWS_CSV = (
    "first_name,last_name,email,do_not_contact\n"
    ",SinNombre,not-an-email,maybe\n"
    "Bien,Formado,bien@example.com,yes\n"
)


def test_validate_accepts_good_rows_and_reports_bad_ones() -> None:
    valid, errors, total = validate_patient_csv(BAD_ROWS_CSV.encode())
    assert total == 2
    assert len(valid) == 1
    assert valid[0].first_name == "Bien"
    assert valid[0].do_not_contact is True
    assert len(errors) == 1
    assert errors[0]["row"] == 2


def test_validate_rejects_missing_header_and_bad_encoding() -> None:
    with pytest.raises(CsvImportError):
        validate_patient_csv(b"nombre,apellido\nJuan,Perez\n")
    with pytest.raises(CsvImportError):
        validate_patient_csv("first_name,last_name\nJosé,X\n".encode("latin-1"))
    with pytest.raises(CsvImportError):
        validate_patient_csv(b"")
    # Unknown columns are ignored so foreign exports import uncleaned.
    valid, errors, total = validate_patient_csv(b"first_name,last_name,whatever\nAna,Garcia,x\n")
    assert total == 1 and not errors and valid[0].last_name == "Garcia"


@pytest.mark.asyncio
async def test_import_creates_patients_in_clinic(
    test_clinic: Clinic, test_patient: Patient, db_session: AsyncSession
) -> None:
    valid, errors, total = validate_patient_csv(VALID_CSV.encode())
    assert total == 2 and not errors
    created = await import_patients(db_session, test_clinic.id, valid)
    assert len(created) == 2
    names = sorted(
        (
            await db_session.execute(
                select(Patient.first_name).where(Patient.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .all()
    )
    assert names == ["Ana", "Luis", "Test"]


@pytest.mark.asyncio
async def test_endpoint_dry_run_writes_nothing_then_commits(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    dry = await client.post(
        "/api/v1/patients/import.csv",
        files={"file": ("patients.csv", VALID_CSV.encode(), "text/csv")},
        headers=auth_headers,
    )
    assert dry.status_code == 200, dry.text
    body = dry.json()["data"]
    assert (body["total"], body["valid"], body["created"]) == (2, 2, 0)
    assert body["errors"] == []

    total_before = (
        await db_session.execute(select(Patient).where(Patient.clinic_id == test_clinic.id))
    ).scalars()
    assert len(list(total_before.all())) == 1  # only the fixture patient

    commit = await client.post(
        "/api/v1/patients/import.csv?dry_run=false",
        files={"file": ("patients.csv", VALID_CSV.encode(), "text/csv")},
        headers=auth_headers,
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["data"]["created"] == 2


@pytest.mark.asyncio
async def test_endpoint_rejects_garbage_csv(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    response = await client.post(
        "/api/v1/patients/import.csv",
        files={"file": ("bad.csv", b"no-header-just-text", "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 422
