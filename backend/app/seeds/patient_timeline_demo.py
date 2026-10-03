"""Demo data seed for the patient_timeline module.

Derives timeline rows from the already-seeded clinical/financial data —
appointments, treatment plans, tooth treatments, budgets, invoices — so
the ficha's "Actividad" tab has a realistic narrative out of the box.

Only invoked by ``backend/scripts/seed_demo.py`` and only when
``patient_timeline`` is installed in ``core_module``. Idempotent for the
given clinic: wipes the clinic's timeline rows, then repopulates.

Lives in the host seeds package, not inside the patient_timeline
module (#309): it reads models from five other modules to walk the
seeded narrative, and patient_timeline deliberately declares none of
them — its event sources are runtime-optional by design. Host-level
demo seeding is the established home for such cross-module fixtures
(see ``demo_data.py`` and the india_gst precedent).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.i18n_names import catalog_name
from app.modules.agenda.models import Appointment
from app.modules.billing.models import Invoice
from app.modules.budget.models import Budget
from app.modules.odontogram.models import Treatment
from app.modules.patient_timeline.models import PatientTimeline
from app.modules.treatment_plan.models import PlannedTreatmentItem, TreatmentPlan
from app.seeds.demo_data import t


async def seed_timeline_demo(db: AsyncSession, clinic_id: UUID) -> dict[str, int]:
    """Populate ``patient_timeline`` for the demo clinic.

    Returns a stats dict ``{"visit": n, "treatment": n, "financial": n}``
    consumed by the seed-demo summary.
    """
    await db.execute(delete(PatientTimeline).where(PatientTimeline.clinic_id == clinic_id))

    stats = {"visit": 0, "treatment": 0, "financial": 0}

    # --- Visits ----------------------------------------------------------
    appts = await db.execute(select(Appointment).where(Appointment.clinic_id == clinic_id))
    for appt in appts.scalars().all():
        if not appt.patient_id:
            continue

        title_map = {
            "scheduled": t(
                {
                    "es": "Cita programada",
                    "en": "Scheduled appointment",
                    "fr": "Rendez-vous planifié",
                    "ta": "திட்டமிடப்பட்ட சந்திப்பு",
                    "te": "షెడ్యూల్ చేసిన అపాయింట్‌మెంట్",
                }
            ),
            "confirmed": t(
                {
                    "es": "Cita programada",
                    "en": "Scheduled appointment",
                    "fr": "Rendez-vous planifié",
                    "ta": "திட்டமிடப்பட்ட சந்திப்பு",
                    "te": "షెడ్యూల్ చేసిన అపాయింట్‌మెంట్",
                }
            ),
            "completed": t(
                {
                    "es": "Cita completada",
                    "en": "Completed appointment",
                    "fr": "Rendez-vous terminé",
                    "ta": "முடிக்கப்பட்ட சந்திப்பு",
                    "te": "పూర్తయిన అపాయింట్‌మెంట్",
                }
            ),
            "cancelled": t(
                {
                    "es": "Cita cancelada",
                    "en": "Cancelled appointment",
                    "fr": "Rendez-vous annulé",
                    "ta": "ரத்து செய்யப்பட்ட சந்திப்பு",
                    "te": "రద్దయిన అపాయింట్‌మెంట్",
                }
            ),
            "no_show": t(
                {
                    "es": "Paciente no asistió",
                    "en": "Patient no-show",
                    "fr": "Patient absent",
                    "ta": "நோயாளர் வரவில்லை",
                    "te": "రోగి రాలేదు",
                }
            ),
        }
        title_es = title_map.get(
            appt.status,
            t(
                {
                    "es": "Cita",
                    "en": "Appointment",
                    "fr": "Rendez-vous",
                    "ta": "சந்திப்பு",
                    "te": "అపాయింట్‌మెంట్",
                }
            ),
        )
        treatment_label = appt.treatment_type or t(
            {
                "es": "Consulta",
                "en": "Consultation",
                "fr": "Consultation",
                "ta": "ஆலோசனை",
                "te": "సంప్రదింపు",
            }
        )
        occurred = appt.end_time if appt.status == "completed" else appt.start_time

        event_type_map = {
            "scheduled": "appointment.scheduled",
            "confirmed": "appointment.scheduled",
            "completed": "appointment.completed",
            "cancelled": "appointment.cancelled",
            "no_show": "appointment.no_show",
        }

        db.add(
            PatientTimeline(
                clinic_id=clinic_id,
                patient_id=appt.patient_id,
                event_type=event_type_map.get(appt.status, "appointment.scheduled"),
                event_category="visit",
                source_table="appointments",
                source_id=appt.id,
                title=f"{title_es}: {treatment_label}",
                description=None,
                event_data={
                    "cabinet": appt.cabinet,
                    "professional_id": str(appt.professional_id),
                },
                occurred_at=occurred,
            )
        )
        stats["visit"] += 1

    # --- Treatment plans -------------------------------------------------
    plans = await db.execute(select(TreatmentPlan).where(TreatmentPlan.clinic_id == clinic_id))
    for plan in plans.scalars().all():
        db.add(
            PatientTimeline(
                clinic_id=clinic_id,
                patient_id=plan.patient_id,
                event_type="treatment_plan.created",
                event_category="treatment",
                source_table="treatment_plans",
                source_id=plan.id,
                title=f"{t({'es': 'Plan de tratamiento creado', 'en': 'Treatment plan created', 'fr': 'Plan de traitement créé', 'ta': 'சிகிச்சைத் திட்டம் உருவாக்கப்பட்டது', 'te': 'చికిత్స ప్రణాళిక సృష్టించబడింది'})}: {plan.title or plan.plan_number}",
                event_data={"plan_number": plan.plan_number},
                occurred_at=plan.created_at or datetime.now(UTC),
                created_by=plan.created_by,
            )
        )
        stats["treatment"] += 1

    # --- Completed plan items --------------------------------------------
    completed_items = await db.execute(
        select(PlannedTreatmentItem)
        .options(
            selectinload(PlannedTreatmentItem.treatment).selectinload(Treatment.catalog_item),
        )
        .where(
            PlannedTreatmentItem.clinic_id == clinic_id,
            PlannedTreatmentItem.status == "completed",
        )
    )
    for item in completed_items.scalars().all():
        names = (
            item.treatment.catalog_item.names
            if item.treatment and item.treatment.catalog_item
            else {}
        ) or {}
        item_name = catalog_name(names) or t(
            {
                "es": "tratamiento",
                "en": "treatment",
                "fr": "traitement",
                "ta": "சிகிச்சை",
                "te": "చికిత్స",
            }
        )
        patient_id = item.treatment.patient_id if item.treatment else None
        if not patient_id:
            continue
        db.add(
            PatientTimeline(
                clinic_id=clinic_id,
                patient_id=patient_id,
                event_type="treatment_plan.treatment_completed",
                event_category="treatment",
                source_table="planned_treatment_items",
                source_id=item.id,
                title=f"{t({'es': 'Tratamiento del plan completado', 'en': 'Plan treatment completed', 'fr': 'Traitement du plan terminé', 'ta': 'திட்டத்தின் சிகிச்சை முடிக்கப்பட்டது', 'te': 'ప్రణాళికలోని చికిత్స పూర్తయింది'})}: {item_name}",
                event_data={"plan_id": str(item.treatment_plan_id)},
                occurred_at=item.completed_at or item.created_at or datetime.now(UTC),
                created_by=item.completed_by,
            )
        )
        stats["treatment"] += 1

    # --- Performed tooth treatments (odontogram) -------------------------
    performed = await db.execute(
        select(Treatment)
        .options(selectinload(Treatment.catalog_item), selectinload(Treatment.teeth))
        .where(Treatment.clinic_id == clinic_id, Treatment.status == "performed")
    )
    for treatment in performed.scalars().all():
        names = (treatment.catalog_item.names if treatment.catalog_item else {}) or {}
        name = (
            catalog_name(names)
            or treatment.clinical_type
            or t(
                {
                    "es": "tratamiento",
                    "en": "treatment",
                    "fr": "traitement",
                    "ta": "சிகிச்சை",
                    "te": "చికిత్స",
                }
            )
        )
        teeth = [t.tooth_number for t in treatment.teeth]
        teeth_label = ", ".join(str(t) for t in teeth) if teeth else None
        db.add(
            PatientTimeline(
                clinic_id=clinic_id,
                patient_id=treatment.patient_id,
                event_type="odontogram.treatment.performed",
                event_category="treatment",
                source_table="treatments",
                source_id=treatment.id,
                title=f"{t({'es': 'Tratamiento realizado', 'en': 'Treatment performed', 'fr': 'Traitement réalisé', 'ta': 'சிகிச்சை செய்யப்பட்டது', 'te': 'చికిత్స చేయబడింది'})}: {name}",
                description=f"{t({'es': 'Dientes', 'en': 'Teeth', 'fr': 'Dents', 'ta': 'வாய்ச்சிறுபிடிப்புகள்', 'te': 'దంతాలు'})}: {teeth_label}"
                if teeth_label
                else None,
                event_data={
                    "clinical_type": treatment.clinical_type,
                    "tooth_numbers": teeth,
                },
                occurred_at=treatment.performed_at or datetime.now(UTC),
                created_by=treatment.performed_by,
            )
        )
        stats["treatment"] += 1

    # --- Budgets ---------------------------------------------------------
    budgets = await db.execute(select(Budget).where(Budget.clinic_id == clinic_id))
    for budget in budgets.scalars().all():
        if budget.status in ("sent", "accepted", "completed"):
            db.add(
                PatientTimeline(
                    clinic_id=clinic_id,
                    patient_id=budget.patient_id,
                    event_type="budget.sent",
                    event_category="financial",
                    source_table="budgets",
                    source_id=budget.id,
                    title=f"{t({'es': 'Presupuesto enviado', 'en': 'Budget sent', 'fr': 'Devis envoyé', 'ta': 'மதிப்பீடு அனுப்பப்பட்டது', 'te': 'అంచనా పంపబడింది'})}: {budget.budget_number}",
                    event_data={
                        "budget_number": budget.budget_number,
                        "total": str(budget.total),
                    },
                    occurred_at=budget.updated_at or budget.created_at or datetime.now(UTC),
                )
            )
            stats["financial"] += 1
        if budget.status in ("accepted", "completed"):
            db.add(
                PatientTimeline(
                    clinic_id=clinic_id,
                    patient_id=budget.patient_id,
                    event_type="budget.accepted",
                    event_category="financial",
                    source_table="budgets",
                    source_id=budget.id,
                    title=f"{t({'es': 'Presupuesto aceptado', 'en': 'Budget accepted', 'fr': 'Devis accepté', 'ta': 'மதிப்பீடு ஏற்கப்பட்டது', 'te': 'అంచనా అంగీకరించబడింది'})}: {budget.budget_number}",
                    event_data={
                        "budget_number": budget.budget_number,
                        "total": str(budget.total),
                    },
                    occurred_at=budget.updated_at or budget.created_at or datetime.now(UTC),
                )
            )
            stats["financial"] += 1

    # --- Invoices --------------------------------------------------------
    invoices = await db.execute(select(Invoice).where(Invoice.clinic_id == clinic_id))
    for invoice in invoices.scalars().all():
        if invoice.status in ("issued", "partial", "paid"):
            db.add(
                PatientTimeline(
                    clinic_id=clinic_id,
                    patient_id=invoice.patient_id,
                    event_type="invoice.issued",
                    event_category="financial",
                    source_table="invoices",
                    source_id=invoice.id,
                    title=f"{t({'es': 'Factura emitida', 'en': 'Invoice issued', 'fr': 'Facture émise', 'ta': 'வாங்கப்பட்ட பில்', 'te': 'ఇన్‌వాయిస్ జారీ చేయబడింది'})}: {invoice.invoice_number or '—'}",
                    event_data={
                        "invoice_number": invoice.invoice_number,
                        "total": str(invoice.total),
                    },
                    occurred_at=(
                        datetime.combine(invoice.issue_date, datetime.min.time()).replace(
                            tzinfo=UTC
                        )
                        if invoice.issue_date
                        else (invoice.created_at or datetime.now(UTC))
                    ),
                )
            )
            stats["financial"] += 1
        if invoice.status == "paid":
            db.add(
                PatientTimeline(
                    clinic_id=clinic_id,
                    patient_id=invoice.patient_id,
                    event_type="invoice.paid",
                    event_category="financial",
                    source_table="invoices",
                    source_id=invoice.id,
                    title=f"{t({'es': 'Factura pagada', 'en': 'Invoice paid', 'fr': 'Facture payée', 'ta': 'வாங்கப்பட்ட பில் செலுத்தப்பட்டது', 'te': 'ఇన్‌వాయిస్ చెల్లించబడింది'})}: {invoice.invoice_number or '—'}",
                    event_data={
                        "invoice_number": invoice.invoice_number,
                        "total": str(invoice.total),
                    },
                    occurred_at=invoice.updated_at or invoice.created_at or datetime.now(UTC),
                )
            )
            stats["financial"] += 1

    await db.flush()
    return stats
