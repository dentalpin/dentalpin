"""CSV patient import — parse, validate (dry-run), and commit.

Column contract (header row required; unknown columns ignored so exports
from other systems import without pre-cleaning):

    first_name*, last_name*, phone, email, date_of_birth (YYYY-MM-DD
    or DD/MM/YYYY), notes, do_not_contact (true/1/yes/sí | false/0/no/blank),
    national_id, national_id_type, billing_name, billing_tax_id

Delimiter is sniffed (`,` or `;`, comma fallback for Spanish Excel).
``*`` required. Validation reuses ``PatientCreate`` itself, so the import
can never admit a row the API would reject. Caps: 1000 rows, 1 MiB.
Duplicate detection flags rows matching an existing non-archived patient
(national_id, else email + date_of_birth); commit skips them unless
``allow_duplicates`` is set.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
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


def _parse_date(raw: str, row_number: int, field: str) -> date:
    value = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise CsvImportError(f"row {row_number}: {field} must be YYYY-MM-DD or DD/MM/YYYY")


def _parse_bool(raw: str, row_number: int) -> bool:
    value = raw.strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    raise CsvImportError(f"row {row_number}: do_not_contact must be true/false-like")


def validate_patient_csv(content: bytes) -> tuple[list[PatientCreate], list[dict], int, list[int]]:
    """Validate CSV bytes without writing anything.

    Returns ``(valid_rows, errors, total, lines)`` where errors are
    ``{"row": int, "message": str}`` (row = 1-based file line) and
    ``lines`` parallels ``valid_rows`` for duplicate mapping.
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

    valid: list[PatientCreate] = []
    lines: list[int] = []
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
                if field == "do_not_contact":
                    data[field] = _parse_bool(value, line_number)
                elif field == "date_of_birth":
                    data[field] = _parse_date(value, line_number, field)
                else:
                    data[field] = value
            valid.append(PatientCreate.model_validate(data))
            lines.append(line_number)
        except ValidationError as exc:
            first = exc.errors()[0]
            errors.append({"row": line_number, "message": f"{first['loc'][0]}: {first['msg']}"})
        except CsvImportError as exc:
            errors.append({"row": line_number, "message": str(exc)})
    return valid, errors, total, lines


async def find_duplicate_lines(
    db: AsyncSession, clinic_id: UUID, valid: list[PatientCreate], lines: list[int]
) -> list[dict]:
    """Flag rows matching an existing non-archived patient — or each other.

    Match key: national_id, else email + date_of_birth. Returns
    ``{"row", "patient_id", "matched_on"}`` per flagged row;
    intra-file repeats carry ``patient_id: null`` and
    ``matched_on: "same_file"``.
    """
    duplicates: list[dict] = []
    seen_ids: dict[str, int] = {}
    seen_emails: dict[tuple[str | None, object], int] = {}
    for row, line_number in zip(valid, lines):
        if row.national_id:
            if row.national_id in seen_ids:
                duplicates.append(
                    {
                        "row": line_number,
                        "patient_id": None,
                        "matched_on": "same_file",
                    }
                )
                continue
            seen_ids[row.national_id] = line_number
        elif row.email and row.date_of_birth:
            key = (row.email, row.date_of_birth)
            if key in seen_emails:
                duplicates.append(
                    {
                        "row": line_number,
                        "patient_id": None,
                        "matched_on": "same_file",
                    }
                )
                continue
            seen_emails[key] = line_number
        match: Patient | None = None
        matched_on = ""
        if row.national_id:
            match = (
                (
                    await db.execute(
                        select(Patient).where(
                            Patient.clinic_id == clinic_id,
                            Patient.national_id == row.national_id,
                            Patient.status != "archived",
                        )
                    )
                )
                .scalars()
                .first()
            )
            matched_on = "national_id"
        if match is None and row.email and row.date_of_birth:
            match = (
                (
                    await db.execute(
                        select(Patient).where(
                            Patient.clinic_id == clinic_id,
                            Patient.email == row.email,
                            Patient.date_of_birth == row.date_of_birth,
                            Patient.status != "archived",
                        )
                    )
                )
                .scalars()
                .first()
            )
            matched_on = "email+date_of_birth"
        if match is not None:
            duplicates.append(
                {"row": line_number, "patient_id": str(match.id), "matched_on": matched_on}
            )
    return duplicates


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
