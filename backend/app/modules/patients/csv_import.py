"""CSV patient import — parse, validate (dry-run), and commit.

Column contract (header row required; unknown columns ignored so exports
from other systems import without pre-cleaning):

    first_name*, last_name*, phone, email, date_of_birth (YYYY-MM-DD),
    notes, do_not_contact (true/1/yes/sí | false/0/no/blank),
    national_id, national_id_type, billing_name, billing_tax_id

``*`` required. Validation reuses ``PatientCreate`` itself, so the import
can never admit a row the API would reject. Caps: 1000 rows, 1 MiB.
"""

from __future__ import annotations

import csv
import io
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.patients.models import Patient

from .schemas import PatientCreate
from .service import PatientService

MAX_CSV_ROWS = 1000
MAX_CSV_BYTES = 1024 * 1024

REQUIRED_COLUMNS = ("first_name", "last_name")

# CSV header -> PatientCreate field. Unknown headers are ignored.
COLUMN_MAP = {
    "first_name": "first_name",
    "last_name": "last_name",
    "phone": "phone",
    "email": "email",
    "date_of_birth": "date_of_birth",
    "notes": "notes",
    "do_not_contact": "do_not_contact",
    "national_id": "national_id",
    "national_id_type": "national_id_type",
    "billing_name": "billing_name",
    "billing_tax_id": "billing_tax_id",
}

_TRUTHY = {"true", "1", "yes", "sí", "si", "y"}
_FALSY = {"false", "0", "no", "n", ""}


class CsvImportError(ValueError):
    """Whole-file rejection (encoding, header, caps). Maps to 422."""


def _parse_bool(raw: str, row_number: int) -> bool:
    value = raw.strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    raise CsvImportError(f"row {row_number}: do_not_contact must be true/false-like")


def validate_patient_csv(content: bytes) -> tuple[list[PatientCreate], list[dict], int]:
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

    valid: list[PatientCreate] = []
    errors: list[dict] = []
    total = 0
    for line_number, raw_row in enumerate(reader, start=2):
        if all((v or "").strip() == "" for v in raw_row.values()):
            continue  # skip blank lines
        total += 1
        if total > MAX_CSV_ROWS:
            raise CsvImportError(f"CSV exceeds {MAX_CSV_ROWS} rows")
        try:
            data: dict = {}
            for header in headers:
                if header not in COLUMN_MAP:
                    continue
                value = (raw_row.get(header) or "").strip()
                if value == "":
                    continue
                field = COLUMN_MAP[header]
                data[field] = (
                    _parse_bool(value, line_number) if field == "do_not_contact" else value
                )
            valid.append(PatientCreate.model_validate(data))
        except ValidationError as exc:
            first = exc.errors()[0]
            errors.append({"row": line_number, "message": f"{first['loc'][0]}: {first['msg']}"})
        except CsvImportError as exc:
            errors.append({"row": line_number, "message": str(exc)})
    return valid, errors, total


async def import_patients(
    db: AsyncSession, clinic_id: UUID, rows: list[PatientCreate]
) -> list[Patient]:
    """Persist validated rows via the canonical create path (events fire)."""
    created = []
    for row in rows:
        created.append(
            await PatientService.create_patient(db, clinic_id, row.model_dump(exclude_unset=True))
        )
    return created
