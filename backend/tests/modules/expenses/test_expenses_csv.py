"""expenses CSV import: validation, dry-run, commit, endpoint."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.expenses.csv_import import (
    CsvImportError,
    import_expenses,
    validate_expense_csv,
)
from app.modules.expenses.models import Expense

VALID_CSV = (
    "category,amount,expense_date,description\n"
    "rent,1200.00,2026-08-01,August rent\n"
    "supplies,45.50,2026-08-03,\n"
)

BAD_ROWS_CSV = "category,amount,expense_date\nyachts,-50,2026-08-01\nrent,100.00,2026-08-02\n"


def test_validate_accepts_good_rows_and_reports_bad_ones() -> None:
    valid, errors, total = validate_expense_csv(BAD_ROWS_CSV.encode())
    assert total == 2
    assert len(valid) == 1
    assert valid[0].category == "rent"
    assert valid[0].amount == Decimal("100.00")
    assert len(errors) == 1
    assert errors[0]["row"] == 2


def test_validate_rejects_missing_header_and_bad_encoding() -> None:
    with pytest.raises(CsvImportError):
        validate_expense_csv(b"concepto,importe\nAlquiler,100\n")
    with pytest.raises(CsvImportError):
        validate_expense_csv("categoría,importe\nteléfono,1\n".encode("latin-1"))
    with pytest.raises(CsvImportError):
        validate_expense_csv(b"")


def test_validate_sniffs_semicolon_and_spanish_dates() -> None:
    csv_text = b"category;amount;expense_date\nrent;1200.00;01/08/2026\n"
    valid, errors, total = validate_expense_csv(csv_text)
    assert total == 1 and not errors
    assert str(valid[0].expense_date) == "2026-08-01"


@pytest.mark.asyncio
async def test_import_creates_expenses_in_clinic(
    test_clinic: Clinic, db_session: AsyncSession
) -> None:
    valid, errors, total = validate_expense_csv(VALID_CSV.encode())
    assert total == 2 and not errors
    created = await import_expenses(db_session, test_clinic.id, None, valid)
    assert len(created) == 2
    amounts = sorted(
        (
            await db_session.execute(
                select(Expense.amount).where(Expense.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .all()
    )
    assert amounts == [Decimal("45.50"), Decimal("1200.00")]


@pytest.mark.asyncio
async def test_endpoint_dry_run_writes_nothing_then_commits(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, db_session: AsyncSession
) -> None:
    dry = await client.post(
        "/api/v1/expenses/import.csv",
        files={"file": ("expenses.csv", VALID_CSV.encode(), "text/csv")},
        headers=auth_headers,
    )
    assert dry.status_code == 200, dry.text
    body = dry.json()["data"]
    assert (body["total"], body["valid"], body["created"]) == (2, 2, 0)
    assert body["errors"] == []

    before = (
        await db_session.execute(select(Expense).where(Expense.clinic_id == test_clinic.id))
    ).scalars()
    assert len(list(before.all())) == 0

    commit = await client.post(
        "/api/v1/expenses/import.csv?dry_run=false",
        files={"file": ("expenses.csv", VALID_CSV.encode(), "text/csv")},
        headers=auth_headers,
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["data"]["created"] == 2


@pytest.mark.asyncio
async def test_oversize_upload_422s_not_500s(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    from app.modules.expenses.csv_import import MAX_CSV_BYTES

    big = b"category,amount,expense_date\n" + b"rent,1.00,2026-08-01\n" * (
        (MAX_CSV_BYTES // 20) + 10
    )
    assert len(big) > MAX_CSV_BYTES
    response = await client.post(
        "/api/v1/expenses/import.csv",
        files={"file": ("big.csv", big, "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 422
