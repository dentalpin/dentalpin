"""CSV expense import — parse, validate (dry-run), and commit.

Column contract (header row required; unknown columns ignored):

    category* (rent|utilities|salaries|supplies|equipment|insurance|
    maintenance|other), amount* (decimal > 0), expense_date* (YYYY-MM-DD),
    description

``*`` required. Validation reuses ``ExpenseCreate`` itself, so the import
can never admit a row the API would reject. Caps: 1000 rows, 1 MiB.
"""

from __future__ import annotations

import csv
import io
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
    reader = csv.DictReader(io.StringIO(text))
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
            valid.append(ExpenseCreate.model_validate(data))
        except ValidationError as exc:
            first = exc.errors()[0]
            errors.append({"row": line_number, "message": f"{first['loc'][0]}: {first['msg']}"})
    return valid, errors, total


async def import_expenses(
    db: AsyncSession, clinic_id: UUID, user_id: UUID, rows: list[ExpenseCreate]
) -> list[Expense]:
    """Persist validated rows via the canonical create path."""
    created = []
    for row in rows:
        created.append(await ExpenseService.create_expense(db, clinic_id, row, user_id))
    return created
