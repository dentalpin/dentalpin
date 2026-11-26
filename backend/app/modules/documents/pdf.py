"""Branded PDF rendering for generated clinical documents.

Renders a prescription, medical certificate, referral letter or
radiology request as a clinic-branded PDF.  Mirrors billing's
``InvoicePDFService``: WeasyPrint is CPU-bound, so rendering is
offloaded to a worker thread via ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from html import escape
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.core.pdf_locales import format_pdf_date, format_pdf_datetime

if TYPE_CHECKING:
    from app.core.auth.models import Clinic
    from app.modules.patients.models import Patient

    from .models import GeneratedDocument

_LABELS = {
    "es": {
        "patient": "Paciente",
        "dob": "Fecha de nacimiento",
        "doc": "Documento",
        "issued": "Fecha de emisión",
        "issued_by": "Emitido por",
        "diagnosis": "Diagnóstico",
        "description": "Descripción",
        "recommendations": "Recomendaciones",
        "medications": "Medicación",
        "medName": "Medicamento",
        "dose": "Dosis",
        "frequency": "Frecuencia",
        "duration": "Duración",
        "referred_to": "Derivado a",
        "specialty": "Especialidad",
        "reason": "Motivo de la derivación",
        "clinical_summary": "Resumen clínico",
        "exam_type": "Tipo de exploración",
        "region": "Región",
        "clinical_question": "Pregunta clínica",
        "notes": "Observaciones",
        "generated_by": "Generado con DentalPin",
        "registration_number": "Nº colegiado",
        "informed_consent": "Consentimiento informado",
        "prescription": "Receta",
        "medical_certificate": "Certificado médico",
        "referral": "Carta de derivación",
        "radiology_request": "Solicitud de radiología",
    },
    "en": {
        "patient": "Patient",
        "dob": "Date of birth",
        "doc": "Document",
        "issued": "Issue date",
        "issued_by": "Issued by",
        "diagnosis": "Diagnosis",
        "description": "Description",
        "recommendations": "Recommendations",
        "medications": "Medication",
        "medName": "Medication",
        "dose": "Dose",
        "frequency": "Frequency",
        "duration": "Duration",
        "referred_to": "Referred to",
        "specialty": "Specialty",
        "reason": "Reason for referral",
        "clinical_summary": "Clinical summary",
        "exam_type": "Exam type",
        "region": "Region",
        "clinical_question": "Clinical question",
        "notes": "Notes",
        "generated_by": "Generated with DentalPin",
        "registration_number": "License number",
        "informed_consent": "Informed consent",
        "prescription": "Prescription",
        "medical_certificate": "Medical certificate",
        "referral": "Referral letter",
        "radiology_request": "Radiology request",
    },
    "ta": {
        "patient": "நோயாளி",
        "dob": "பிறந்த தேதி",
        "doc": "ஆவணம்",
        "issued": "வெளியிட்ட தேதி",
        "issued_by": "வழங்கியவர்",
        "diagnosis": "நோய் கண்டறிதல்",
        "description": "விளக்கம்",
        "recommendations": "பரிந்துரைகள்",
        "medications": "மருந்துகள்",
        "medName": "மருந்து",
        "dose": "அளவு",
        "frequency": "அடிக்கடி",
        "duration": "கால அளவு",
        "referred_to": "பரிந்துரைக்கப்பட்டவர்",
        "specialty": "சிறப்புத் துறை",
        "reason": "பரிந்துரைக்கான காரணம்",
        "clinical_summary": "மருத்துவச் சுருக்கம்",
        "exam_type": "பரிசோதனை வகை",
        "region": "பகுதி",
        "clinical_question": "மருத்துவ வினா",
        "notes": "குறிப்புகள்",
        "generated_by": "DentalPin மூலம் உருவாக்கப்பட்டது",
        "registration_number": "உரிம எண்",
        "informed_consent": "தகவலறிந்த ஒப்புதல்",
        "prescription": "மருந்துச்சீட்டு",
        "medical_certificate": "மருத்துவச் சான்றிதழ்",
        "referral": "பரிந்துரைக் கடிதம்",
        "radiology_request": "கதிரியக்க பரிசோதனை கோரிக்கை",
    },
    "te": {
        "patient": "రోగి",
        "dob": "పుట్టిన తేదీ",
        "doc": "పత్రం",
        "issued": "జారీ తేదీ",
        "issued_by": "జారీ చేసినవారు",
        "diagnosis": "రోగనిర్ధారణ",
        "description": "వివరణ",
        "recommendations": "సిఫార్సులు",
        "medications": "మందులు",
        "medName": "మందు",
        "dose": "మోతాదు",
        "frequency": "ఎన్ని సార్లు",
        "duration": "వ్యవధి",
        "referred_to": "ఎవరికి రిఫర్ చేశారు",
        "specialty": "ప్రత్యేకత",
        "reason": "రిఫరల్ కారణం",
        "clinical_summary": "క్లినికల్ సారాంశం",
        "exam_type": "పరీక్ష రకం",
        "region": "ప్రాంతం",
        "clinical_question": "క్లినికల్ ప్రశ్న",
        "notes": "గమనికలు",
        "generated_by": "DentalPin ద్వారా రూపొందించబడింది",
        "registration_number": "లైసెన్స్ నంబర్",
        "informed_consent": "సమాచారంతో కూడిన సమ్మతి",
        "prescription": "ప్రిస్క్రిప్షన్",
        "medical_certificate": "వైద్య సర్టిఫికెట్",
        "referral": "రిఫరల్ లేఖ",
        "radiology_request": "రేడియాలజీ అభ్యర్థన",
    },
    "hi": {
        "patient": "मरीज़",
        "dob": "जन्म तिथि",
        "doc": "दस्तावेज़",
        "issued": "जारी करने की तिथि",
        "issued_by": "जारीकर्ता",
        "diagnosis": "निदान",
        "description": "विवरण",
        "recommendations": "सिफ़ारिशें",
        "medications": "दवाइयाँ",
        "medName": "दवा",
        "dose": "खुराक",
        "frequency": "आवृत्ति",
        "duration": "अवधि",
        "referred_to": "किसके पास भेजा गया",
        "specialty": "विशेषज्ञता",
        "reason": "रेफ़र करने का कारण",
        "clinical_summary": "नैदानिक सारांश",
        "exam_type": "जाँच का प्रकार",
        "region": "क्षेत्र",
        "clinical_question": "नैदानिक प्रश्न",
        "notes": "टिप्पणियाँ",
        "generated_by": "DentalPin द्वारा तैयार",
        "registration_number": "पंजीकरण संख्या",
        "informed_consent": "सूचित सहमति",
        "prescription": "पर्चा",
        "medical_certificate": "चिकित्सा प्रमाणपत्र",
        "referral": "रेफ़रल पत्र",
        "radiology_request": "रेडियोलॉजी जाँच अनुरोध",
    },
    "fr": {
        "patient": "Patient",
        "dob": "Date de naissance",
        "doc": "Document",
        "issued": "Date d'émission",
        "issued_by": "Émis par",
        "diagnosis": "Diagnostic",
        "description": "Description",
        "recommendations": "Recommandations",
        "medications": "Médicaments",
        "medName": "Médicament",
        "dose": "Posologie",
        "frequency": "Fréquence",
        "duration": "Durée",
        "referred_to": "Adressé à",
        "specialty": "Spécialité",
        "reason": "Motif de l'orientation",
        "clinical_summary": "Résumé clinique",
        "exam_type": "Type d'examen",
        "region": "Région",
        "clinical_question": "Question clinique",
        "notes": "Notes",
        "generated_by": "Généré avec DentalPin",
        "registration_number": "N° de licence",
        "informed_consent": "Consentement éclairé",
        "prescription": "Ordonnance",
        "medical_certificate": "Certificat médical",
        "referral": "Lettre d'orientation",
        "radiology_request": "Demande de radiologie",
    },
    "pt": {
        "patient": "Paciente",
        "dob": "Data de nascimento",
        "doc": "Documento",
        "issued": "Data de emissão",
        "issued_by": "Emitido por",
        "diagnosis": "Diagnóstico",
        "description": "Descrição",
        "recommendations": "Recomendações",
        "medications": "Medicação",
        "medName": "Medicamento",
        "dose": "Dose",
        "frequency": "Frequência",
        "duration": "Duração",
        "referred_to": "Encaminhado a",
        "specialty": "Especialidade",
        "reason": "Motivo do encaminhamento",
        "clinical_summary": "Resumo clínico",
        "exam_type": "Tipo de exame",
        "region": "Região",
        "clinical_question": "Questão clínica",
        "notes": "Notas",
        "generated_by": "Gerado com o DentalPin",
        "registration_number": "N.º de licença",
        "informed_consent": "Consentimento informado",
        "prescription": "Receita médica",
        "medical_certificate": "Atestado médico",
        "referral": "Carta de encaminhamento",
        "radiology_request": "Pedido de radiologia",
    },
    "de": {
        "patient": "Patient",
        "dob": "Geburtsdatum",
        "doc": "Dokument",
        "issued": "Ausstellungsdatum",
        "issued_by": "Ausgestellt von",
        "diagnosis": "Diagnose",
        "description": "Beschreibung",
        "recommendations": "Empfehlungen",
        "medications": "Medikation",
        "medName": "Medikament",
        "dose": "Dosierung",
        "frequency": "Häufigkeit",
        "duration": "Dauer",
        "referred_to": "Überweisung an",
        "specialty": "Fachgebiet",
        "reason": "Überweisungsgrund",
        "clinical_summary": "Klinische Zusammenfassung",
        "exam_type": "Untersuchungsart",
        "region": "Region",
        "clinical_question": "Fragestellung",
        "notes": "Notizen",
        "generated_by": "Erstellt mit DentalPin",
        "registration_number": "Lizenznummer",
        "informed_consent": "Einwilligung nach Aufklärung",
        "prescription": "Rezept",
        "medical_certificate": "Ärztliches Attest",
        "referral": "Überweisungsschreiben",
        "radiology_request": "Röntgenanforderung",
    },
    "hu": {
        "patient": "Páciens",
        "dob": "Születési dátum",
        "doc": "Dokumentum",
        "issued": "Kiállítás dátuma",
        "issued_by": "Kiállította",
        "diagnosis": "Diagnózis",
        "description": "Leírás",
        "recommendations": "Javaslatok",
        "medications": "Gyógyszerelés",
        "medName": "Gyógyszer",
        "dose": "Adagolás",
        "frequency": "Gyakoriság",
        "duration": "Időtartam",
        "referred_to": "Beutalva ide",
        "specialty": "Szakterület",
        "reason": "A beutalás indoka",
        "clinical_summary": "Klinikai összefoglaló",
        "exam_type": "Vizsgálat típusa",
        "region": "Régió",
        "clinical_question": "Klinikai kérdés",
        "notes": "Megjegyzések",
        "generated_by": "Készült a DentalPin rendszerrel",
        "registration_number": "Pecsétszám",
        "informed_consent": "Tájékozott beleegyezés",
        "prescription": "Recept",
        "medical_certificate": "Orvosi igazolás",
        "referral": "Beutaló",
        "radiology_request": "Röntgenkérő",
    },
    "pl": {
        "patient": "Pacjent",
        "dob": "Data urodzenia",
        "doc": "Dokument",
        "issued": "Data wystawienia",
        "issued_by": "Wystawił",
        "diagnosis": "Rozpoznanie",
        "description": "Opis",
        "recommendations": "Zalecenia",
        "medications": "Leki",
        "medName": "Lek",
        "dose": "Dawka",
        "frequency": "Częstotliwość",
        "duration": "Czas trwania",
        "referred_to": "Skierowanie do",
        "specialty": "Specjalizacja",
        "reason": "Powód skierowania",
        "clinical_summary": "Podsumowanie kliniczne",
        "exam_type": "Rodzaj badania",
        "region": "Okolica",
        "clinical_question": "Pytanie kliniczne",
        "notes": "Uwagi",
        "generated_by": "Wygenerowano w DentalPin",
        "registration_number": "Nr prawa wykonywania zawodu",
        "informed_consent": "Świadoma zgoda",
        "prescription": "Recepta",
        "medical_certificate": "Zaświadczenie lekarskie",
        "referral": "Skierowanie",
        "radiology_request": "Skierowanie na badanie RTG",
    },
    "it": {
        "patient": "Paziente",
        "dob": "Data di nascita",
        "doc": "Documento",
        "issued": "Data di emissione",
        "issued_by": "Rilasciato da",
        "diagnosis": "Diagnosi",
        "description": "Descrizione",
        "recommendations": "Raccomandazioni",
        "medications": "Terapia farmacologica",
        "medName": "Farmaco",
        "dose": "Posologia",
        "frequency": "Frequenza",
        "duration": "Durata",
        "referred_to": "Inviato a",
        "specialty": "Specialità",
        "reason": "Motivo dell'invio",
        "clinical_summary": "Riepilogo clinico",
        "exam_type": "Tipo di esame",
        "region": "Regione",
        "clinical_question": "Quesito clinico",
        "notes": "Note",
        "generated_by": "Generato con DentalPin",
        "registration_number": "N. di licenza",
        "informed_consent": "Consenso informato",
        "prescription": "Ricetta medica",
        "medical_certificate": "Certificato medico",
        "referral": "Lettera di invio",
        "radiology_request": "Richiesta radiologica",
    },
    "ar": {
        "patient": "المريض",
        "dob": "تاريخ الميلاد",
        "doc": "المستند",
        "issued": "تاريخ الإصدار",
        "issued_by": "صادر عن",
        "diagnosis": "التشخيص",
        "description": "الوصف",
        "recommendations": "التوصيات",
        "medications": "الأدوية",
        "medName": "الدواء",
        "dose": "الجرعة",
        "frequency": "عدد المرات",
        "duration": "المدة",
        "referred_to": "محال إلى",
        "specialty": "التخصص",
        "reason": "سبب الإحالة",
        "clinical_summary": "الملخص السريري",
        "exam_type": "نوع الفحص",
        "region": "المنطقة",
        "clinical_question": "السؤال السريري",
        "notes": "ملاحظات",
        "generated_by": "أُنشئ باستخدام DentalPin",
        "registration_number": "رقم الترخيص",
        "informed_consent": "الموافقة المستنيرة",
        "prescription": "وصفة طبية",
        "medical_certificate": "شهادة طبية",
        "referral": "خطاب إحالة",
        "radiology_request": "طلب أشعة",
    },
}
# pt-BR reuses pt labels as there is no differing words so far.
# Consent-specific text is translated for every supported PDF language.
_CONSENT_LABELS = {
    "es": (
        "Revocación",
        "El firmante revoca el consentimiento anterior.",
        "Paciente",
        "Tutor legal",
        "Representante",
        "BORRADOR",
    ),
    "en": (
        "Revocation",
        "The signer revokes the prior consent.",
        "Patient",
        "Legal guardian",
        "Representative",
        "DRAFT",
    ),
    "ta": (
        "திரும்பப் பெறுதல்",
        "கையொப்பமிட்டவர் முந்தைய ஒப்புதலைத் திரும்பப் பெறுகிறார்.",
        "நோயாளர்",
        "சட்டப்பூர்வ பாதுகாவலர்",
        "பிரதிநிதி",
        "வரைவு",
    ),
    "te": (
        "ఉపసంహరణ",
        "సంతకం చేసిన వ్యక్తి మునుపటి సమ్మతిని ఉపసంహరించుకుంటున్నారు.",
        "రోగి",
        "చట్టపరమైన సంరక్షకుడు",
        "ప్రతినిధి",
        "ముసాయిదా",
    ),
    "hi": (
        "निरस्तीकरण",
        "हस्ताक्षरकर्ता पिछली सहमति वापस लेता है।",
        "रोगी",
        "कानूनी अभिभावक",
        "प्रतिनिधि",
        "मसौदा",
    ),
    "fr": (
        "Révocation",
        "Le signataire révoque le consentement précédent.",
        "Patient",
        "Tuteur légal",
        "Représentant",
        "BROUILLON",
    ),
    "pt": (
        "Revogação",
        "O signatário revoga o consentimento anterior.",
        "Paciente",
        "Tutor legal",
        "Representante",
        "RASCUNHO",
    ),
    "de": (
        "Widerruf",
        "Die unterzeichnende Person widerruft die vorherige Einwilligung.",
        "Patient",
        "Gesetzlicher Vormund",
        "Vertretung",
        "ENTWURF",
    ),
    "hu": (
        "Visszavonás",
        "Az aláíró visszavonja a korábbi beleegyezést.",
        "Páciens",
        "Törvényes gyám",
        "Képviselő",
        "TERVEZET",
    ),
    "pl": (
        "Wycofanie",
        "Podpisujący wycofuje wcześniejszą zgodę.",
        "Pacjent",
        "Opiekun prawny",
        "Przedstawiciel",
        "PROJEKT",
    ),
    "it": (
        "Revoca",
        "Il firmatario revoca il consenso precedente.",
        "Paziente",
        "Tutore legale",
        "Rappresentante",
        "BOZZA",
    ),
    "ar": (
        "سحب الموافقة",
        "يسحب الموقّع الموافقة السابقة.",
        "المريض",
        "الوصي القانوني",
        "الممثل",
        "مسودة",
    ),
}
for _locale, _values in _CONSENT_LABELS.items():
    _LABELS[_locale].update(
        dict(
            zip(
                (
                    "consent_revocation",
                    "consent_revocation_text",
                    "consent_patient",
                    "consent_guardian",
                    "consent_representative",
                    "consent_draft",
                ),
                _values,
                strict=True,
            )
        )
    )

_LABELS["pt-BR"] = _LABELS["pt"]


class DocumentPDFService:
    """Service for generating branded PDFs of clinical documents."""

    @staticmethod
    def async_generate_pdf(
        document: GeneratedDocument,
        clinic: Clinic,
        patient: Patient,
        locale: str = "es",
        issued_by: str = "",
    ) -> asyncio.Future[bytes]:
        """Render the document to PDF bytes off the event loop."""
        return asyncio.to_thread(
            DocumentPDFService._generate_pdf,
            document,
            clinic,
            patient,
            locale,
            issued_by,
        )

    @classmethod
    async def generate_pdf(
        cls,
        document: GeneratedDocument,
        clinic: Clinic,
        patient: Patient,
        locale: str = "es",
        issued_by: str = "",
    ) -> bytes:
        """Return the rendered PDF for a document."""
        return await cls.async_generate_pdf(document, clinic, patient, locale, issued_by)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pdf(
        document: GeneratedDocument,
        clinic: Clinic,
        patient: Patient,
        locale: str,
        issued_by: str,
    ) -> bytes:
        html = DocumentPDFService._generate_html(document, clinic, patient, locale, issued_by)
        return DocumentPDFService._html_to_pdf(html)

    @staticmethod
    def _format_address(address: dict | None) -> str:
        """Format a clinic address dict as a readable string."""
        if not address:
            return ""
        parts = []
        if address.get("street"):
            parts.append(address["street"])
        city_line = " ".join(filter(None, [address.get("postal_code"), address.get("city")]))
        if city_line:
            parts.append(city_line)
        if address.get("country"):
            parts.append(address["country"])
        return ", ".join(parts)

    @staticmethod
    def _letterhead(clinic: Clinic) -> dict:
        """Resolve letterhead settings for a clinic.

        Per-clinic overrides live under ``clinic.settings["documents"]["letterhead"]``;
        every key falls back to the clinic's native profile.
        """
        raw = {}
        if clinic is not None and isinstance(clinic.settings, dict):
            raw = clinic.settings.get("documents") or {}
            raw = raw.get("letterhead") or {}
        if not clinic:
            return {"name": "", "address": "", "phone": "", "email": "", "registration_number": ""}

        def pick(key: str, native: str) -> str:
            if raw.get(key):
                return str(raw[key])
            return native or ""

        address = ""
        if clinic.address:
            address = DocumentPDFService._format_address(clinic.address)
        return {
            "name": pick("name", clinic.name or "Dental Clinic"),
            "address": pick("address", address),
            "phone": pick("phone", clinic.phone or ""),
            "email": pick("email", clinic.email or ""),
            "registration_number": pick(
                "registration_number",
                clinic.tax_id or "",
            ),
            "logo": raw.get("logo") or "",
        }

    @staticmethod
    def _patient_birth(patient: Patient, locale: str) -> str:
        return (
            format_pdf_date(patient.date_of_birth, locale)
            if getattr(patient, "date_of_birth", None)
            else "-"
        )

    @staticmethod
    def _generate_html(
        document: GeneratedDocument,
        clinic: Clinic,
        patient: Patient,
        locale: str,
        issued_by: str,
    ) -> str:
        labels = _LABELS.get(locale, _LABELS["en"])
        header = DocumentPDFService._letterhead(clinic)

        doc_title = labels.get(document.document_type, document.document_type)
        try:
            clinic_tz = ZoneInfo(clinic.timezone or "UTC")
        except (KeyError, ValueError):
            clinic_tz = UTC
        issued_at = format_pdf_datetime(datetime.now(clinic_tz), locale)

        patient_name = ""
        patient_id = ""
        if patient is not None:
            patient_name = f"{patient.first_name} {patient.last_name}"
            patient_id = str(patient.id)

        content = document.content or {}
        logo_html = ""
        if header.get("logo"):
            logo_html = (
                '<div class="clinic-logo">'
                f'<img src="{escape(str(header["logo"]))}" alt="logo" />'
                "</div>"
            )

        clinic_lines = [
            escape(header["address"]),
            escape(header["phone"]) if header["phone"] else "",
            escape(header["email"]) if header["email"] else "",
        ]
        if header.get("registration_number"):
            clinic_lines.append(
                f"{labels['registration_number']}: {escape(header['registration_number'])}"
            )
        clinic_details_html = "<br>".join(line for line in clinic_lines if line)

        issued_by_html = ""
        if issued_by:
            issued_by_html = (
                f'<div class="info-group"><div class="info-label">{labels["issued_by"]}</div>'
                f'<div class="info-value">{escape(issued_by)}</div></div>'
            )

        body_html = DocumentPDFService._render_body(document.document_type, content, labels)
        if document.document_type == "informed_consent" and getattr(document, "title", None):
            # The evidence carries what the patient saw and signed (#1040).
            body_html = f'<h2 class="consent-title">{escape(document.title)}</h2>' + body_html

        # Arabic is a supported PDF locale, so the page has to be mirrored —
        # the same attribute billing's invoice sets (#524).
        rtl_attr = ' dir="rtl"' if locale == "ar" else ""

        return f"""<!DOCTYPE html>
        <html lang="{locale}"{rtl_attr}>
        <head>
            <meta charset="UTF-8">
            <title>{escape(doc_title)} — {escape(patient_name)}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                /* The bottom margin is the footer's: text never flows into it (#1039). */
                @page {{ margin: 20mm 20mm 30mm; }}
                body {{
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    font-size: 11pt; line-height: 1.4; color: #333;
                }}
                .header {{
                    display: flex; justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 30px; padding-bottom: 20px;
                    border-bottom: 2px solid #2563eb;
                }}
                .clinic-info {{ max-width: 60%; }}
                .clinic-logo {{ margin-bottom: 8px; }}
                .clinic-logo img {{ max-height: 24mm; max-width: 50mm; }}
                .clinic-name {{ font-size: 18pt; font-weight: bold; color: #1e40af; margin-bottom: 5px; }}
                .clinic-details {{ font-size: 9pt; color: #666; }}
                .doc-title {{ font-size: 16pt; font-weight: bold; color: #1e40af; text-align: right; }}
                .consent-title {{ font-size: 13pt; margin-bottom: 12px; overflow-wrap: anywhere; }}
                .section {{ margin-bottom: 25px; }}
                .section-title {{
                    font-size: 11pt; font-weight: bold; color: #1e40af;
                    margin-bottom: 10px; padding-bottom: 5px;
                    border-bottom: 1px solid #e5e7eb;
                }}
                /* Wrap metadata rather than clipping patient or issuer details. */
                .meta {{ display: flex; flex-wrap: wrap; }}
                .info-group {{ width: 48%; min-width: 0; margin-bottom: 8px; overflow-wrap: anywhere; }}
                .info-label {{ font-size: 9pt; color: #666; margin-bottom: 2px; }}
                .info-value {{ font-weight: 500; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                th {{
                    background: #f3f4f6; padding: 8px; text-align: left;
                    font-size: 9pt; font-weight: 600; color: #374151;
                    border-bottom: 2px solid #e5e7eb;
                }}
                td {{ padding: 8px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
                tr:last-child td {{ border-bottom: none; }}
                .notes-content {{ background: #f9fafb; padding: 12px; border-radius: 8px; font-size: 10pt; }}
                .footer {{
                    position: fixed; bottom: -20mm; left: 0; right: 0;
                    font-size: 8pt; color: #9ca3af; text-align: center;
                    border-top: 1px solid #e5e7eb; padding-top: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="clinic-info">
                    {logo_html}
                    <div class="clinic-name">{escape(header["name"])}</div>
                    <div class="clinic-details">
                        {clinic_details_html}
                    </div>
                </div>
                <div>
                    <div class="doc-title">{escape(doc_title)}</div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">{labels["patient"]}</div>
                <div class="meta">
                    <div class="info-group">
                        <div class="info-label">{labels["patient"]}</div>
                        <div class="info-value">{escape(patient_name)}</div>
                    </div>
                    <div class="info-group">
                        <div class="info-label">{labels["dob"]}</div>
                        <div class="info-value">{DocumentPDFService._patient_birth(patient, locale)}</div>
                    </div>
                    <div class="info-group">
                        <div class="info-label">{labels["issued"]}</div>
                        <div class="info-value">{issued_at}</div>
                    </div>
                    {issued_by_html}
                    <div class="info-group">
                        <div class="info-label">ID</div>
                        <div class="info-value">{patient_id}</div>
                    </div>
                </div>
            </div>

            {body_html}

            <div class="footer">
                {escape(labels["generated_by"])} | {escape(header["name"])}
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _render_body(document_type: str, content: dict, labels: dict) -> str:
        """Render the type-specific content block.

        Content is user-entered free text (plus structured medication
        rows), so every value is escaped before it reaches the template.
        """

        def esc(value: object) -> str:
            return escape("" if value is None else str(value))

        if document_type == "informed_consent":
            # Only validated PNG data URIs reach this renderer through the signing flow.
            signature = esc(content.get("signature"))
            title = (
                labels["consent_revocation"]
                if content.get("purpose") == "revoke"
                else labels["informed_consent"]
            )
            relationship = labels.get(f"consent_{content.get('relationship_to_patient', '')}", "")
            return (
                f'<div class="section"><div class="section-title">{esc(title)}</div>'
                + (
                    f"<p><strong>{esc(labels['consent_draft'])}</strong></p>"
                    if not signature
                    else ""
                )
                + f'<div class="notes-content" style="white-space:pre-wrap">{esc(content.get("text"))}</div></div>'
                + (
                    f"<p>{esc(labels['consent_revocation_text'])}</p>"
                    if content.get("purpose") == "revoke"
                    else ""
                )
                + (
                    f"<p>{esc(content.get('signer_name'))} · {esc(relationship)} · {esc(content.get('signed_at'))}</p>"
                    + f'<img src="{signature}" alt="Signature" style="max-width:250px;max-height:100px" />'
                    if signature
                    else ""
                )
            )

        if document_type == "prescription":
            rows = ""
            for med in content.get("medications") or []:
                if not isinstance(med, dict):
                    continue
                rows += (
                    "<tr>"
                    f"<td>{esc(med.get('name'))}</td>"
                    f"<td>{esc(med.get('dose'))}</td>"
                    f"<td>{esc(med.get('frequency'))}</td>"
                    f"<td>{esc(med.get('duration'))}</td>"
                    "</tr>"
                )
            meds_html = (
                f"<table><thead><tr>"
                f"<th>{labels['medName']}</th><th>{labels['dose']}</th>"
                f"<th>{labels['frequency']}</th><th>{labels['duration']}</th>"
                f"</tr></thead><tbody>{rows}</tbody></table>"
                if rows
                else '<div class="notes-content">-</div>'
            )
            return (
                f'<div class="section"><div class="section-title">{labels["diagnosis"]}</div>'
                f'<div class="notes-content">{esc(content.get("diagnosis"))}</div></div>'
                f'<div class="section"><div class="section-title">{labels["medications"]}</div>'
                f"{meds_html}</div>"
                + (
                    f'<div class="section"><div class="section-title">{labels["notes"]}</div>'
                    f'<div class="notes-content">{esc(content.get("notes"))}</div></div>'
                    if content.get("notes")
                    else ""
                )
            )

        if document_type == "medical_certificate":
            return (
                _block(labels["diagnosis"], content.get("diagnosis"))
                + _block(labels["description"], content.get("description"))
                + _block(labels["recommendations"], content.get("recommendations"))
            )

        if document_type == "referral":
            return (
                _block(labels["referred_to"], content.get("referred_to"))
                + _block(labels["specialty"], content.get("specialty"))
                + _block(labels["reason"], content.get("reason"))
                + _block(labels["clinical_summary"], content.get("clinical_summary"))
                + _block(labels["notes"], content.get("notes"))
            )

        if document_type == "radiology_request":
            return (
                _block(labels["exam_type"], content.get("exam_type"))
                + _block(labels["region"], content.get("region"))
                + _block(labels["clinical_question"], content.get("clinical_question"))
                + _block(labels["notes"], content.get("notes"))
            )

        return ""

    @staticmethod
    def _html_to_pdf(html_content: str) -> bytes:
        """Convert HTML to PDF with WeasyPrint; raw HTML fallback."""
        try:
            from weasyprint import HTML

            pdf_buffer = BytesIO()
            HTML(string=html_content).write_pdf(pdf_buffer)
            return pdf_buffer.getvalue()
        except ImportError:
            return html_content.encode("utf-8")


def _block(title: str, value: object) -> str:
    """Render a titled content block with an escaped value."""
    text = "" if value is None else str(value)
    if not text.strip():
        return ""
    return (
        f'<div class="section"><div class="section-title">{escape(title)}</div>'
        f'<div class="notes-content">{escape(text)}</div></div>'
    )
