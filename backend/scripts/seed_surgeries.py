#!/usr/bin/env python3
"""Seed medical_reference_surgery from the surgeries list extracted from
list.odt (2026-07 upload) — same source as the other reference lists, just
not seeded until the surgeries table existed. Idempotent, same pattern as
scripts/seed_uploaded_lists.py.

Usage:
    docker-compose exec -T backend python scripts/seed_surgeries.py
    docker-compose exec -T backend python scripts/seed_surgeries.py --clinic-id <uuid>
"""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select

# Same full model-import block as seed_uploaded_lists.py, for the same
# reason — Clinic's string-based relationship() references need every
# related class importable before any mapper is used. See that script's
# comment for the full explanation.
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
from app.modules.medical_reference.models import ReferenceSurgery

DATA_PATH = Path(__file__).parent / "seed_data" / "surgeries_2026_07.json"


async def resolve_clinic_id(session, explicit: str | None) -> UUID:
    if explicit:
        return UUID(explicit)
    result = await session.execute(select(Clinic.id))
    ids = [row[0] for row in result.all()]
    if len(ids) == 1:
        return ids[0]
    if len(ids) == 0:
        raise SystemExit("No clinics found in this database — nothing to seed against.")
    raise SystemExit(f"Found {len(ids)} clinics — pass --clinic-id explicitly. IDs: {ids}")


async def main(explicit_clinic_id: str | None) -> None:
    names = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    async with async_session_maker() as session:
        clinic_id = await resolve_clinic_id(session, explicit_clinic_id)
        print(f"Seeding against clinic {clinic_id}")

        existing_stmt = select(func.lower(ReferenceSurgery.name)).where(
            ReferenceSurgery.clinic_id == clinic_id
        )
        existing = {row[0] for row in (await session.execute(existing_stmt)).all()}

        added = 0
        for name in names:
            if name.lower() in existing:
                continue
            session.add(ReferenceSurgery(clinic_id=clinic_id, name=name))
            existing.add(name.lower())
            added += 1

        await session.commit()

    print(f"Surgeries added: {added} / {len(names)}")
    print("Done. Re-running this script is safe — it only inserts what's missing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clinic-id", default=None)
    args = parser.parse_args()
    asyncio.run(main(args.clinic_id))
