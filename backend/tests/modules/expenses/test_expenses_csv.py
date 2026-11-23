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
    csv_text = b"category;amount;expense_date\nrent;1200,50;01/08/2026\n"
    valid, errors, total = validate_expense_csv(csv_text)
    assert total == 1 and not errors
    assert str(valid[0].expense_date) == "2026-08-01"
    assert valid[0].amount == Decimal("1200.50")


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


def test_a_bad_date_is_a_row_error_not_a_whole_file_rejection() -> None:
    """One unreadable date flags its row, like a bad category or amount (#974).

    ``_parse_date`` raised ``CsvImportError`` (documented for whole-file
    problems: encoding, header, caps), which the per-row ``except
    ValidationError`` did not catch, so the dry run answered 422 for the
    whole file and never listed the other rows' errors or the valid rows.
    """
    valid, errors, total = validate_expense_csv(
        b"category,amount,expense_date\n"
        b"rent,100,2026-08-01\n"
        b"rent,5,2026/08/01\n"
        b"yachts,1,2026-08-01\n"
    )
    assert total == 3
    assert [v.amount for v in valid] == [Decimal("100")]
    assert [e["row"] for e in errors] == [3, 4]
    assert "expense_date" in errors[0]["message"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('"1,200"', Decimal("1200")),  # English Excel thousands
        ('"1,234.56"', Decimal("1234.56")),
        ("1.200", Decimal("1200")),  # Spanish Excel thousands
        ('"1.234,56"', Decimal("1234.56")),
        ('"1200,5"', Decimal("1200.50")),
        ("1200.50", Decimal("1200.50")),
        ('"1,200,000"', Decimal("1200000")),
        ("0.50", Decimal("0.50")),
        ('"0,5"', Decimal("0.50")),
    ],
)
def test_validate_reads_thousands_separators(raw: str, expected: Decimal) -> None:
    """A thousands separator is never read as a decimal point (#962).

    "1,200" and "1.200" used to become 1.20: the row was valid and the
    expense was stored 1000 times too small.
    """
    valid, errors, total = validate_expense_csv(
        f"category,amount,expense_date\nrent,{raw},2026-08-01\n".encode()
    )
    assert total == 1 and not errors, errors
    assert valid[0].amount == expected


def test_validate_reports_an_ambiguous_amount_as_a_row_error() -> None:
    """A separator followed by neither 1-2 nor groups of 3 digits is refused."""
    valid, errors, total = validate_expense_csv(
        b"category,amount,expense_date\nrent,1.2345,2026-08-01\nrent,10,2026-08-01\n"
    )
    assert total == 2
    assert len(valid) == 1
    assert errors and errors[0]["row"] == 2


# #1114: a spreadsheet's trailing ",,," line has one cell more than the header.
RAGGED_CSV = b"category,amount,expense_date\nrent,100.00,2026-11-01\n,,,\n"


def test_validate_ignores_cells_beyond_the_header() -> None:
    valid, errors, total = validate_expense_csv(RAGGED_CSV)
    assert (total, errors) == (1, [])
    assert valid[0].amount == Decimal("100.00")

    extra = b"category,amount,expense_date\nrent,100.00,2026-11-01,stray\n"
    valid, errors, total = validate_expense_csv(extra)
    assert (total, errors) == (1, [])


def test_validate_reads_a_column_whose_header_is_padded() -> None:
    padded = b"category, amount ,expense_date\nrent,100.00,2026-11-01\n"
    valid, errors, total = validate_expense_csv(padded)
    assert (total, errors) == (1, [])
    assert valid[0].amount == Decimal("100.00")


@pytest.mark.asyncio
async def test_endpoint_answers_a_ragged_file_without_a_500(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    response = await client.post(
        "/api/v1/expenses/import.csv",
        files={"file": ("ragged.csv", RAGGED_CSV, "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert (body["total"], body["valid"], body["errors"]) == (1, 1, [])
