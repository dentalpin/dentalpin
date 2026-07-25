#!/usr/bin/env python3
"""Seed the medications catalog (Phase 9 module) from a fixed list.

Usage:
    python scripts/seed_medications.py --clinic-id <uuid>
    python scripts/seed_medications.py                     # auto-detect if exactly one clinic exists

Idempotent: for each entry, checks for an existing medication with the
same (name, clinic_id) before inserting — safe to re-run.

Does NOT create or apply any migration and does NOT alter the schema.
All 56 entries below have real dose + unit values (no nulls), matching
the live NOT NULL schema — no placeholder/skip logic needed.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Running this file directly (``python scripts/seed_medications.py``) only
# puts scripts/ on sys.path, not the repo root where the `app` package
# lives. Add it explicitly so `from app....` imports below resolve
# regardless of cwd or how this is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.auth.models import Clinic
from app.core.plugins.loader import discover_modules
from app.database import async_session_maker
from app.modules.medications.models import Medication, MedicationForm, UnitType

MEDICATIONS: list[dict] = [
    {"name": "Primacaine Adrénalinée (1/100 000) Articaïne + Épinéphrine", "dose": 1.7, "unit": "ml", "form": "injection"},
    {"name": "Lignospan (2%) Lidocaïne + Épinéphrine", "dose": 1.7, "unit": "ml", "form": "injection"},
    {"name": "Xylocaïne (2%) Lidocaïne", "dose": 1.7, "unit": "ml", "form": "injection"},
    {"name": "Scandonest (2% Spéciale) Mépivacaïne + Épinéphrine", "dose": 1.7, "unit": "ml", "form": "injection"},
    {"name": "Scandonest (3% Sans Vasoconstricteur) Mépivacaïne", "dose": 1.7, "unit": "ml", "form": "injection"},
    {"name": "Marcaine (0.5%) Bupivacaïne", "dose": 1.7, "unit": "ml", "form": "injection"},
    {"name": "Hurricaine (20%) Benzocaïne", "dose": 20, "unit": "%", "form": "gel"},
    {"name": "Clamoxyl (500mg) Amoxicilline", "dose": 500, "unit": "mg", "form": "tablet"},
    {"name": "Clamoxyl (1g) Amoxicilline", "dose": 1000, "unit": "mg", "form": "tablet"},
    {"name": "Augmentin (1g/125mg) Amoxicilline + Acide clavulanique", "dose": 1000, "unit": "mg", "form": "tablet"},
    {"name": "Rovamycine (1.5 M.U.I) Spiramycine", "dose": 1500000, "unit": "UI", "form": "tablet"},
    {"name": "Rovamycine (3 M.U.I) Spiramycine", "dose": 3000000, "unit": "UI", "form": "tablet"},
    {"name": "Flagyl (500mg) Métronidazole", "dose": 500, "unit": "mg", "form": "tablet"},
    {"name": "Rodogyl (750 000 UI/125mg) Spiramycine + Métronidazole", "dose": 750000, "unit": "UI", "form": "tablet"},
    {"name": "Birodogyl (1.5 M.U.I/250mg) Spiramycine + Métronidazole", "dose": 1500000, "unit": "UI", "form": "tablet"},
    {"name": "Erythrocine (500mg) Érythromycine", "dose": 500, "unit": "mg", "form": "tablet"},
    {"name": "Zithromax (500mg) Azithromycine", "dose": 500, "unit": "mg", "form": "tablet"},
    {"name": "Zeclar (500mg) Clarithromycine", "dose": 500, "unit": "mg", "form": "tablet"},
    {"name": "Dalacine (300mg) Clindamycine", "dose": 300, "unit": "mg", "form": "capsule"},
    {"name": "Vibramycine (100mg) Doxycycline", "dose": 100, "unit": "mg", "form": "capsule"},
    {"name": "Doliprane (500mg) Paracétamol", "dose": 500, "unit": "mg", "form": "tablet"},
    {"name": "Doliprane (1000mg) Paracétamol", "dose": 1000, "unit": "mg", "form": "tablet"},
    {"name": "Acupan (20mg/2ml) Néfopam", "dose": 20, "unit": "mg", "form": "injection"},
    {"name": "Ixprim (37.5mg/325mg) Paracétamol + Tramadol", "dose": 37.5, "unit": "mg", "form": "tablet"},
    {"name": "Zaldiar (37.5mg/325mg) Paracétamol + Tramadol", "dose": 37.5, "unit": "mg", "form": "tablet"},
    {"name": "Dafalgan Codéine (500mg/30mg) Paracétamol + Codéine", "dose": 500, "unit": "mg", "form": "tablet"},
    {"name": "Tramal (50mg) Tramadol", "dose": 50, "unit": "mg", "form": "capsule"},
    {"name": "Brufen (400mg) Ibuprofène", "dose": 400, "unit": "mg", "form": "tablet"},
    {"name": "Brufen (600mg) Ibuprofène", "dose": 600, "unit": "mg", "form": "tablet"},
    {"name": "Profenid (100mg) Kétoprofène", "dose": 100, "unit": "mg", "form": "tablet"},
    {"name": "Bi-Profenid (150mg) Kétoprofène", "dose": 150, "unit": "mg", "form": "tablet"},
    {"name": "Nifluril (250mg) Acide niflumique", "dose": 250, "unit": "mg", "form": "capsule"},
    {"name": "Voltarene (50mg) Diclofénac", "dose": 50, "unit": "mg", "form": "tablet"},
    {"name": "Feldene (20mg) Piroxicam", "dose": 20, "unit": "mg", "form": "capsule"},
    {"name": "Naproxène (500mg) Naproxène", "dose": 500, "unit": "mg", "form": "tablet"},
    {"name": "Celebrex (200mg) Célécoxib", "dose": 200, "unit": "mg", "form": "capsule"},
    {"name": "Solupred (20mg) Prednisolone", "dose": 20, "unit": "mg", "form": "tablet"},
    {"name": "Cortancyl (20mg) Prednisone", "dose": 20, "unit": "mg", "form": "tablet"},
    {"name": "Dectancyl (0.5mg) Dexaméthasone", "dose": 0.5, "unit": "mg", "form": "tablet"},
    {"name": "Medrol (16mg) Méthylprednisolone", "dose": 16, "unit": "mg", "form": "tablet"},
    {"name": "Eludril Gé (0.1%) Chlorhexidine", "dose": 15, "unit": "ml", "form": "mouthwash"},
    {"name": "Prexidine (0.12%) Chlorhexidine", "dose": 15, "unit": "ml", "form": "mouthwash"},
    {"name": "Corsodyl (0.2%) Chlorhexidine", "dose": 10, "unit": "ml", "form": "mouthwash"},
    {"name": "Hextril (0.1%) Hétidine", "dose": 15, "unit": "ml", "form": "mouthwash"},
    {"name": "Betadine Bain de Bouche (10%) Povidone iodée", "dose": 15, "unit": "ml", "form": "mouthwash"},
    {"name": "Eau Oxygénée (10 Volumes) Peroxyde d'hydrogène", "dose": 15, "unit": "ml", "form": "mouthwash"},
    {"name": "Bicarbonate de sodium (1.4%) Bicarbonate de sodium", "dose": 15, "unit": "ml", "form": "mouthwash"},
    {"name": "Gel de chlorhexidine 1%", "dose": 1, "unit": "ml", "form": "gel"},
    {"name": "Exacyl (500mg) Acide tranexamique", "dose": 500, "unit": "mg", "form": "tablet"},
    {"name": "Spongel (Standard) Éponge de gélatine", "dose": 1, "unit": "other", "form": "other"},
    {"name": "Surgicel (Standard) Cellulose oxydée", "dose": 1, "unit": "other", "form": "other"},
    {"name": "Daktarin (2%) Miconazole", "dose": 2.5, "unit": "ml", "form": "gel"},
    {"name": "Mycostatine (100 000 UI/ml) Nystatine", "dose": 1, "unit": "ml", "form": "syrup"},
    {"name": "Fungizone (10%) Amphotéricine B", "dose": 1, "unit": "ml", "form": "other"},
    {"name": "Zovirax (200mg) Aciclovir", "dose": 200, "unit": "mg", "form": "tablet"},
    {"name": "Eugénol (topique)", "dose": 0.1, "unit": "ml", "form": "other"},
]


async def resolve_clinic_id(session, clinic_id_arg: str | None) -> UUID:
    if clinic_id_arg:
        try:
            clinic_id = UUID(clinic_id_arg)
        except ValueError:
            print(f"ERROR: '{clinic_id_arg}' is not a valid UUID.", file=sys.stderr)
            sys.exit(1)
        clinic = await session.get(Clinic, clinic_id)
        if clinic is None:
            print(f"ERROR: no clinic found with id {clinic_id}.", file=sys.stderr)
            sys.exit(1)
        return clinic_id

    result = await session.execute(select(Clinic.id))
    clinic_ids = [row[0] for row in result.all()]
    if len(clinic_ids) == 1:
        return clinic_ids[0]
    if not clinic_ids:
        print("ERROR: no clinics found in the database.", file=sys.stderr)
    else:
        print(
            f"ERROR: {len(clinic_ids)} clinics found — pass --clinic-id explicitly.",
            file=sys.stderr,
        )
    sys.exit(1)


async def seed(clinic_id: UUID) -> None:
    added = 0
    skipped_existing = 0
    async with async_session_maker() as session:
        for entry in MEDICATIONS:
            existing = await session.execute(
                select(Medication.id).where(
                    Medication.clinic_id == clinic_id,
                    Medication.name == entry["name"],
                )
            )
            if existing.scalar_one_or_none() is not None:
                skipped_existing += 1
                continue

            medication = Medication(
                clinic_id=clinic_id,
                name=entry["name"],
                dose=entry["dose"],
                unit=UnitType(entry["unit"]),
                form=MedicationForm(entry["form"]),
                is_prescribed=True,
            )
            session.add(medication)
            added += 1

        await session.commit()

    print(f"Medications added: {added} / {len(MEDICATIONS)}")
    if skipped_existing:
        print(f"(skipped {skipped_existing} already present for this clinic)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the medications catalog.")
    parser.add_argument(
        "--clinic-id",
        default=None,
        help="Clinic UUID. Auto-detected if omitted and exactly one clinic exists.",
    )
    args = parser.parse_args()

    # Import every module's models (Patient, etc.) before any query runs —
    # Clinic.relationship(back_populates="patients") is a string reference
    # that SQLAlchemy can only resolve if the target class has already been
    # imported somewhere. The running app does this at startup via
    # load_modules(); this script isn't the app, so it has to do it itself.
    discover_modules()

    async def run() -> None:
        async with async_session_maker() as session:
            clinic_id = await resolve_clinic_id(session, args.clinic_id)
        await seed(clinic_id)

    asyncio.run(run())


if __name__ == "__main__":
    main()
