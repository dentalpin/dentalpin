#!/usr/bin/env python3
"""Seed script to populate DentalPin with demo data.

Creates the full clinical narrative for a demo clinic:
    patients → treatment plans → (budgets + appointments) → invoices

- 1 clinic with full configuration
- 5 users (admin, dentist, hygienist, assistant, receptionist)
- 15 patients of varied ages
- Odontogram data (tooth records + treatments per patient)
- Treatment catalog (categories + items)
- 15 treatment plans (one per patient)
- ~10 budgets derived from plan items (some draft, accepted+signed, rejected, completed)
- ~35 appointments anchored to plan items (no random appointments)
- 2 invoice series + ~8 invoices derived from budgets, with payments

Usage:
    docker-compose exec -T backend python scripts/seed_demo.py              # English
    docker-compose exec -T backend python scripts/seed_demo.py --lang es    # Spanish

All users have password: demo1234
"""

import argparse
import asyncio
from collections import Counter

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.database import async_session_maker
from app.modules.agenda.models import Appointment, AppointmentTreatment
from app.modules.billing.models import Invoice, InvoiceItem, InvoicePayment, InvoiceSeries
from app.modules.budget.models import Budget, BudgetItem, BudgetSignature
from app.modules.catalog.models import TreatmentCatalogItem
from app.modules.catalog.seed import seed_catalog
from app.modules.clinical_notes.seed import seed_clinical_notes_demo
from app.modules.media.models import Document  # noqa: F401 - needed for relationship resolution
from app.modules.odontogram.models import ToothRecord, Treatment, TreatmentTooth
from app.modules.patient_timeline.models import (
    PatientTimeline,  # noqa: F401 - relationship resolution
)
from app.modules.patients.models import Patient
from app.modules.patients_clinical.models import (
    Allergy,
    EmergencyContact,
    LegalGuardian,
    MedicalContext,
    Medication,
    SurgicalHistory,
    SystemicDisease,
)
from app.modules.payments.models import PatientEarnedEntry, Payment, PaymentAllocation
from app.modules.treatment_plan.models import (
    PlannedTreatmentItem,
    PlannedTreatmentItemSession,
    TreatmentPlan,
)
from app.seeds.demo_data import (
    CLINIC_ID,
    USER_DENTIST_ID,
    USER_HYGIENIST_ID,
    USER_RECEPTIONIST_ID,
    generate_appointments_data,
    generate_budgets_data,
    generate_invoice_series_data,
    generate_invoices_data,
    generate_odontogram_data,
    generate_treatment_plans_data,
    get_clinic_data,
    get_patients_data,
    get_users_data,
    set_language,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def check_existing_data(db: AsyncSession) -> bool:
    """Check if demo data already exists."""
    result = await db.execute(select(Clinic).where(Clinic.id == CLINIC_ID))
    return result.scalar_one_or_none() is not None


async def _module_is_installed(db: AsyncSession, name: str) -> bool:
    """True when ``core_module`` has the module in the ``installed`` state.

    Optional-module seeds gate themselves on this so uninstalling a
    module also silently skips its demo data on re-seed.
    """
    from app.core.plugins.db_models import ModuleRecord
    from app.core.plugins.state import ModuleState

    result = await db.execute(select(ModuleRecord).where(ModuleRecord.name == name))
    record = result.scalar_one_or_none()
    return record is not None and record.state == ModuleState.INSTALLED.value


async def _load_catalog_map(db: AsyncSession) -> dict[str, dict]:
    """Load catalog items into a single map consumed by all journey generators.

    Each value carries everything the generators need — default_price, VAT info
    and the odontogram_treatment_type — so the map is built once per seed run.
    """
    result = await db.execute(
        select(TreatmentCatalogItem)
        .options(
            selectinload(TreatmentCatalogItem.vat_type_rel),
            selectinload(TreatmentCatalogItem.odontogram_mapping),
            selectinload(TreatmentCatalogItem.sessions),
        )
        .where(TreatmentCatalogItem.clinic_id == CLINIC_ID)
    )
    mapping: dict[str, dict] = {}
    for item in result.scalars():
        vat_rate = item.vat_type_rel.rate if item.vat_type_rel else 0.0
        odontogram_type = (
            item.odontogram_mapping.odontogram_treatment_type if item.odontogram_mapping else None
        )
        sessions = sorted(
            (
                {
                    "sequence": s.sequence,
                    "labels": dict(s.labels or {}),
                    "default_price": s.default_price,
                }
                for s in (item.sessions or [])
            ),
            key=lambda s: s["sequence"],
        )
        mapping[item.internal_code] = {
            "id": item.id,
            "default_price": item.default_price,
            "vat_type_id": item.vat_type_id,
            "vat_rate": rate_or_zero(vat_rate),
            "odontogram_treatment_type": odontogram_type,
            "sessions": sessions,
        }
    return mapping


def rate_or_zero(rate) -> float:
    return float(rate) if rate is not None else 0.0


def _print_status_counts(header: str, rows: list[dict], status_key: str = "status") -> None:
    counts = Counter(r[status_key] for r in rows)
    print(header)
    for status, count in sorted(counts.items()):
        print(f"    - {status}: {count}")


# ---------------------------------------------------------------------------
# Entity creators (mirror the clinical workflow order)
# ---------------------------------------------------------------------------


async def seed_clinic(db: AsyncSession) -> Clinic:
    """Create the demo clinic + its cabinets."""
    from uuid import uuid4

    from app.modules.agenda.models import Cabinet

    clinic_data = get_clinic_data()
    clinic = Clinic(
        id=clinic_data["id"],
        name=clinic_data["name"],
        tax_id=clinic_data["tax_id"],
        address=clinic_data["address"],
        phone=clinic_data["phone"],
        email=clinic_data["email"],
        timezone=clinic_data["timezone"],
        currency=clinic_data["currency"],
        settings=clinic_data["settings"],
    )
    db.add(clinic)
    await db.flush()

    for order, cab in enumerate(clinic_data.get("cabinets") or []):
        db.add(
            Cabinet(
                id=uuid4(),
                clinic_id=clinic.id,
                name=cab["name"],
                color=cab["color"],
                display_order=order,
                is_active=True,
            )
        )
    await db.flush()

    print(f"  Created clinic: {clinic.name}")
    return clinic


async def seed_users(db: AsyncSession, password_hash: str) -> list[User]:
    """Create demo users with their clinic memberships."""
    users: list[User] = []
    for user_data in get_users_data():
        user = User(
            id=user_data["id"],
            email=user_data["email"],
            password_hash=password_hash,
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            professional_id=user_data.get("professional_id"),
            is_active=True,
            token_version=0,
        )
        db.add(user)
        users.append(user)

        db.add(
            ClinicMembership(
                id=user_data["membership_id"],
                user_id=user_data["id"],
                clinic_id=CLINIC_ID,
                role=user_data["role"],
            )
        )
        print(f"  Created user: {user.email} ({user_data['role']})")

    await db.flush()
    return users


async def seed_patients(db: AsyncSession) -> list[Patient]:
    """Create demo patients + their normalized clinical rows."""
    patients: list[Patient] = []
    for patient_data in get_patients_data():
        patient = Patient(
            id=patient_data["id"],
            clinic_id=CLINIC_ID,
            first_name=patient_data["first_name"],
            last_name=patient_data["last_name"],
            phone=patient_data["phone"],
            email=patient_data["email"],
            date_of_birth=patient_data["date_of_birth"],
            notes=patient_data["notes"],
            status="active",
        )
        db.add(patient)
        patients.append(patient)

        _seed_patient_clinical(db, patient_data)

    await db.flush()
    print(f"  Created {len(patients)} patients (+ normalized clinical rows)")
    return patients


_MEDICAL_CONTEXT_KEYS = (
    "is_pregnant",
    "pregnancy_week",
    "is_lactating",
    "is_on_anticoagulants",
    "anticoagulant_medication",
    "inr_value",
    "last_inr_date",
    "is_smoker",
    "smoking_frequency",
    "alcohol_consumption",
    "bruxism",
    "adverse_reactions_to_anesthesia",
    "anesthesia_reaction_details",
)


def _seed_patient_clinical(db: AsyncSession, patient_data: dict) -> None:
    """Fan out the legacy-shaped ``medical_history`` + ``emergency_contact``
    blobs into the normalized patients_clinical tables."""
    patient_id = patient_data["id"]

    ec = patient_data.get("emergency_contact")
    if ec and ec.get("name") and ec.get("phone"):
        db.add(
            EmergencyContact(
                patient_id=patient_id,
                clinic_id=CLINIC_ID,
                name=ec["name"],
                relationship=ec.get("relationship"),
                phone=ec["phone"],
                email=ec.get("email"),
                is_legal_guardian=bool(ec.get("is_legal_guardian", False)),
            )
        )

    lg = patient_data.get("legal_guardian")
    if lg and lg.get("name") and lg.get("relationship") and lg.get("phone"):
        db.add(
            LegalGuardian(
                patient_id=patient_id,
                clinic_id=CLINIC_ID,
                name=lg["name"],
                relationship=lg["relationship"],
                dni=lg.get("dni"),
                phone=lg["phone"],
                email=lg.get("email"),
                address=lg.get("address"),
                notes=lg.get("notes"),
            )
        )

    mh = patient_data.get("medical_history") or {}
    if not mh:
        return

    for allergy in mh.get("allergies") or []:
        db.add(
            Allergy(
                patient_id=patient_id,
                clinic_id=CLINIC_ID,
                name=allergy.get("name") or "Desconocida",
                type=allergy.get("type"),
                severity=allergy.get("severity") or "medium",
                reaction=allergy.get("reaction"),
                notes=allergy.get("notes"),
            )
        )

    for med in mh.get("medications") or []:
        db.add(
            Medication(
                patient_id=patient_id,
                clinic_id=CLINIC_ID,
                name=med.get("name") or "Desconocido",
                dosage=med.get("dosage"),
                frequency=med.get("frequency"),
                start_date=med.get("start_date"),
                notes=med.get("notes"),
            )
        )

    for disease in mh.get("systemic_diseases") or []:
        db.add(
            SystemicDisease(
                patient_id=patient_id,
                clinic_id=CLINIC_ID,
                name=disease.get("name") or "Desconocida",
                type=disease.get("type"),
                diagnosis_date=disease.get("diagnosis_date"),
                is_controlled=bool(disease.get("is_controlled", True)),
                is_critical=bool(disease.get("is_critical", False)),
                medications=disease.get("medications"),
                notes=disease.get("notes"),
            )
        )

    for surgery in mh.get("surgical_history") or []:
        db.add(
            SurgicalHistory(
                patient_id=patient_id,
                clinic_id=CLINIC_ID,
                procedure=surgery.get("procedure") or "Sin especificar",
                surgery_date=surgery.get("surgery_date"),
                complications=surgery.get("complications"),
                notes=surgery.get("notes"),
            )
        )

    context_data = {k: mh[k] for k in _MEDICAL_CONTEXT_KEYS if k in mh}
    if context_data:
        db.add(
            MedicalContext(
                patient_id=patient_id,
                clinic_id=CLINIC_ID,
                **context_data,
            )
        )


async def seed_odontogram(db: AsyncSession) -> dict:
    """Create demo odontogram data (tooth records + treatments + treatment_teeth)."""
    data = generate_odontogram_data()

    for record_data in data["tooth_records"]:
        db.add(ToothRecord(**record_data))
    await db.flush()

    for t_data in data["treatments"]:
        db.add(Treatment(**t_data))
    await db.flush()

    for tt in data["treatment_teeth"]:
        db.add(TreatmentTooth(**tt))
    await db.flush()

    patient_ids = {r["patient_id"] for r in data["tooth_records"]}
    performed = sum(1 for t in data["treatments"] if t["status"] == "performed")
    planned = sum(1 for t in data["treatments"] if t["status"] == "planned")

    print(f"  Created {len(data['tooth_records'])} tooth records for {len(patient_ids)} patients")
    print(f"  Created {len(data['treatments'])} treatments:")
    print(f"    - performed: {performed}")
    print(f"    - planned: {planned}")
    return {
        "tooth_records": len(data["tooth_records"]),
        "treatments": len(data["treatments"]),
        "patients": len(patient_ids),
    }


async def seed_treatment_plans(db: AsyncSession, catalog_map: dict) -> dict:
    """Create treatment plans + backing Treatments + planned items.

    Plans are inserted with budget_id=None; the link is wired by seed_budgets
    once the budgets exist.

    Also seeds the per-item ``PlannedTreatmentItemSession`` snapshot rows
    (always at least one per item) and the matching ``PatientEarnedEntry``
    rows for completed sessions so the patient "Pagos" tab shows the
    "Pendiente de cobrar" panel out of the box.
    """
    data = generate_treatment_plans_data(catalog_map)

    for plan_dict in data["plans"]:
        db.add(TreatmentPlan(**plan_dict))
    await db.flush()

    # Treatments backing each planned item must exist before PlannedTreatmentItem
    # can reference them (FK + unique constraint on treatment_id).
    for pt in data["plan_treatments"]:
        db.add(Treatment(**pt))
    await db.flush()

    for item_dict in data["items"]:
        db.add(PlannedTreatmentItem(**item_dict))
    await db.flush()

    for session_dict in data["item_sessions"]:
        db.add(PlannedTreatmentItemSession(**session_dict))
    await db.flush()

    for earned_dict in data["earned_entries"]:
        db.add(PatientEarnedEntry(**earned_dict))
    await db.flush()

    _print_status_counts(f"  Created {len(data['plans'])} treatment plans:", data["plans"])
    print(f"  Created {len(data['items'])} planned items")
    print(f"  Created {len(data['item_sessions'])} planned-item sessions")
    print(f"  Created {len(data['earned_entries'])} earned-entry rows")
    return data


async def seed_budgets(db: AsyncSession, catalog_map: dict, plans_result: dict) -> dict:
    """Create budgets + items + signatures derived from plans, then wire plan→budget FK."""
    data = generate_budgets_data(catalog_map, plans_result)

    for budget_dict in data["budgets"]:
        db.add(Budget(**budget_dict))
    await db.flush()

    for item_dict in data["items"]:
        db.add(BudgetItem(**item_dict))
    await db.flush()

    for sig_dict in data["signatures"]:
        db.add(BudgetSignature(**sig_dict))
    await db.flush()

    # Wire TreatmentPlan.budget_id now that budgets exist.
    for plan_id, budget_id in data["plan_to_budget"].items():
        await db.execute(
            update(TreatmentPlan).where(TreatmentPlan.id == plan_id).values(budget_id=budget_id)
        )
    await db.flush()

    _print_status_counts(f"  Created {len(data['budgets'])} budgets:", data["budgets"])
    print(f"  Created {len(data['items'])} budget items")
    print(f"  Created {len(data['signatures'])} signatures")
    print(f"  Linked {len(data['plan_to_budget'])} plan(s) to budget(s)")
    return data


async def seed_appointments(db: AsyncSession, plans_result: dict) -> dict:
    """Create appointments anchored to plan items + their AppointmentTreatment rows."""
    from sqlalchemy import select

    from app.modules.agenda.models import AppointmentStatusEvent, Cabinet

    data = generate_appointments_data(plans_result)

    # Resolve cabinet_id from the cabinet name for every appointment.
    result = await db.execute(select(Cabinet))
    cab_by_name = {(c.clinic_id, c.name): c.id for c in result.scalars().all()}

    for appt_dict in data["appointments"]:
        key = (appt_dict["clinic_id"], appt_dict["cabinet"])
        cab_id = cab_by_name.get(key)
        if cab_id is None:
            raise RuntimeError(f"Demo seed: cabinet {key} not found")
        appt_dict["cabinet_id"] = cab_id
        appt_dict.setdefault("current_status_since", appt_dict["start_time"])
        db.add(Appointment(**appt_dict))
    await db.flush()

    # Seed the synthetic initial status event for each appointment so
    # analytics have a complete audit trail from the start. For appointments
    # already past ``scheduled`` we also emit a second event so the timeline
    # captures *that* the transition happened, even though intermediate
    # steps are unknown for seeded rows.
    for appt_dict in data["appointments"]:
        db.add(
            AppointmentStatusEvent(
                clinic_id=appt_dict["clinic_id"],
                appointment_id=appt_dict["id"],
                from_status=None,
                to_status="scheduled",
                changed_at=appt_dict["start_time"],
                changed_by=None,
            )
        )
        if appt_dict.get("status") and appt_dict["status"] != "scheduled":
            db.add(
                AppointmentStatusEvent(
                    clinic_id=appt_dict["clinic_id"],
                    appointment_id=appt_dict["id"],
                    from_status="scheduled",
                    to_status=appt_dict["status"],
                    changed_at=appt_dict["start_time"],
                    changed_by=None,
                )
            )
    await db.flush()

    for at_dict in data["appointment_treatments"]:
        db.add(AppointmentTreatment(**at_dict))
    await db.flush()

    _print_status_counts(
        f"  Created {len(data['appointments'])} appointments:", data["appointments"]
    )
    print(f"  Linked {len(data['appointment_treatments'])} appointment treatments")
    return data


async def seed_invoice_series(db: AsyncSession) -> int:
    """Create demo invoice series."""
    series_data = generate_invoice_series_data()
    for series_dict in series_data:
        db.add(InvoiceSeries(**series_dict))
    await db.flush()
    print(f"  Created {len(series_data)} invoice series")
    return len(series_data)


async def seed_invoices(db: AsyncSession, catalog_map: dict, budgets_result: dict) -> dict:
    """Create invoices derived from budgets and update BudgetItem.invoiced_quantity."""
    data = generate_invoices_data(catalog_map, budgets_result)

    for invoice_dict in data["invoices"]:
        db.add(Invoice(**invoice_dict))
    await db.flush()

    for item_dict in data["items"]:
        db.add(InvoiceItem(**item_dict))
    await db.flush()

    for payment_dict in data["payments"]:
        db.add(Payment(**payment_dict))
    await db.flush()

    for alloc_dict in data["payment_allocations"]:
        db.add(PaymentAllocation(**alloc_dict))
    await db.flush()

    for invpay_dict in data["invoice_payments"]:
        db.add(InvoicePayment(**invpay_dict))
    await db.flush()

    for budget_item_id, qty in data["invoiced_quantity_by_budget_item"].items():
        await db.execute(
            update(BudgetItem).where(BudgetItem.id == budget_item_id).values(invoiced_quantity=qty)
        )
    await db.flush()

    _print_status_counts(f"  Created {len(data['invoices'])} invoices:", data["invoices"])
    print(f"  Created {len(data['items'])} invoice items")
    print(f"  Created {len(data['payments'])} payments")
    print(f"  Created {len(data['payment_allocations'])} payment allocations")
    print(f"  Created {len(data['invoice_payments'])} invoice payments")
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Seed DentalPin with demo data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/seed_demo.py              # Default (English)
  python scripts/seed_demo.py --lang es    # Spanish
  python scripts/seed_demo.py --lang en    # English (explicit)
  python scripts/seed_demo.py --lang fr    # French
        """,
    )
    parser.add_argument(
        "--lang",
        "-l",
        choices=["en", "es", "fr"],
        default="en",
        help="Language for demo data (default: en)",
    )
    return parser.parse_args()


async def main(lang: str = "en") -> None:
    """Seed the full demo clinical workflow."""
    set_language(lang)
    lang_names = {"en": "English", "es": "Spanish", "fr": "French"}
    lang_name = lang_names.get(lang, lang)

    print("\n" + "=" * 60)
    print(f"DentalPin Demo Data Seeder ({lang_name})")
    print("=" * 60 + "\n")

    async with async_session_maker() as db:
        if await check_existing_data(db):
            print("Demo data already exists!")
            print("To reset, run: ./scripts/reset-db.sh")
            print("Then run this script again.\n")
            return

        print("Creating demo data...\n")

        password_hash = hash_password("demo1234")

        try:
            print("[1/10] Creating clinic...")
            await seed_clinic(db)

            print("\n[2/10] Creating users...")
            await seed_users(db, password_hash)

            print("\n[3/10] Creating patients...")
            await seed_patients(db)

            print("\n[4/10] Creating treatment catalog...")
            catalog_result = await seed_catalog(db, CLINIC_ID)
            print(f"  Created {catalog_result['categories']} categories")
            print(f"  Created {catalog_result['items']} catalog items")
            catalog_map = await _load_catalog_map(db)

            print("\n[5/10] Creating odontogram data...")
            await seed_odontogram(db)

            print("\n[6/10] Creating treatment plans...")
            plans_result = await seed_treatment_plans(db, catalog_map)

            print("\n[7/10] Creating clinical notes (admin/diagnosis/plan/treatment)...")
            notes_stats = await seed_clinical_notes_demo(
                db,
                clinic_id=CLINIC_ID,
                dentist_id=USER_DENTIST_ID,
                hygienist_id=USER_HYGIENIST_ID,
            )
            print(
                f"  Administrative: {notes_stats['administrative']} | "
                f"Diagnosis: {notes_stats['diagnosis']} | "
                f"Plan: {notes_stats['treatment_plan']} | "
                f"Treatment: {notes_stats['treatment']}"
            )

            print("\n[8/10] Creating budgets (derived from plans)...")
            budgets_result = await seed_budgets(db, catalog_map, plans_result)

            print("\n[9/10] Creating appointments (anchored to plan items)...")
            await seed_appointments(db, plans_result)

            print("\n[10/10] Creating invoice series + invoices (derived from budgets)...")
            await seed_invoice_series(db)
            await seed_invoices(db, catalog_map, budgets_result)

            # Optional modules — only seed when installed. Looked up by
            # name in ``core_module`` so a future ``dentalpin modules
            # uninstall schedules`` cleanly skips this step.
            if await _module_is_installed(db, "schedules"):
                print("\n[opt] Creating schedules demo (module installed)...")
                from app.modules.schedules.seed import seed_schedules_demo

                stats = await seed_schedules_demo(
                    db,
                    clinic_id=CLINIC_ID,
                    dentist_id=USER_DENTIST_ID,
                    hygienist_id=USER_HYGIENIST_ID,
                )
                print(
                    f"  Clinic shifts: {stats['clinic_shifts']} | "
                    f"Professional shifts: {stats['professional_shifts']} | "
                    f"Overrides: {stats['overrides']}"
                )

            if await _module_is_installed(db, "patient_timeline"):
                print("\n[opt] Creating patient timeline demo (module installed)...")
                from app.modules.patient_timeline.seed import seed_timeline_demo

                stats = await seed_timeline_demo(db, clinic_id=CLINIC_ID)
                print(
                    f"  Visits: {stats['visit']} | "
                    f"Treatments: {stats['treatment']} | "
                    f"Financial: {stats['financial']}"
                )

            if await _module_is_installed(db, "recalls"):
                print("\n[opt] Creating recalls demo (module installed)...")
                from app.modules.recalls.seed import seed_recalls_demo

                stats = await seed_recalls_demo(
                    db,
                    clinic_id=CLINIC_ID,
                    dentist_id=USER_DENTIST_ID,
                    hygienist_id=USER_HYGIENIST_ID,
                    receptionist_id=USER_RECEPTIONIST_ID,
                )
                print(
                    f"  Total: {stats['total']} | "
                    f"Pending: {stats['pending']} | "
                    f"No answer: {stats['contacted_no_answer']} | "
                    f"Scheduled: {stats['contacted_scheduled']} | "
                    f"Done: {stats['done']} | "
                    f"Needs review: {stats['needs_review']} | "
                    f"Attempts logged: {stats['attempts']}"
                )

            await db.commit()
            print("\n" + "=" * 60)
            print("Demo data created successfully!")
            print("=" * 60)

        except Exception as e:
            await db.rollback()
            print(f"\nError creating demo data: {e}")
            raise

    users_data = get_users_data()
    print("\n" + "-" * 60)
    print("DEMO CREDENTIALS (all passwords: demo1234)")
    print("-" * 60)
    print(f"{'Email':<30} {'Role':<15} {'Name'}")
    print("-" * 60)
    for user in users_data:
        print(f"{user['email']:<30} {user['role']:<15} {user['first_name']} {user['last_name']}")
    print("-" * 60)
    print("\nOpen http://localhost:3000 to access the application.\n")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(lang=args.lang))
