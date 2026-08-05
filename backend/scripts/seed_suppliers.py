"""One-time import of cleaned supplier data into `contacts`.

Run from inside the backend container:

    docker compose exec backend python3 scripts/seed_suppliers.py <clinic_id>

Uses raw SQL (not the Contact ORM model) — per this codebase's own
bug-prevention convention for seed scripts (avoid importing ORM models
with complex relationships). `Contact` itself is simple, but this
keeps the script dependency-free and safe to run without the full app
import graph.

Idempotent-ish: re-running with the same clinic_id will create
duplicate rows (there's no unique constraint on contacts.name to
upsert against) — check first if you're not sure whether it already
ran, e.g.:

    SELECT count(*) FROM contacts WHERE clinic_id = '<clinic_id>' AND contact_type = 'supplier';

Source data: 45 suppliers from a spreadsheet export. Two data-quality
notes baked into the cleanup (see suppliers_cleaned.csv):
  - the original "Address" column actually held a contact PERSON's
    name in most rows (e.g. "Anis Jallouli") rather than a street
    address — those went to `contact_person` here, filed into
    `notes`, NOT into `contacts.address`. Only rows with genuine
    street-address text (containing "Rue", "Route", "Résidence",
    "Boutique", or a number) were treated as a real address.
  - the original "PH1"/"PH2" columns were just labels ("Bureau" /
    "Portable 1/2"), not data — the real phone numbers were in
    "Contact 1"/"Contact 2". Since `contacts.phone` is a single field,
    only the primary number is stored there; a second number (when
    present) is appended to `notes` instead of dropped.
"""

import asyncio
import csv
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from app.database import async_session_maker

CSV_PATH = Path(__file__).parent.parent / "data" / "suppliers_cleaned.csv"


async def main(clinic_id: str) -> None:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    async with async_session_maker() as db:
        inserted = 0
        for row in rows:
            notes_parts = []
            if row["contact_person"]:
                notes_parts.append(f"Contact: {row['contact_person']}")
            if row["phone_secondary"]:
                notes_parts.append(f"Secondary phone: {row['phone_secondary']}")
            if row["notes"]:
                notes_parts.append(row["notes"])
            notes = " | ".join(notes_parts) or None

            await db.execute(
                text(
                    """
                    INSERT INTO contacts
                        (id, clinic_id, name, contact_type, phone, email, address, notes,
                         is_active, created_at, updated_at)
                    VALUES
                        (:id, :clinic_id, :name, 'supplier', :phone, NULL, :address, :notes,
                         true, now(), now())
                    """
                ),
                {
                    "id": str(uuid4()),
                    "clinic_id": clinic_id,
                    "name": row["name"],
                    "phone": row["phone"] or None,
                    "address": row["address"] or None,
                    "notes": notes,
                },
            )
            inserted += 1

        await db.commit()
        print(f"Inserted {inserted} supplier contacts for clinic {clinic_id}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/seed_suppliers.py <clinic_id>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
