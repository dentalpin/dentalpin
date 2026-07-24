#!/usr/bin/env python3
"""Seed medical_reference lists + inventory items from the clinic's uploaded lists.

Sources (2026-07 upload), bundled into seed_data/uploaded_lists_2026_07.json:
    - Allergies (19)              — from list.odt, "Most Common Allergies in Dentistry"
    - APCI diseases (24)          — from listeapci.pdf, official APCI list, is_apci=True
    - General diseases (32)       — from list.odt, "Most Common Systemic Diseases", is_apci=False
    - Medications (133)           — from medic_.json, dental + common comorbidity meds
    - Inventory items (213)       — from Inventaire_Dentaire_18_07_2026.xlsx

Idempotent: every insert checks for an existing row (case-insensitive name
match) first, so this is safe to re-run — reruns only add what's missing,
never duplicate.

Inventory categories were auto-assigned by a simple keyword heuristic
(gants/champs/masques -> ppe; anesthesia-related -> medication; everything
else -> consumables). This is a rough first pass — recategorize freely in
Settings afterwards, it doesn't affect quantity/threshold data.

Usage:
    docker-compose exec -T backend python scripts/seed_uploaded_lists.py
    docker-compose exec -T backend python scripts/seed_uploaded_lists.py --clinic-id <uuid>

If your instance has exactly one clinic (the normal case for a self-hosted
single-clinic install), --clinic-id is optional — it's auto-detected.
"""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select

# Every one of these imports is required even though most classes are never
# referenced directly below. SQLAlchemy's declarative registry resolves
# relationship() string references (e.g. Clinic -> "Patient") lazily, the
# first time any mapper is used — so if a related class was never imported
# into the process, that lookup fails with a bare KeyError/InvalidRequestError
# at query time, regardless of which specific query triggered it. This is
# the exact same problem alembic/env.py solves the same way — this block is
# a direct copy of its import list, not a new pattern.
from app.core.agents.models import (  # noqa: F401
    Agent,
    AgentApprovalQueue,
    AgentAuditLog,
    AgentSession,
)
from app.core.auth.models import Clinic, ClinicMembership, User  # noqa: F401
from app.core.plugins.db_models import (  # noqa: F401
    ExternalId,
    ModuleOperationLog,
    ModuleRecord,
)
from app.modules.agenda.models import Appointment, AppointmentTreatment, Cabinet  # noqa: F401
from app.modules.billing.models import (  # noqa: F401
    Invoice,
    InvoiceHistory,
    InvoiceItem,
    InvoicePayment,
    InvoiceSeries,
    InvoiceSeriesHistory,
)
from app.modules.budget.models import (  # noqa: F401
    Budget,
    BudgetHistory,
    BudgetItem,
    BudgetSignature,
)
from app.modules.catalog.models import (  # noqa: F401
    TreatmentCatalogItem,
    TreatmentCategory,
    TreatmentOdontogramMapping,
    VatType,
)
from app.modules.media.models import Document, MediaAttachment  # noqa: F401
from app.modules.notifications.models import (  # noqa: F401
    ClinicChannelSettings,
    ClinicNotificationSettings,
    ClinicSmtpSettings,
    CommunicationMessage,
    NotificationPreference,
    NotificationTemplate,
)
from app.modules.odontogram.models import (  # noqa: F401
    OdontogramHistory,
    ToothRecord,
    Treatment,
    TreatmentTooth,
)
from app.modules.patient_timeline.models import PatientTimeline  # noqa: F401
from app.modules.patients.models import Patient  # noqa: F401
from app.modules.patients_clinical.models import (  # noqa: F401
    Allergy,
    EmergencyContact,
    LegalGuardian,
    MedicalContext,
    Medication,
    SurgicalHistory,
    SystemicDisease,
)
from app.modules.payments.models import (  # noqa: F401
    PatientEarnedEntry,
    Payment,
    PaymentAllocation,
    PaymentHistory,
    Refund,
)
from app.modules.recalls.models import (  # noqa: F401
    Recall,
    RecallContactAttempt,
    RecallSettings,
)
from app.modules.schedules.models import (  # noqa: F401
    ClinicOverride,
    ClinicWeeklySchedule,
    ProfessionalOverride,
    ProfessionalWeeklySchedule,
    ScheduleShift,
)
from app.modules.treatment_plan.models import (  # noqa: F401
    PlannedTreatmentItem,
    TreatmentPlan,
)
from app.modules.whatsapp_kapso.models import (  # noqa: F401
    WhatsappKapsoSettings,
    WhatsappKapsoTemplate,
)

from app.database import async_session_maker
from app.modules.inventory.models import InventoryItem
from app.modules.medical_reference.models import (
    ReferenceAllergy,
    ReferenceDisease,
    ReferenceMedication,
)

DATA_PATH = Path(__file__).parent / "seed_data" / "uploaded_lists_2026_07.json"


async def resolve_clinic_id(session, explicit: str | None) -> UUID:
    if explicit:
        return UUID(explicit)
    result = await session.execute(select(Clinic.id))
    ids = [row[0] for row in result.all()]
    if len(ids) == 1:
        return ids[0]
    if len(ids) == 0:
        raise SystemExit("No clinics found in this database — nothing to seed against.")
    raise SystemExit(
        f"Found {len(ids)} clinics — pass --clinic-id explicitly. IDs: {ids}"
    )


async def seed_lookup_table(session, model, clinic_id: UUID, names: list[str], **extra_fields) -> int:
    """Insert whichever names don't already exist (case-insensitive) for this clinic."""
    existing_stmt = select(func.lower(model.name)).where(model.clinic_id == clinic_id)
    existing = {row[0] for row in (await session.execute(existing_stmt)).all()}

    added = 0
    for name in names:
        if name.lower() in existing:
            continue
        session.add(model(clinic_id=clinic_id, name=name, **extra_fields))
        existing.add(name.lower())  # guard against dupes within the same source list
        added += 1
    return added


async def seed_inventory(session, clinic_id: UUID, items: list[dict]) -> int:
    existing_stmt = select(func.lower(InventoryItem.name)).where(InventoryItem.clinic_id == clinic_id)
    existing = {row[0] for row in (await session.execute(existing_stmt)).all()}

    added = 0
    for item in items:
        if item["name"].lower() in existing:
            continue
        session.add(
            InventoryItem(
                clinic_id=clinic_id,
                name=item["name"],
                category=item["category"],
                quantity_on_hand=item["quantity_on_hand"],
                low_stock_threshold=item["low_stock_threshold"],
            )
        )
        existing.add(item["name"].lower())
        added += 1
    return added


async def main(explicit_clinic_id: str | None) -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    async with async_session_maker() as session:
        clinic_id = await resolve_clinic_id(session, explicit_clinic_id)
        print(f"Seeding against clinic {clinic_id}")

        n_allergies = await seed_lookup_table(session, ReferenceAllergy, clinic_id, data["allergies"])
        n_apci = await seed_lookup_table(
            session, ReferenceDisease, clinic_id, data["apci_diseases"], is_apci=True
        )
        n_general = await seed_lookup_table(
            session, ReferenceDisease, clinic_id, data["general_diseases"], is_apci=False
        )
        n_meds = await seed_lookup_table(session, ReferenceMedication, clinic_id, data["medications"])
        n_inventory = await seed_inventory(session, clinic_id, data["inventory_items"])

        await session.commit()

    print(f"Allergies added:        {n_allergies} / {len(data['allergies'])}")
    print(f"APCI diseases added:    {n_apci} / {len(data['apci_diseases'])}")
    print(f"General diseases added: {n_general} / {len(data['general_diseases'])}")
    print(f"Medications added:      {n_meds} / {len(data['medications'])}")
    print(f"Inventory items added:  {n_inventory} / {len(data['inventory_items'])}")
    print("Done. Re-running this script is safe — it only inserts what's missing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clinic-id", default=None, help="Clinic UUID (auto-detected if only one exists)")
    args = parser.parse_args()
    asyncio.run(main(args.clinic_id))
