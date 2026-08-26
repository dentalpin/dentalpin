"""Seed data for the medication catalog.

A 56-item dental medication list covering the drugs a dental clinic
actually stocks or prescribes: antibiotics, analgesics, local
anaesthetics, emergency kit, corticosteroids, antifungals/antivirals,
oral-care products and a small GI/allergy tail.

Idempotent: ``seed_medications`` skips entries whose (case-insensitive)
name already exists for the clinic, so it can run on every
``clinic.created``, on demand via ``POST /medication_catalog/seed``,
and after imports without ever duplicating rows.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import MedicationCatalogItem

# (name, dose, unit, form, requires_prescription)
DENTAL_MEDICATIONS: list[tuple[str, str | None, str | None, str, bool]] = [
    # --- Antibiotics -------------------------------------------------------
    # NOTE: same molecule at different strengths is entered as separate,
    # self-qualified names ("Metronidazole 250 mg" vs "... 500 mg")
    # because names are unique per clinic regardless of case.
    ("Amoxicillin 500 mg", "500", "mg", "capsule", True),
    ("Amoxicillin/Clavulanic acid 875/125 mg", "875/125", "mg", "tablet", True),
    ("Penicillin V 500 mg", "500", "mg", "tablet", True),
    ("Metronidazole 250 mg", "250", "mg", "tablet", True),
    ("Metronidazole 500 mg", "500", "mg", "tablet", True),
    ("Azithromycin 500 mg", "500", "mg", "tablet", True),
    ("Clarithromycin 500 mg", "500", "mg", "tablet", True),
    ("Clindamycin 300 mg", "300", "mg", "capsule", True),
    ("Cephalexin 500 mg", "500", "mg", "capsule", True),
    ("Doxycycline 100 mg", "100", "mg", "capsule", True),
    ("Ciprofloxacin 500 mg", "500", "mg", "tablet", True),
    ("Erythromycin 500 mg", "500", "mg", "tablet", True),
    # --- Analgesics --------------------------------------------------------
    ("Paracetamol 500 mg", "500", "mg", "tablet", False),
    ("Paracetamol 1 g", "1", "g", "tablet", False),
    ("Ibuprofen 400 mg", "400", "mg", "tablet", False),
    ("Ibuprofen 600 mg", "600", "mg", "tablet", True),
    ("Naproxen 250 mg", "250", "mg", "tablet", False),
    ("Diclofenac potassium 50 mg", "50", "mg", "tablet", True),
    ("Aceclofenac 100 mg", "100", "mg", "tablet", True),
    ("Ketorolac 10 mg", "10", "mg", "tablet", True),
    ("Tramadol 50 mg", "50", "mg", "capsule", True),
    ("Paracetamol/Codeine 500/30 mg", "500/30", "mg", "tablet", True),
    # --- Local anaesthetics -------------------------------------------------
    ("Lidocaine 2% + Epinephrine 1:100,000", None, None, "injection", True),
    ("Articaine 4% + Epinephrine 1:100,000", None, None, "injection", True),
    ("Mepivacaine 3%", None, None, "injection", True),
    ("Prilocaine 3%", None, None, "injection", True),
    ("Bupivacaine 0.5% + Epinephrine 1:200,000", None, None, "injection", True),
    ("Benzocaine 20%", None, None, "gel", False),
    # --- Emergency kit -------------------------------------------------------
    ("Adrenaline (Epinephrine)", "1", "mg/ml", "injection", True),
    ("Salbutamol", "100", "mcg/dose", "spray", True),
    ("Glyceryl trinitrate", "400", "mcg/dose", "spray", True),
    ("Aspirin", "300", "mg", "tablet", False),
    ("Glucose oral gel", "40", "%", "gel", False),
    ("Chlorphenamine", "10", "mg/ml", "injection", True),
    # --- Corticosteroids -----------------------------------------------------
    ("Dexamethasone", "4", "mg", "tablet", True),
    ("Prednisolone", "5", "mg", "tablet", True),
    ("Triamcinolone acetonide 0.1%", None, None, "paste", True),
    ("Hydrocortisone 1%", None, None, "cream", False),
    # --- Antifungal / antiviral ----------------------------------------------
    ("Miconazole oral gel 2%", None, None, "gel", True),
    ("Nystatin", "100000", "U/ml", "suspension", True),
    ("Fluconazole", "150", "mg", "capsule", True),
    ("Aciclovir", "200", "mg", "tablet", True),
    ("Aciclovir 5%", None, None, "cream", True),
    ("Valaciclovir", "500", "mg", "tablet", True),
    # --- Oral care -----------------------------------------------------------
    ("Chlorhexidine 0.2%", None, None, "mouthwash", False),
    ("Benzydamine 0.15%", None, None, "mouthwash", False),
    ("Sodium fluoride varnish 5%", None, None, "varnish", True),
    ("Potassium nitrate 5%", None, None, "gel", False),
    ("Carbamide peroxide 10%", None, None, "gel", False),
    ("Povidone-iodine 1%", None, None, "mouthwash", False),
    ("Sodium chloride 0.9%", None, None, "mouthwash", False),
    ("Hydrogen peroxide 1.5%", None, None, "mouthwash", False),
    # --- GI / allergy tail ----------------------------------------------------
    ("Omeprazole", "20", "mg", "capsule", False),
    ("Ondansetron", "4", "mg", "tablet", True),
    ("Loratadine", "10", "mg", "tablet", False),
    ("Diphenhydramine", "25", "mg", "capsule", False),
]

assert len(DENTAL_MEDICATIONS) == 56, len(DENTAL_MEDICATIONS)


async def seed_medications(db: AsyncSession, clinic_id: UUID) -> dict:
    """Seed the clinic's medication list. Idempotent: skips names that
    already exist (case-insensitively). Returns a created/skipped summary.
    """
    existing_rows = (
        (
            await db.execute(
                select(MedicationCatalogItem.name).where(
                    MedicationCatalogItem.clinic_id == clinic_id
                )
            )
        )
        .scalars()
        .all()
    )
    # column select yields plain strings
    existing = {(n or "").strip().lower() for n in existing_rows}

    created = skipped = 0
    for name, dose, unit, form, rx in DENTAL_MEDICATIONS:
        if name.strip().lower() in existing:
            skipped += 1
            continue
        db.add(
            MedicationCatalogItem(
                clinic_id=clinic_id,
                name=name,
                dose=dose,
                unit=unit,
                form=form,
                requires_prescription=rx,
                is_active=True,
            )
        )
        created += 1

    if created:
        await db.flush()
    return {"created": created, "skipped": skipped}
