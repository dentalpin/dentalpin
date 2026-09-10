"""patients CSV import: validation, dry-run, commit, endpoint, isolation, duplicates."""

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
    valid, errors, total, lines = validate_patient_csv(BAD_ROWS_CSV.encode())
    assert total == 2
    assert len(valid) == 1
    assert valid[0].first_name == "Bien"
    assert valid[0].do_not_contact is True
    assert lines == [3]
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
    valid, errors, total, _lines = validate_patient_csv(
        b"first_name,last_name,whatever\nAna,Garcia,x\n"
    )
    assert total == 1 and not errors and valid[0].last_name == "Garcia"


def test_validate_sniffs_semicolon_and_spanish_dates() -> None:
    csv_text = "first_name;last_name;date_of_birth\nAna;García;01/05/1990\n".encode()
    valid, errors, total, _lines = validate_patient_csv(csv_text)
    assert total == 1 and not errors
    assert str(valid[0].date_of_birth) == "1990-05-01"
    _valid, bad_errors, _total, _ln = validate_patient_csv(
        b"first_name,last_name,date_of_birth\nAna,X,01.05.1990\n"
    )
    assert len(bad_errors) == 1 and "YYYY-MM-DD" in bad_errors[0]["message"]


@pytest.mark.asyncio
async def test_import_creates_patients_in_clinic(
    test_clinic: Clinic, test_patient: Patient, db_session: AsyncSession
) -> None:
    valid, errors, total, _lines = validate_patient_csv(VALID_CSV.encode())
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


@pytest.mark.asyncio
async def test_oversize_upload_422s_not_500s(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    from app.modules.patients.csv_import import MAX_CSV_BYTES

    big = b"first_name,last_name\n" + b"A,B\n" * ((MAX_CSV_BYTES // 4) + 10)
    assert len(big) > MAX_CSV_BYTES
    response = await client.post(
        "/api/v1/patients/import.csv",
        files={"file": ("big.csv", big, "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicates_flagged_and_skipped_unless_allowed(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    # The fixture patient has no national_id/email — give it a matchable id.
    test_patient.national_id = "99999999Z"
    await db_session.commit()
    dup_csv = b"first_name,last_name,national_id\nAna,Garcia,99999999Z\nLuis,Perez,\n"

    dry = await client.post(
        "/api/v1/patients/import.csv",
        files={"file": ("dup.csv", dup_csv, "text/csv")},
        headers=auth_headers,
    )
    assert dry.status_code == 200, dry.text
    body = dry.json()["data"]
    assert len(body["duplicates"]) == 1
    assert body["duplicates"][0]["row"] == 2
    assert body["duplicates"][0]["matched_on"] == "national_id"

    commit = await client.post(
        "/api/v1/patients/import.csv?dry_run=false",
        files={"file": ("dup.csv", dup_csv, "text/csv")},
        headers=auth_headers,
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["data"]["created"] == 1
    assert commit.json()["data"]["skipped"] == 1

    forced = await client.post(
        "/api/v1/patients/import.csv?dry_run=false&allow_duplicates=true",
        files={"file": ("dup.csv", dup_csv, "text/csv")},
        headers=auth_headers,
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["data"]["created"] == 2


@pytest.mark.asyncio
async def test_intra_file_duplicates_flagged(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
) -> None:
    twin_csv = b"first_name,last_name,national_id\nAna,Garcia,11111111H\nEva,Lopez,11111111H\n"
    dry = await client.post(
        "/api/v1/patients/import.csv",
        files={"file": ("twins.csv", twin_csv, "text/csv")},
        headers=auth_headers,
    )
    assert dry.status_code == 200, dry.text
    body = dry.json()["data"]
    assert len(body["duplicates"]) == 1
    assert body["duplicates"][0]["row"] == 3
    assert body["duplicates"][0]["matched_on"] == "same_file"
