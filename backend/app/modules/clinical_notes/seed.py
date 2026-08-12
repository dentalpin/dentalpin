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
        "ta": "மாலை நேர சந்திப்புகளை விரும்புகிறார். உறுதிப்படுத்த 24 மணி நேரத்திற்கு முன் தெரிவிக்கவும்.",
    },
    {
        "es": "Llamar siempre al móvil; no responde al fijo.",
        "en": "Always call mobile; does not answer landline.",
        "fr": "Appeler toujours le portable ; ne répond pas au fixe.",
        "ta": "எப்போதும் மொபைல் எண்ணுக்கு அழைக்கவும்; லேண்ட்லைன் அழைப்புக்கு பதிலளிக்கமாட்டார்.",
    },
    {
        "es": "Pago habitual con tarjeta. Solicita factura simplificada.",
        "en": "Usually pays by card. Requests simplified invoice.",
        "fr": "Paiement habituel par carte. Demande une facture simplifiée.",
        "ta": "வழக்கமாக அட்டையால் பணம் செலுத்துகிறார். சுருக்கப்பட்ட விலைப்பட்டியலைக் கோருகிறார்.",
    },
    {
        "es": "Acude acompañado/a de un familiar; documentar consentimiento.",
        "en": "Attends with a family member; document consent.",
        "fr": "Vient accompagné(e) d'un membre de la famille ; documenter le consentement.",
        "ta": "குடும்ப உறுப்பினருடன் வருகிறார்; சம்மதத்தை ஆவணப்படுத்தவும்.",
    },
    {
        "es": "Idioma preferido para comunicaciones: español.",
        "en": "Preferred language for communications: Spanish.",
        "fr": "Langue préférée pour les communications : espagnol.",
        "ta": "தொடர்புகளுக்கான விருப்ப மொழி: ஸ்பானிஷ்.",
    },
    {
        "es": "Solicita recordatorio por WhatsApp el día anterior.",
        "en": "Requests WhatsApp reminder the day before.",
        "fr": "Demande un rappel par WhatsApp la veille.",
        "ta": "முந்தைய நாள் WhatsApp நினைவூட்டலைக் கோருகிறார்.",
    },
    {
        "es": "Tiene movilidad reducida; reservar cabinete accesible.",
        "en": "Has reduced mobility; reserve accessible room.",
        "fr": "Mobilité réduite ; réserver le cabinet accessible.",
        "ta": "இயக்கம் குறைந்தவர்; அணுகல் வசதியுள்ள அறையை முன்பதிவு செய்யவும்.",
    },
)

_DIAGNOSIS_BODIES = (
    {
        "es": "Caries oclusal incipiente; valorar empaste en próxima visita.",
        "en": "Incipient occlusal caries; evaluate filling at next visit.",
        "fr": "Carie occlusale naissante ; évaluer l'obturation à la prochaine visite.",
        "ta": "தொடக்கநிலை கடிப்பு மேற்பரப்பு பல் சொத்தை; அடுத்த சந்திப்பில் பல் நிரப்புதலை மதிப்பீடு செய்யவும்.",
    },
    {
        "es": "Movilidad grado I y sospecha de absceso periapical. Solicitar radiografía periapical.",
        "en": "Grade I mobility and suspected periapical abscess. Request periapical X-ray.",
        "fr": "Mobilité grade I et suspicion d'abcès périapical. Demander une radiographie périapicale.",
        "ta": "முதல் நிலை பல் அசைவு மற்றும் பல் வேர் முனைப்பகுதி சீழ்க்கட்டி சந்தேகம். பல் வேர் முனைப்பகுதி எக்ஸ்ரே கோரவும்.",
    },
    {
        "es": "Sensibilidad al frío en el cuadrante; descartar recesión gingival.",
        "en": "Cold sensitivity in quadrant; rule out gingival recession.",
        "fr": "Sensibilité au froid dans le quadrant ; éliminer la récession gingivale.",
        "ta": "குவாட்ரண்டில் குளிர் உணர்திறன்; ஈறு பின்வாங்கலை நிராகரிக்கவும்.",
    },
    {
        "es": "Bruxismo evidente con desgaste oclusal generalizado. Considerar férula de descarga.",
        "en": "Evident bruxism with generalized occlusal wear. Consider occlusal splint.",
        "fr": "Bruxisme évident avec usure occlusale généralisée. Envisager une gouttière d'occlusion.",
        "ta": "தெளிவான பற்களைக் கடித்தல் மற்றும் அரைத்தலுடன் பொதுவான கடிப்பு மேற்பரப்பு தேய்மானம் உள்ளது. கடிப்பு அழுத்தத் தடுப்பு ஸ்ப்ளிண்ட்டைப் பரிசீலிக்கவும்.",
    },
    {
        "es": "Encía inflamada con sangrado al sondaje. Refuerzo de higiene oral.",
        "en": "Inflamed gums with bleeding on probing. Oral hygiene reinforcement.",
        "fr": "Gencives enflammées avec saignement au sondage. Renforcement de l'hygiène buccale.",
        "ta": "ஈறுகளில் வீக்கத்துடன் ஆய்வுக் கருவி பரிசோதனையின்போது இரத்தக்கசிவு உள்ளது. வாய்வழி சுகாதார வழிமுறைகளை வலியுறுத்தவும்.",
    },
    {
        "es": "Restauración antigua filtrada; recomendar sustitución.",
        "en": "Leaky old restoration; recommend replacement.",
        "fr": "Obturation ancienne fuyante ; recommander le remplacement.",
        "ta": "கசிவு உள்ள பழைய பல் மறுசீரமைப்பு; மாற்றிப் பொருத்த பரிந்துரைக்கப்படுகிறது.",
    },
    {
        "es": "Tercer molar incluido sin sintomatología actual; mantener en observación.",
        "en": "Impacted third molar, currently asymptomatic; keep under observation.",
        "fr": "Troisième molaire inclus, actuellement asymptomatique ; maintenir sous observation.",
        "ta": "தற்போது அறிகுறிகள் இல்லாத புதைந்த மூன்றாம் கடைவாய்ப்பல்; தொடர்ந்து கண்காணிக்கவும்.",
    },
)

_TREATMENT_BODIES = (
    {
        "es": "Se aplica anestesia local (articaína 4% con epinefrina 1:100.000) sin incidencias.",
        "en": "Local anesthesia applied (articaine 4% with epinephrine 1:100,000) without incident.",
        "fr": "Anesthésie locale appliquée (articaine 4% avec épinéphrine 1:100 000) sans incident.",
        "ta": "உள்ளூர் மயக்க மருந்து (ஆர்டிகைன் 4% மற்றும் எபினெஃப்ரின் 1:100,000) எந்தச் சிக்கலும் இல்லாமல் செலுத்தப்பட்டது.",
    },
    {
        "es": "Apertura cameral e irrigación con hipoclorito sódico al 5,25%. Localizados 3 conductos.",
        "en": "Chamber access and irrigation with 5.25% sodium hypochlorite. 3 canals located.",
        "fr": "Ouverture pulpaire et irrigation à l'hypochlorite de sodium 5,25 %. 3 canaux localisés.",
        "ta": "பற்கூழ் அறை திறக்கப்பட்டு 5.25% சோடியம் ஹைப்போகுளோரைட்டால் கழுவப்பட்டது. 3 வேர் கால்வாய்கள் கண்டறியப்பட்டன.",
    },
    {
        "es": "Adaptación marginal correcta tras pulido. Paciente refiere ausencia de molestias.",
        "en": "Correct marginal adaptation after polishing. Patient reports no discomfort.",
        "fr": "Adaptation marginale correcte après polissage. Patient déclare absence de gêne.",
        "ta": "மெருகூட்டலுக்குப் பிறகு விளிம்புப் பொருத்தம் சரியாக உள்ளது. நோயாளி எந்த அசௌகரியமும் இல்லை எனத் தெரிவிக்கிறார்.",
    },
    {
        "es": "Se coloca dique de goma para aislamiento absoluto. Buena cooperación del paciente.",
        "en": "Rubber dam placed for absolute isolation. Good patient cooperation.",
        "fr": "Digue en place pour l'isolement absolu. Bonne coopération du patient.",
        "ta": "முழுமையான தனிமைப்படுத்தலுக்காக ரப்பர் டாம் பொருத்தப்பட்டது. நோயாளியின் ஒத்துழைப்பு நன்றாக இருந்தது.",
    },
    {
        "es": "Se recomienda cita de control en dos semanas para revisar oclusión.",
        "en": "Follow-up appointment recommended in two weeks to check occlusion.",
        "fr": "Rendez-vous de contrôle recommandé dans deux semaines pour vérifier l'occlusion.",
        "ta": "கடிப்பு நிலையைச் சரிபார்க்க இரண்டு வாரங்களில் தொடர் பரிசோதனை சந்திப்பு பரிந்துரைக்கப்படுகிறது.",
    },
    {
        "es": "Procedimiento sin complicaciones. Indicaciones postoperatorias entregadas.",
        "en": "Procedure without complications. Post-operative instructions given.",
        "fr": "Procédure sans complications. Consignes post-opératoires remises.",
        "ta": "செயல்முறை எந்தச் சிக்கலும் இல்லாமல் முடிந்தது. சிகிச்சைக்குப் பிந்தைய வழிமுறைகள் வழங்கப்பட்டன.",
    },
    {
        "es": "Cementado definitivo con cemento de ionómero de vidrio. Ajuste oclusal verificado.",
        "en": "Permanent cementation with glass ionomer cement. Occlusal adjustment verified.",
        "fr": "Cimentation définitive au ciment verre ionomère. Réglage occlusal vérifié.",
        "ta": "கண்ணாடி அயனோமர் சிமெண்ட் மூலம் நிரந்தரமாகப் பொருத்தப்பட்டது. கடிப்பு சீரமைப்பு சரிபார்க்கப்பட்டது.",
    },
)

_PLAN_BODIES = (
    {
        "es": "Plan acordado con el paciente. Priorizar tratamientos urgentes en cuadrante superior derecho.",
        "en": "Plan agreed with patient. Prioritize urgent treatments in the upper right quadrant.",
        "fr": "Plan convenu avec le patient. Prioriser les traitements urgents dans le quadrant supérieur droit.",
        "ta": "நோயாளியுடன் சிகிச்சைத் திட்டம் ஒப்புக்கொள்ளப்பட்டது. மேல் வலது குவாட்ரண்டில் உள்ள அவசர சிகிச்சைகளுக்கு முன்னுரிமை அளிக்கவும்.",
    },
    {
        "es": "Paciente solicita financiación; gestionar opción a 6 meses sin intereses.",
        "en": "Patient requests financing; arrange 6-month interest-free option.",
        "fr": "Patient demande un financement ; organiser l'option 6 mois sans intérêts.",
        "ta": "நோயாளர் தவணை முறையில் பணம் செலுத்த விரும்புகிறார்; வட்டி இல்லாத 6 மாதத் திட்டத்தை ஏற்பாடு செய்யவும்.",
    },
    {
        "es": "Se acuerda iniciar fase higiénica antes de los tratamientos restauradores.",
        "en": "Hygiene phase agreed before restorative treatments.",
        "fr": "Phase d'hygiène convenue avant les traitements restaurateurs.",
        "ta": "மறுசீரமைப்பு சிகிச்சைகளைத் தொடங்குவதற்கு முன் வாய்வழி சுகாதார கட்டத்தை மேற்கொள்ள ஒப்புக்கொள்ளப்பட்டது.",
    },
    {
        "es": "Pendiente de presentación al cónyuge; confirmará aceptación tras consulta familiar.",
        "en": "Pending presentation to spouse; will confirm acceptance after family consultation.",
        "fr": "En attente de présentation au conjoint ; confirmera l'acceptation après consultation familiale.",
        "ta": "துணையிடம் சிகிச்சைத் திட்டத்தை விளக்குவது நிலுவையில் உள்ளது; குடும்ப ஆலோசனைக்குப் பிறகு ஒப்புதலை உறுதிப்படுத்துவார்.",
    },
    {
        "es": "Se aplica descuento del 10% por tratamiento integral.",
        "en": "10% discount applied for comprehensive treatment.",
        "fr": "Remise de 10 % appliquée pour le traitement global.",
        "ta": "முழுமையான சிகிச்சைக்காக 10% தள்ளுபடி வழங்கப்பட்டது.",
    },
    {
        "es": "Paciente prefiere posponer la fase estética hasta después del verano.",
        "en": "Patient prefers to postpone the aesthetic phase until after summer.",
        "fr": "Patient préfère reporter la phase esthétique après l'été.",
        "ta": "கோடைக்காலத்திற்குப் பிறகு அழகியல் சிகிச்சைக் கட்டத்தைத் தொடங்க நோயாளர் விரும்புகிறார்.",
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
