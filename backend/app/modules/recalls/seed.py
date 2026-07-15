"""Demo seed for the recalls module.

Generates a realistic monthly call list across the seeded patients:
mix of statuses (pending / no answer / scheduled / done / needs
review / cancelled), reasons, priorities, and a sprinkle of contact
attempts so the receptionist UX has something to work through on a
fresh demo. Lazily seeds ``RecallSettings`` with the documented
defaults (already handled by the service, so we just call it once).

Idempotent for the given clinic: wipes the clinic's recalls +
attempts, then repopulates. ``recall.*`` events are NOT published
during seeding — listeners would re-seed off-cycle data.

Only invoked by ``backend/scripts/seed_demo.py`` after patients +
appointments exist (recalls reference both).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agenda.models import Appointment
from app.modules.patients.models import Patient
from app.seeds.demo_data import t

from .models import Recall, RecallContactAttempt
from .service import RecallSettingsService


def _normalize_due_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_months(d: date, months: int) -> date:
    base = _normalize_due_month(d)
    total = base.year * 12 + (base.month - 1) + months
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


# Eight scenario templates, cycled across patients. Together they
# cover every status the call-list filters can show, plus enough
# reasons and priorities for the dashboard counters to be non-trivial.
_SCENARIOS = (
    {
        "key": "pending_due_this_month_hygiene",
        "month_offset": 0,
        "reason": "hygiene",
        "priority": "normal",
        "status": "pending",
        "attempts": 0,
        "note": {
            "es": "Recordatorio de higiene anual.",
            "en": "Annual hygiene reminder.",
            "fr": "Rappel d'hygiène annuel.",
        },
    },
    {
        "key": "no_answer_overdue_checkup",
        "month_offset": -1,
        "reason": "checkup",
        "priority": "normal",
        "status": "contacted_no_answer",
        "attempts": 2,
        "note": {
            "es": "Revisión anual; no contesta al teléfono fijo.",
            "en": "Annual checkup; no answer on landline.",
            "fr": "Contrôle annuel ; pas de réponse au téléphone fixe.",
        },
    },
    {
        "key": "scheduled_postop_high",
        "month_offset": 0,
        "reason": "post_op",
        "priority": "high",
        "status": "contacted_scheduled",
        "attempts": 1,
        "note": {
            "es": "Postoperatorio de cirugía 36; cita confirmada.",
            "en": "Post-op surgery 36; appointment confirmed.",
            "fr": "Post-opératoire chirurgie 36 ; rendez-vous confirmé.",
        },
    },
    {
        "key": "done_last_month_hygiene",
        "month_offset": -1,
        "reason": "hygiene",
        "priority": "normal",
        "status": "done",
        "attempts": 1,
        "note": {
            "es": "Higiene completada en visita previa.",
            "en": "Hygiene completed at previous visit.",
            "fr": "Hygiène complétée lors de la visite précédente.",
        },
    },
    {
        "key": "pending_next_month_ortho",
        "month_offset": 1,
        "reason": "ortho_review",
        "priority": "normal",
        "status": "pending",
        "attempts": 0,
        "note": {
            "es": "Revisión mensual de ortodoncia.",
            "en": "Monthly orthodontic review.",
            "fr": "Contrôle mensuel d'orthodontie.",
        },
    },
    {
        "key": "needs_review_implant",
        "month_offset": -2,
        "reason": "implant_review",
        "priority": "high",
        "status": "needs_review",
        "attempts": 0,
        "note": {
            "es": "Revisión de implante 46; revisar contacto.",
            "en": "Implant 46 review; check contact.",
            "fr": "Révision implant 46 ; vérifier le contact.",
        },
    },
    {
        "key": "cancelled_treatment_followup",
        "month_offset": -1,
        "reason": "treatment_followup",
        "priority": "low",
        "status": "cancelled",
        "attempts": 1,
        "note": {
            "es": "Paciente declina seguimiento.",
            "en": "Patient declines follow-up.",
            "fr": "Patient décline le suivi.",
        },
    },
    {
        "key": "pending_three_months_implant",
        "month_offset": 3,
        "reason": "implant_review",
        "priority": "normal",
        "status": "pending",
        "attempts": 0,
        "note": {
            "es": "Control de implante a los 3 meses.",
            "en": "Implant check at 3 months.",
            "fr": "Contrôle d'implant à 3 mois.",
        },
    },
)


_ATTEMPT_NOTES = (
    {
        "es": "Llamada al móvil sin respuesta.",
        "en": "Called mobile, no answer.",
        "fr": "Appel mobile sans réponse.",
    },
    {
        "es": "Buzón de voz; mensaje dejado.",
        "en": "Voicemail; message left.",
        "fr": "Messagerie ; message laissé.",
    },
    {
        "es": "Indica que llamemos la próxima semana.",
        "en": "Asks us to call next week.",
        "fr": "Demande de rappeler la semaine prochaine.",
    },
    {
        "es": "Acuerda agendar tras revisar agenda laboral.",
        "en": "Agrees to schedule after checking work calendar.",
        "fr": "Accepte de planifier après vérification de l'agenda.",
    },
)


async def seed_recalls_demo(
    db: AsyncSession,
    clinic_id: UUID,
    dentist_id: UUID,
    hygienist_id: UUID,
    receptionist_id: UUID,
) -> dict[str, int]:
    """Populate the recalls module for the demo clinic.

    Returns ``{<status>: count}`` plus a top-level ``total`` for the
    summary line printed by ``seed_demo.py``.
    """
    # Wipe — attempts cascade via FK ondelete=CASCADE.
    await db.execute(delete(Recall).where(Recall.clinic_id == clinic_id))
    await db.flush()

    # Lazy-seed settings (idempotent — fetches the row or inserts the
    # documented defaults).
    await RecallSettingsService.get_or_create(db, clinic_id)

    patients_res = await db.execute(
        select(Patient).where(Patient.clinic_id == clinic_id).order_by(Patient.created_at)
    )
    patient_list = list(patients_res.scalars().all())

    # Map patient -> earliest scheduled appointment (used to give
    # ``contacted_scheduled`` recalls a real linked_appointment_id when
    # one exists; falls back to None otherwise).
    appt_res = await db.execute(
        select(Appointment)
        .where(Appointment.clinic_id == clinic_id)
        .order_by(Appointment.start_time)
    )
    appt_by_patient: dict[UUID, UUID] = {}
    for appt in appt_res.scalars().all():
        if appt.patient_id and appt.patient_id not in appt_by_patient:
            appt_by_patient[appt.patient_id] = appt.id

    today = date.today()
    now = datetime.now(UTC)

    stats: dict[str, int] = {
        "pending": 0,
        "contacted_no_answer": 0,
        "contacted_scheduled": 0,
        "done": 0,
        "cancelled": 0,
        "needs_review": 0,
        "attempts": 0,
        "total": 0,
    }

    for i, patient in enumerate(patient_list):
        scenario = _SCENARIOS[i % len(_SCENARIOS)]
        due_month = _add_months(today, scenario["month_offset"])
        created_at = now - timedelta(days=14 + (i % 21))

        completed_at = None
        if scenario["status"] == "done":
            completed_at = now - timedelta(days=5 + (i % 10))

        professional_id = (
            dentist_id
            if scenario["reason"]
            in (
                "post_op",
                "implant_review",
                "ortho_review",
                "treatment_followup",
            )
            else hygienist_id
        )

        recall = Recall(
            clinic_id=clinic_id,
            patient_id=patient.id,
            due_month=due_month,
            due_date=None,
            reason=scenario["reason"],
            reason_note=t(scenario["note"]),
            priority=scenario["priority"],
            status=scenario["status"],
            recommended_by=dentist_id,
            assigned_professional_id=professional_id,
            contact_attempt_count=scenario["attempts"],
            last_contact_attempt_at=(
                now - timedelta(days=2 + (i % 5)) if scenario["attempts"] > 0 else None
            ),
            completed_at=completed_at,
            created_at=created_at,
            updated_at=created_at,
        )
        if scenario["status"] == "contacted_scheduled":
            recall.linked_appointment_id = appt_by_patient.get(patient.id)

        db.add(recall)
        await db.flush()  # need recall.id to attach attempts

        # Attempts: one per N declared by the scenario, channels +
        # outcomes mixed so the call-list shows variety.
        for k in range(scenario["attempts"]):
            channel = "phone" if k == 0 else ("whatsapp" if k == 1 else "sms")
            outcome = (
                "scheduled"
                if scenario["status"] == "contacted_scheduled" and k == scenario["attempts"] - 1
                else (
                    "declined"
                    if scenario["status"] == "cancelled"
                    else ("voicemail" if k == 1 else "no_answer")
                )
            )
            db.add(
                RecallContactAttempt(
                    recall_id=recall.id,
                    clinic_id=clinic_id,
                    attempted_by=receptionist_id,
                    channel=channel,
                    outcome=outcome,
                    attempted_at=now - timedelta(days=k + 1, hours=2 * k),
                    note=t(_ATTEMPT_NOTES[(i + k) % len(_ATTEMPT_NOTES)]),
                )
            )
            stats["attempts"] += 1

        stats[scenario["status"]] += 1
        stats["total"] += 1

    await db.flush()
    return stats
