"""CSV expense import — parse, validate (dry-run), and commit.

Column contract (header row required; unknown columns ignored):

    category* (rent|utilities|salaries|supplies|equipment|insurance|
    maintenance|other), amount* (decimal > 0), expense_date* (YYYY-MM-DD
    or DD/MM/YYYY), description

Delimiter is sniffed (`,` or `;`, comma fallback for Spanish Excel).
``*`` required. Validation reuses ``ExpenseCreate`` itself, so the import
can never admit a row the API would reject. Caps: 1000 rows, 1 MiB.
Commit is all-or-nothing (single flush; the request commits) — unlike
single ``create_expense``, which commits per call.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.expenses.models import Expense

from .schemas import ExpenseCreate
from .service import ExpenseService

MAX_CSV_ROWS = 1000
MAX_CSV_BYTES = 1024 * 1024

REQUIRED_COLUMNS = ("category", "amount", "expense_date")

COLUMN_MAP = {
    "category": "category",
    "amount": "amount",
    "expense_date": "expense_date",
    "description": "description",
}


class CsvImportError(ValueError):
    """Whole-file rejection (encoding, header, caps). Maps to 422."""


async def read_upload_limited(file) -> bytes:  # noqa: ANN001 — Starlette UploadFile
    """Read at most cap+1 bytes so the size check precedes buffering."""
    content = await file.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES:
        raise CsvImportError(f"CSV exceeds {MAX_CSV_BYTES // 1024} KiB")
    return content


def _detect_reader(text: str) -> csv.DictReader:
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;")
    except csv.Error:
        return csv.DictReader(io.StringIO(text))
    return csv.DictReader(io.StringIO(text), dialect=dialect)


def _parse_date(raw: str, row_number: int) -> object:
    value = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise CsvImportError(f"row {row_number}: expense_date must be YYYY-MM-DD or DD/MM/YYYY")


def validate_expense_csv(content: bytes) -> tuple[list[ExpenseCreate], list[dict], int]:
    """Validate CSV bytes without writing anything.

    Returns ``(valid_rows, errors, total)`` where errors are
    ``{"row": int, "message": str}`` (row = 1-based file line).
    Raises ``CsvImportError`` for whole-file problems.
    """
    if len(content) > MAX_CSV_BYTES:
        raise CsvImportError(f"CSV exceeds {MAX_CSV_BYTES // 1024} KiB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvImportError("CSV must be UTF-8 encoded")
    reader = _detect_reader(text)
    if reader.fieldnames is None:
        raise CsvImportError("CSV has no header row")
    headers = [h.strip() for h in reader.fieldnames if h and h.strip()]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise CsvImportError(f"CSV missing required columns: {', '.join(missing)}")

    valid: list[ExpenseCreate] = []
    errors: list[dict] = []
    total = 0
    for line_number, raw_row in enumerate(reader, start=2):
        if all((v or "").strip() == "" for v in raw_row.values()):
            continue  # skip blank lines
        total += 1
        if total > MAX_CSV_ROWS:
            raise CsvImportError(f"CSV exceeds {MAX_CSV_ROWS} rows")
        try:
            data = {
                COLUMN_MAP[header]: (raw_row.get(header) or "").strip()
                for header in headers
                if header in COLUMN_MAP
            }
            data = {k: v for k, v in data.items() if v != ""}
            if "expense_date" in data:
                data["expense_date"] = _parse_date(data["expense_date"], line_number)
            valid.append(ExpenseCreate.model_validate(data))
        except ValidationError as exc:
            first = exc.errors()[0]
            errors.append({"row": line_number, "message": f"{first['loc'][0]}: {first['msg']}"})
    return valid, errors, total


async def import_expenses(
    db: AsyncSession, clinic_id: UUID, user_id: UUID | None, rows: list[ExpenseCreate]
) -> list[Expense]:
    """Persist validated rows via bulk create (all-or-nothing)."""
    return await ExpenseService.bulk_create(db, clinic_id, rows, user_id)
