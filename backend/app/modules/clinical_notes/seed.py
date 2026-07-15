"""Demo seed for clinical notes.

Derives notes from already-seeded patients, treatment plans and
treatments. Inserts ``ClinicalNote`` rows directly without firing
``clinical_notes.*_created`` events so re-seed remains idempotent —
``patient_timeline`` re-derives its own rows from the source data and
firing events here would have it double-record entries that its seed
later wipes.

Only invoked by ``backend/scripts/seed_demo.py`` after treatment plans
exist (notes need their owners). Idempotent for the given clinic:
wipes the clinic's clinical_notes rows, then repopulates.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.odontogram.models import Treatment, TreatmentTooth
from app.modules.patients.models import Patient
from app.modules.treatment_plan.models import TreatmentPlan
from app.seeds.demo_data import t

from .models import (
    NOTE_OWNER_PATIENT,
    NOTE_OWNER_PLAN,
    NOTE_OWNER_TREATMENT,
    NOTE_TYPE_ADMINISTRATIVE,
    NOTE_TYPE_DIAGNOSIS,
    NOTE_TYPE_TREATMENT,
    NOTE_TYPE_TREATMENT_PLAN,
    ClinicalNote,
)

# Translation dicts resolved via t() at seed time — after set_language().
_ADMIN_BODIES = (
    {
        "es": "Prefiere citas por la tarde. Avisar 24h antes para confirmar.",
        "en": "Prefers afternoon appointments. Notify 24h before to confirm.",
        "fr": "Préfère les rendez-vous l'après-midi. Prévenir 24h avant pour confirmer.",
    },
    {
        "es": "Llamar siempre al móvil; no responde al fijo.",
        "en": "Always call mobile; does not answer landline.",
        "fr": "Appeler toujours le portable ; ne répond pas au fixe.",
    },
    {
        "es": "Pago habitual con tarjeta. Solicita factura simplificada.",
        "en": "Usually pays by card. Requests simplified invoice.",
        "fr": "Paiement habituel par carte. Demande une facture simplifiée.",
    },
    {
        "es": "Acude acompañado/a de un familiar; documentar consentimiento.",
        "en": "Attends with a family member; document consent.",
        "fr": "Vient accompagné(e) d'un membre de la famille ; documenter le consentement.",
    },
    {
        "es": "Idioma preferido para comunicaciones: español.",
        "en": "Preferred language for communications: Spanish.",
        "fr": "Langue préférée pour les communications : espagnol.",
    },
    {
        "es": "Solicita recordatorio por WhatsApp el día anterior.",
        "en": "Requests WhatsApp reminder the day before.",
        "fr": "Demande un rappel par WhatsApp la veille.",
    },
    {
        "es": "Tiene movilidad reducida; reservar cabinete accesible.",
        "en": "Has reduced mobility; reserve accessible room.",
        "fr": "Mobilité réduite ; réserver le cabinet accessible.",
    },
)

_DIAGNOSIS_BODIES = (
    {
        "es": "Caries oclusal incipiente; valorar empaste en próxima visita.",
        "en": "Incipient occlusal caries; evaluate filling at next visit.",
        "fr": "Carie occlusale naissante ; évaluer l'obturation à la prochaine visite.",
    },
    {
        "es": "Movilidad grado I y sospecha de absceso periapical. Solicitar radiografía periapical.",
        "en": "Grade I mobility and suspected periapical abscess. Request periapical X-ray.",
        "fr": "Mobilité grade I et suspicion d'abcès périapical. Demander une radiographie périapicale.",
    },
    {
        "es": "Sensibilidad al frío en el cuadrante; descartar recesión gingival.",
        "en": "Cold sensitivity in quadrant; rule out gingival recession.",
        "fr": "Sensibilité au froid dans le quadrant ; éliminer la récession gingivale.",
    },
    {
        "es": "Bruxismo evidente con desgaste oclusal generalizado. Considerar férula de descarga.",
        "en": "Evident bruxism with generalized occlusal wear. Consider occlusal splint.",
        "fr": "Bruxisme évident avec usure occlusale généralisée. Envisager une gouttière d'occlusion.",
    },
    {
        "es": "Encía inflamada con sangrado al sondaje. Refuerzo de higiene oral.",
        "en": "Inflamed gums with bleeding on probing. Oral hygiene reinforcement.",
        "fr": "Gencives enflammées avec saignement au sondage. Renforcement de l'hygiène buccale.",
    },
    {
        "es": "Restauración antigua filtrada; recomendar sustitución.",
        "en": "Leaky old restoration; recommend replacement.",
        "fr": "Obturation ancienne fuyante ; recommander le remplacement.",
    },
    {
        "es": "Tercer molar incluido sin sintomatología actual; mantener en observación.",
        "en": "Impacted third molar, currently asymptomatic; keep under observation.",
        "fr": "Troisième molaire inclus, actuellement asymptomatique ; maintenir sous observation.",
    },
)

_TREATMENT_BODIES = (
    {
        "es": "Se aplica anestesia local (articaína 4% con epinefrina 1:100.000) sin incidencias.",
        "en": "Local anesthesia applied (articaine 4% with epinephrine 1:100,000) without incident.",
        "fr": "Anesthésie locale appliquée (articaine 4% avec épinéphrine 1:100 000) sans incident.",
    },
    {
        "es": "Apertura cameral e irrigación con hipoclorito sódico al 5,25%. Localizados 3 conductos.",
        "en": "Chamber access and irrigation with 5.25% sodium hypochlorite. 3 canals located.",
        "fr": "Ouverture pulpaire et irrigation à l'hypochlorite de sodium 5,25 %. 3 canaux localisés.",
    },
    {
        "es": "Adaptación marginal correcta tras pulido. Paciente refiere ausencia de molestias.",
        "en": "Correct marginal adaptation after polishing. Patient reports no discomfort.",
        "fr": "Adaptation marginale correcte après polissage. Patient déclare absence de gêne.",
    },
    {
        "es": "Se coloca dique de goma para aislamiento absoluto. Buena cooperación del paciente.",
        "en": "Rubber dam placed for absolute isolation. Good patient cooperation.",
        "fr": "Digue en place pour l'isolement absolu. Bonne coopération du patient.",
    },
    {
        "es": "Se recomienda cita de control en dos semanas para revisar oclusión.",
        "en": "Follow-up appointment recommended in two weeks to check occlusion.",
        "fr": "Rendez-vous de contrôle recommandé dans deux semaines pour vérifier l'occlusion.",
    },
    {
        "es": "Procedimiento sin complicaciones. Indicaciones postoperatorias entregadas.",
        "en": "Procedure without complications. Post-operative instructions given.",
        "fr": "Procédure sans complications. Consignes post-opératoires remises.",
    },
    {
        "es": "Cementado definitivo con cemento de ionómero de vidrio. Ajuste oclusal verificado.",
        "en": "Permanent cementation with glass ionomer cement. Occlusal adjustment verified.",
        "fr": "Cimentation définitive au ciment verre ionomère. Réglage occlusal vérifié.",
    },
)

_PLAN_BODIES = (
    {
        "es": "Plan acordado con el paciente. Priorizar tratamientos urgentes en cuadrante superior derecho.",
        "en": "Plan agreed with patient. Prioritize urgent treatments in the upper right quadrant.",
        "fr": "Plan convenu avec le patient. Prioriser les traitements urgents dans le quadrant supérieur droit.",
    },
    {
        "es": "Paciente solicita financiación; gestionar opción a 6 meses sin intereses.",
        "en": "Patient requests financing; arrange 6-month interest-free option.",
        "fr": "Patient demande un financement ; organiser l'option 6 mois sans intérêts.",
    },
    {
        "es": "Se acuerda iniciar fase higiénica antes de los tratamientos restauradores.",
        "en": "Hygiene phase agreed before restorative treatments.",
        "fr": "Phase d'hygiène convenue avant les traitements restaurateurs.",
    },
    {
        "es": "Pendiente de presentación al cónyuge; confirmará aceptación tras consulta familiar.",
        "en": "Pending presentation to spouse; will confirm acceptance after family consultation.",
        "fr": "En attente de présentation au conjoint ; confirmera l'acceptation après consultation familiale.",
    },
    {
        "es": "Se aplica descuento del 10% por tratamiento integral.",
        "en": "10% discount applied for comprehensive treatment.",
        "fr": "Remise de 10 % appliquée pour le traitement global.",
    },
    {
        "es": "Paciente prefiere posponer la fase estética hasta después del verano.",
        "en": "Patient prefers to postpone the aesthetic phase until after summer.",
        "fr": "Patient préfère reporter la phase esthétique après l'été.",
    },
)


async def seed_clinical_notes_demo(
    db: AsyncSession,
    clinic_id: UUID,
    dentist_id: UUID,
    hygienist_id: UUID,
) -> dict[str, int]:
    """Populate clinical_notes for the demo clinic.

    Returns ``{"administrative": n, "diagnosis": n, "treatment": n,
    "treatment_plan": n}`` for the seed-demo summary line.
    """
    await db.execute(delete(ClinicalNote).where(ClinicalNote.clinic_id == clinic_id))

    stats = {"administrative": 0, "diagnosis": 0, "treatment": 0, "treatment_plan": 0}
    now = datetime.now(UTC)
    cursor = 0

    def author(idx: int) -> UUID:
        return dentist_id if idx % 2 == 0 else hygienist_id

    # --- Per-patient: administrative + diagnosis -------------------------
    patients_res = await db.execute(
        select(Patient).where(Patient.clinic_id == clinic_id).order_by(Patient.created_at)
    )
    patient_list = list(patients_res.scalars().all())

    # First tooth per patient from seeded TreatmentTooth — gives diagnosis
    # notes a realistic tooth pin where the odontogram already has data.
    tt_rows = await db.execute(
        select(TreatmentTooth.tooth_number, Treatment.patient_id)
        .join(Treatment, TreatmentTooth.treatment_id == Treatment.id)
        .where(Treatment.clinic_id == clinic_id)
    )
    tooth_by_patient: dict[UUID, int] = {}
    for tooth_number, patient_id in tt_rows.all():
        tooth_by_patient.setdefault(patient_id, tooth_number)

    for i, patient in enumerate(patient_list):
        admin_at = now - timedelta(days=80 + (i % 14))
        db.add(
            ClinicalNote(
                clinic_id=clinic_id,
                note_type=NOTE_TYPE_ADMINISTRATIVE,
                owner_type=NOTE_OWNER_PATIENT,
                owner_id=patient.id,
                tooth_number=None,
                body=t(_ADMIN_BODIES[cursor % len(_ADMIN_BODIES)]),
                author_id=author(cursor),
                created_at=admin_at,
                updated_at=admin_at,
            )
        )
        cursor += 1
        stats["administrative"] += 1

        diag_at = now - timedelta(days=55 + (i % 14))
        db.add(
            ClinicalNote(
                clinic_id=clinic_id,
                note_type=NOTE_TYPE_DIAGNOSIS,
                owner_type=NOTE_OWNER_PATIENT,
                owner_id=patient.id,
                tooth_number=tooth_by_patient.get(patient.id),
                body=t(_DIAGNOSIS_BODIES[cursor % len(_DIAGNOSIS_BODIES)]),
                author_id=author(cursor),
                created_at=diag_at,
                updated_at=diag_at,
            )
        )
        cursor += 1
        stats["diagnosis"] += 1

    # --- Per-plan: treatment_plan note (~2 of every 3 plans) -------------
    plans_res = await db.execute(
        select(TreatmentPlan)
        .where(TreatmentPlan.clinic_id == clinic_id)
        .order_by(TreatmentPlan.created_at)
    )
    for i, plan in enumerate(plans_res.scalars().all()):
        if i % 3 == 0:
            continue
        plan_at = now - timedelta(days=30 + (i % 14))
        db.add(
            ClinicalNote(
                clinic_id=clinic_id,
                note_type=NOTE_TYPE_TREATMENT_PLAN,
                owner_type=NOTE_OWNER_PLAN,
                owner_id=plan.id,
                tooth_number=None,
                body=t(_PLAN_BODIES[cursor % len(_PLAN_BODIES)]),
                author_id=author(cursor),
                created_at=plan_at,
                updated_at=plan_at,
            )
        )
        cursor += 1
        stats["treatment_plan"] += 1

    # --- Per-performed-treatment: treatment note (every other one) -------
    performed_res = await db.execute(
        select(Treatment).where(
            Treatment.clinic_id == clinic_id,
            Treatment.status == "performed",
        )
    )
    for i, tx in enumerate(performed_res.scalars().all()):
        if i % 2 == 1:
            continue
        tx_at = now - timedelta(days=10 + (i % 18))
        db.add(
            ClinicalNote(
                clinic_id=clinic_id,
                note_type=NOTE_TYPE_TREATMENT,
                owner_type=NOTE_OWNER_TREATMENT,
                owner_id=tx.id,
                tooth_number=None,
                body=t(_TREATMENT_BODIES[cursor % len(_TREATMENT_BODIES)]),
                author_id=author(cursor),
                created_at=tx_at,
                updated_at=tx_at,
            )
        )
        cursor += 1
        stats["treatment"] += 1

    await db.flush()
    return stats
