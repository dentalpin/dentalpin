"""Patient-facing labels for the recall reason codes (#1135).

The reminder email printed the stored code ("(ortho_review)"). These are
the same words the recalls UI shows for each code
(``recalls/frontend/i18n/locales/*.json`` → ``recalls.reasons``), copied
per locale so the backend can render them; a test keeps the two in step.
``pt-BR`` has no wording of its own and falls back to ``pt``, as the
frontend does.
"""

from __future__ import annotations

REASON_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "hygiene": "Hygiene",
        "checkup": "Check-up",
        "ortho_review": "Ortho review",
        "implant_review": "Implant review",
        "post_op": "Post-op",
        "treatment_followup": "Treatment follow-up",
        "other": "Other",
    },
    "es": {
        "hygiene": "Higiene",
        "checkup": "Revisión",
        "ortho_review": "Revisión ortodoncia",
        "implant_review": "Revisión implante",
        "post_op": "Postoperatorio",
        "treatment_followup": "Seguimiento de tratamiento",
        "other": "Otro",
    },
    "fr": {
        "hygiene": "Hygiène",
        "checkup": "Contrôle",
        "ortho_review": "Revue d'orthodontie",
        "implant_review": "Revue d'implant",
        "post_op": "Post-opératoire",
        "treatment_followup": "Suivi de traitement",
        "other": "Autre",
    },
    "de": {
        "hygiene": "Prophylaxe",
        "checkup": "Kontrolluntersuchung",
        "ortho_review": "KFO-Kontrolle",
        "implant_review": "Implantat-Kontrolle",
        "post_op": "Post-OP-Kontrolle",
        "treatment_followup": "Behandlungs-Nachsorge",
        "other": "Sonstiges",
    },
    "it": {
        "hygiene": "Igiene",
        "checkup": "Controllo",
        "ortho_review": "Controllo ortodontico",
        "implant_review": "Controllo implantare",
        "post_op": "Post-operatorio",
        "treatment_followup": "Follow-up del trattamento",
        "other": "Altro",
    },
    "pt": {
        "hygiene": "Higiene",
        "checkup": "Consulta de rotina",
        "ortho_review": "Revisão de ortodontia",
        "implant_review": "Revisão de implante",
        "post_op": "Pós-operatório",
        "treatment_followup": "Seguimento de tratamento",
        "other": "Outro",
    },
    "pl": {
        "hygiene": "Higienizacja",
        "checkup": "Przegląd",
        "ortho_review": "Kontrola ortodontyczna",
        "implant_review": "Kontrola implantu",
        "post_op": "Kontrola pozabiegowa",
        "treatment_followup": "Kontynuacja leczenia",
        "other": "Inne",
    },
    "hu": {
        "hygiene": "Szájhigiénia",
        "checkup": "Kontrollvizsgálat",
        "ortho_review": "Fogszabályozási kontroll",
        "implant_review": "Implantátum-kontroll",
        "post_op": "Posztoperatív kontroll",
        "treatment_followup": "Kezelés utánkövetése",
        "other": "Egyéb",
    },
    "ar": {
        "hygiene": "نظافة",
        "checkup": "فحص دوري",
        "ortho_review": "مراجعة تقويم",
        "implant_review": "مراجعة غرسة",
        "post_op": "ما بعد العملية",
        "treatment_followup": "متابعة العلاج",
        "other": "أخرى",
    },
    "hi": {
        "hygiene": "स्वच्छता",
        "checkup": "जाँच",
        "ortho_review": "ऑर्थो समीक्षा",
        "implant_review": "इम्प्लांट समीक्षा",
        "post_op": "शल्य चिकित्सा के बाद",
        "treatment_followup": "उपचार फ़ॉलो-अप",
        "other": "अन्य",
    },
    "ta": {
        "hygiene": "வாய்ச் சுகாதாரம்",
        "checkup": "வழக்கமான பரிசோதனை",
        "ortho_review": "பற்சீரமைப்பு பரிசீலனை",
        "implant_review": "பல் உள்வைப்பு பரிசீலனை",
        "post_op": "அறுவைச் சிகிச்சைக்குப் பிந்தைய பரிசோதனை",
        "treatment_followup": "சிகிச்சை தொடர்ச்சிப் பரிசோதனை",
        "other": "மற்றவை",
    },
    "te": {
        "hygiene": "దంత శుభ్రత",
        "checkup": "సాధారణ పరీక్ష",
        "ortho_review": "ఆర్థో సమీక్ష",
        "implant_review": "ఇంప్లాంట్ సమీక్ష",
        "post_op": "శస్త్రచికిత్స తర్వాత",
        "treatment_followup": "చికిత్స ఫాలో-అప్",
        "other": "ఇతర",
    },
}


def reason_label(code: str | None, locale: str) -> str | None:
    """The label for ``code`` in ``locale`` (``pt-BR`` → ``pt``, unknown
    locale → ``en``, as the email template itself falls back), or
    ``None`` for an unknown code so the template leaves it out."""
    if not code:
        return None
    labels = (
        REASON_LABELS.get(locale)
        or REASON_LABELS.get(locale.replace("_", "-").split("-")[0])
        or REASON_LABELS["en"]
    )
    return labels.get(code)
