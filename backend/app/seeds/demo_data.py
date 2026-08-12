"""Demo data definitions for DentalPin.

This module contains all the seed data used to populate a demo environment.
All UUIDs are fixed to allow consistent references and easier debugging.

Supports bilingual data (English and Spanish) via LANG setting.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

# =============================================================================
# Language Configuration
# =============================================================================

SupportedLang = Literal["es", "en", "fr", "ta"]
LANG: SupportedLang = "en"  # Default language


def set_language(lang: SupportedLang) -> None:
    """Set the language for seed data."""
    global LANG
    LANG = lang


def t(translations: dict[str, str]) -> str:
    """Get translated string for current language."""
    return translations.get(LANG, translations.get("en", ""))


# =============================================================================
# Fixed UUIDs for consistent references
# =============================================================================

# Clinic
CLINIC_ID = UUID("a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11")

# Users
USER_ADMIN_ID = UUID("b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22")
USER_DENTIST_ID = UUID("b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a23")
USER_HYGIENIST_ID = UUID("b2eebc99-9c0b-4ef8-bb6d-6bb9bd380a24")
USER_ASSISTANT_ID = UUID("b3eebc99-9c0b-4ef8-bb6d-6bb9bd380a25")
USER_RECEPTIONIST_ID = UUID("b4eebc99-9c0b-4ef8-bb6d-6bb9bd380a26")

# Memberships
MEMBERSHIP_ADMIN_ID = UUID("c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33")
MEMBERSHIP_DENTIST_ID = UUID("c1eebc99-9c0b-4ef8-bb6d-6bb9bd380a34")
MEMBERSHIP_HYGIENIST_ID = UUID("c2eebc99-9c0b-4ef8-bb6d-6bb9bd380a35")
MEMBERSHIP_ASSISTANT_ID = UUID("c3eebc99-9c0b-4ef8-bb6d-6bb9bd380a36")
MEMBERSHIP_RECEPTIONIST_ID = UUID("c4eebc99-9c0b-4ef8-bb6d-6bb9bd380a37")

# Patients (15 patients) - Using hex digits only (0-9, a-f)
PATIENT_IDS = [
    UUID("d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a40"),
    UUID("d1eebc99-9c0b-4ef8-bb6d-6bb9bd380a41"),
    UUID("d2eebc99-9c0b-4ef8-bb6d-6bb9bd380a42"),
    UUID("d3eebc99-9c0b-4ef8-bb6d-6bb9bd380a43"),
    UUID("d4eebc99-9c0b-4ef8-bb6d-6bb9bd380a44"),
    UUID("d5eebc99-9c0b-4ef8-bb6d-6bb9bd380a45"),
    UUID("d6eebc99-9c0b-4ef8-bb6d-6bb9bd380a46"),
    UUID("d7eebc99-9c0b-4ef8-bb6d-6bb9bd380a47"),
    UUID("d8eebc99-9c0b-4ef8-bb6d-6bb9bd380a48"),
    UUID("d9eebc99-9c0b-4ef8-bb6d-6bb9bd380a49"),
    UUID("daeebc99-9c0b-4ef8-bb6d-6bb9bd380a4a"),
    UUID("dbeebc99-9c0b-4ef8-bb6d-6bb9bd380a4b"),
    UUID("dceebc99-9c0b-4ef8-bb6d-6bb9bd380a4c"),
    UUID("ddeebc99-9c0b-4ef8-bb6d-6bb9bd380a4d"),
    UUID("deeebc99-9c0b-4ef8-bb6d-6bb9bd380a4e"),
]


# =============================================================================
# Bilingual Data Definitions
# =============================================================================


# Clinic data with translations
def get_clinic_data() -> dict:
    """Get clinic data in current language."""
    return {
        "id": CLINIC_ID,
        "name": t(
            {
                "es": "Clínica Dental Demo",
                "en": "Demo Dental Clinic",
                "fr": "Clinique Dentaire Démo",
                "ta": "டெமோ பல் மருத்துவ கிளினிக்",
            }
        ),
        "tax_id": t({"es": "B12345678", "en": "12-3456789", "fr": "12-3456789", "ta": "33-1234567",}),
        "address": {
            "street": t(
                {"es": "Calle Gran Vía 123", "en": "123 Main Street", "fr": "123 Rue Principale", "ta": "123 மெயின் தெரு",}
            ),
            "city": t({"es": "Madrid", "en": "New York", "fr": "Paris", "ta": "சென்னை"}),
            "postal_code": t({"es": "28013", "en": "10001", "fr": "75001", "ta": "600001"}),
            "country": t({"es": "España", "en": "USA", "fr": "France", "ta": "இந்தியா"}),
        },
        "phone": t({"es": "+34 912 345 678", "en": "+1 (212) 555-0100", "fr": "+33 1 23 45 67 89", "ta": "+91 98401 23456"}),
        "email": "info@demo.clinic",
        "currency": t({"es": "EUR", "en": "USD", "fr": "EUR", "ta": "INR"}),
        "timezone": t({"es": "Europe/Madrid", "en": "America/New_York", "fr": "Europe/Paris", "ta": "Asia/Kolkata"}),
        "settings": {
            "slot_duration_min": 30,
            "working_hours": {
                "monday": {"morning": ["09:00", "14:00"], "afternoon": ["16:00", "20:00"]},
                "tuesday": {"morning": ["09:00", "14:00"], "afternoon": ["16:00", "20:00"]},
                "wednesday": {"morning": ["09:00", "14:00"], "afternoon": ["16:00", "20:00"]},
                "thursday": {"morning": ["09:00", "14:00"], "afternoon": ["16:00", "20:00"]},
                "friday": {"morning": ["09:00", "14:00"], "afternoon": ["16:00", "20:00"]},
            },
        },
        "cabinets": [
            {
                "name": t({"es": "Gabinete 1", "en": "Room 1", "fr": "Cabinet 1", "ta": "அறை 1"}),
                "color": "#3B82F6",
            },
            {
                "name": t({"es": "Gabinete 2", "en": "Room 2", "fr": "Cabinet 2", "ta": "அறை 2"}),
                "color": "#10B981",
            },
        ],
    }


# User names by language

USERS_I18N = {
    "admin": {
        "es": {"first_name": "Admin", "last_name": "Demo"},
        "en": {"first_name": "Admin", "last_name": "Demo"},
        "fr": {"first_name": "Admin", "last_name": "Démo"},
        "ta": {"first_name": "நிர்வாகி", "last_name": "டெமோ"},
    },
    "dentist": {
        "es": {"first_name": "María", "last_name": "García López"},
        "en": {"first_name": "Sarah", "last_name": "Johnson"},
        "fr": {"first_name": "Marie", "last_name": "Dubois Laurent"},
        "ta": {"first_name": "மீனா", "last_name": "குமார்"},
    },
    "hygienist": {
        "es": {"first_name": "Carlos", "last_name": "López Martínez"},
        "en": {"first_name": "Michael", "last_name": "Williams"},
        "fr": {"first_name": "Thomas", "last_name": "Moreau"},
        "ta": {"first_name": "அருண்", "last_name": "ரவி"},
    },
    "assistant": {
        "es": {"first_name": "Ana", "last_name": "Martínez Ruiz"},
        "en": {"first_name": "Emily", "last_name": "Davis"},
        "fr": {"first_name": "Camille", "last_name": "Petit"},
        "ta": {"first_name": "அனிதா", "last_name": "முருகன்"},
    },
    "receptionist": {
        "es": {"first_name": "Laura", "last_name": "Sánchez Pérez"},
        "en": {"first_name": "Jessica", "last_name": "Brown"},
        "fr": {"first_name": "Julie", "last_name": "Bernard"},
        "ta": {"first_name": "லதா", "last_name": "செல்வி"},
    },
}


def get_users_data() -> list[dict]:
    """Get users data in current language."""
    return [
        {
            "id": USER_ADMIN_ID,
            "email": "admin@demo.clinic",
            "first_name": USERS_I18N["admin"][LANG]["first_name"],
            "last_name": USERS_I18N["admin"][LANG]["last_name"],
            "role": "admin",
            "membership_id": MEMBERSHIP_ADMIN_ID,
        },
        {
            "id": USER_DENTIST_ID,
            "email": "dentist@demo.clinic",
            "first_name": USERS_I18N["dentist"][LANG]["first_name"],
            "last_name": USERS_I18N["dentist"][LANG]["last_name"],
            "professional_id": t({"es": "28/12345", "en": "DDS-12345", "fr": "DF-12345"}),
            "role": "dentist",
            "membership_id": MEMBERSHIP_DENTIST_ID,
        },
        {
            "id": USER_HYGIENIST_ID,
            "email": "hygienist@demo.clinic",
            "first_name": USERS_I18N["hygienist"][LANG]["first_name"],
            "last_name": USERS_I18N["hygienist"][LANG]["last_name"],
            "professional_id": t({"es": "28/54321", "en": "RDH-54321", "fr": "OEF-54321"}),
            "role": "hygienist",
            "membership_id": MEMBERSHIP_HYGIENIST_ID,
        },
        {
            "id": USER_ASSISTANT_ID,
            "email": "assistant@demo.clinic",
            "first_name": USERS_I18N["assistant"][LANG]["first_name"],
            "last_name": USERS_I18N["assistant"][LANG]["last_name"],
            "role": "assistant",
            "membership_id": MEMBERSHIP_ASSISTANT_ID,
        },
        {
            "id": USER_RECEPTIONIST_ID,
            "email": "receptionist@demo.clinic",
            "first_name": USERS_I18N["receptionist"][LANG]["first_name"],
            "last_name": USERS_I18N["receptionist"][LANG]["last_name"],
            "role": "receptionist",
            "membership_id": MEMBERSHIP_RECEPTIONIST_ID,
        },
    ]


# Patient data by language (phone and email as dicts for lazy translation)
# emergency_contact: {name, relationship, phone, email, is_legal_guardian}
# medical_history: {allergies[], is_pregnant, pregnancy_week, is_lactating,
#                   is_on_anticoagulants, anticoagulant_medication, inr_value,
#                   adverse_reactions_to_anesthesia, anesthesia_reaction_details,
#                   systemic_diseases[]}
PATIENTS_I18N = [
    # Children/Teens
    {
        "id": PATIENT_IDS[0],
        "es": {
            "first_name": "Pablo",
            "last_name": "Fernández García",
            "notes": "Paciente pediátrico. Primera visita para revisión.",
        },
        "en": {
            "first_name": "Ethan",
            "last_name": "Miller",
            "notes": "Pediatric patient. First visit for checkup.",
        },
        "fr": {
            "first_name": "Hugo",
            "last_name": "Morel",
            "notes": "Patient pédiatrique. Première visite pour contrôle.",
        },
        "ta": {
            "first_name": "லூசியா",
            "last_name": "ரோட்ரிக்ஸ் சான்செஸ்",
            "notes": "பற்சீரமைப்பு சிகிச்சை நடைபெற்று வருகிறது.",
        },
        "phone": {"es": "+34 612 345 001", "en": "+1 (212) 555-0001", "fr": "+33 6 12 34 56 01", "ta": "+91 44 6123 4001"},
        "email": None,
        "date_of_birth": date(2016, 3, 15),
        "emergency_contact": {
            "es": {
                "name": "Carlos Fernández",
                "relationship": "Padre",
                "phone": "+34 612 345 100",
                "email": "carlos.fernandez@email.com",
                "is_legal_guardian": True,
            },
            "en": {
                "name": "John Miller",
                "relationship": "Father",
                "phone": "+1 (212) 555-0100",
                "email": "john.miller@email.com",
                "is_legal_guardian": True,
            },
            "fr": {
                "name": "Marc Morel",
                "relationship": "Père",
                "phone": "+33 6 12 34 56 51",
                "email": "marc.morel@email.com",
                "is_legal_guardian": True,
            },
            "ta": {
                "name": "கார்லோஸ் பெர்னாண்டஸ்",
                "relationship": "தந்தை",
                "phone": "+91 44 6123 4100",
                "email": "carlos.fernandez@email.com",
                "is_legal_guardian": True,
            }
        },
        "medical_history": {
            "allergies": [],
            "systemic_diseases": [],
        },
    },
    {
        "id": PATIENT_IDS[1],
        "es": {
            "first_name": "Lucía",
            "last_name": "Rodríguez Sánchez",
            "notes": "Tratamiento de ortodoncia en curso.",
        },
        "en": {
            "first_name": "Olivia",
            "last_name": "Wilson",
            "notes": "Orthodontic treatment in progress.",
        },
        "fr": {
            "first_name": "Léa",
            "last_name": "Laurent",
            "notes": "Traitement d'orthodontie en cours.",
        },
        "ta": {
            "first_name": "ஓலிவியா",
            "last_name": "வில்சன்",
            "notes": "ஒர்த்தோடான்டிக் சிகிச்சை நடைபெற்று வருகிறது.",
        },
        "phone": {"es": "+34 612 345 002", "en": "+1 (212) 555-0002", "fr": "+33 6 12 34 56 02", "ta": "+91 44 6123 4002"},
        "email": {
            "es": "lucia.rodriguez@email.com",
            "en": "olivia.wilson@email.com",
            "fr": "lea.laurent@email.com",
        },
        "date_of_birth": date(2010, 7, 22),
        "emergency_contact": {
            "es": {
                "name": "María Sánchez",
                "relationship": "Madre",
                "phone": "+34 612 345 101",
                "email": "maria.sanchez@email.com",
                "is_legal_guardian": True,
            },
            "en": {
                "name": "Sarah Wilson",
                "relationship": "Mother",
                "phone": "+1 (212) 555-0101",
                "email": "sarah.wilson@email.com",
                "is_legal_guardian": True,
            },
            "fr": {
                "name": "Isabelle Laurent",
                "relationship": "Mère",
                "phone": "+33 6 12 34 56 52",
                "email": "isabelle.laurent@email.com",
                "is_legal_guardian": True,
            },
            "ta": {
                "name": "சரா வில்சன்",
                "relationship": "தாய்",
                "phone": "+91 44 6123 4101",
                "email": "sarah.wilson@email.com",
                "is_legal_guardian": True,
            }
        },
        "medical_history": {
            "allergies": [],
            "systemic_diseases": [],
        },
    },
    # Young Adults
    {
        "id": PATIENT_IDS[2],
        "es": {"first_name": "Miguel", "last_name": "González Torres", "notes": None},
        "en": {"first_name": "James", "last_name": "Anderson", "notes": None},
        "fr": {"first_name": "Lucas", "last_name": "Rousseau", "notes": None},
        "ta": {"first_name": "ஜேம்ஸ்", "last_name": "ஆண்டர்சன்", "notes": None},
        "phone": {"es": "+34 612 345 003", "en": "+1 (212) 555-0003", "fr": "+33 6 12 34 56 03", "ta": "+91 44 6123 4003"},
        "email": {
            "es": "miguel.gonzalez@email.com",
            "en": "james.anderson@email.com",
            "fr": "lucas.rousseau@email.com",
            "ta": "james.anderson@email.com",
        },
        "date_of_birth": date(1998, 11, 8),
        "emergency_contact": {
            "es": {
                "name": "Laura González",
                "relationship": "Hermana",
                "phone": "+34 612 345 102",
                "email": None,
                "is_legal_guardian": False,
            },
            "en": {
                "name": "Laura Anderson",
                "relationship": "Sister",
                "phone": "+1 (212) 555-0102",
                "email": None,
                "is_legal_guardian": False,
            },
            "fr": {
                "name": "Claire Rousseau",
                "relationship": "Soeur",
                "phone": "+33 6 12 34 56 53",
                "email": None,
                "is_legal_guardian": False,
            },
            "ta": {
                "name": "லௌரா ஆண்டர்சன்",
                "relationship": "சகோதரி",
                "phone": "+91 44 6123 4102",
                "email": None,
                "is_legal_guardian": False,
            }
        },
        "medical_history": {
            "allergies": [],
            "systemic_diseases": [],
        },
    },
    {
        "id": PATIENT_IDS[3],
        "es": {
            "first_name": "Carmen",
            "last_name": "Díaz Moreno",
            "notes": "Sensibilidad dental. Usar anestesia con precaución.",
        },
        "en": {
            "first_name": "Emma",
            "last_name": "Taylor",
            "notes": "Dental sensitivity. Use anesthesia with caution.",
        },
        "fr": {
            "first_name": "Chloé",
            "last_name": "Bertrand",
            "notes": "Sensibilité dentaire. Utiliser l'anesthésie avec précaution.",
        },
        "ta": {
            "first_name": "எம்மா",
            "last_name": "டேலர்",
            "notes": "தோல்கள் உணர்வு. மெதுவாக மெதுவாக பயன்படுத்தவும்.",
        },
        "phone": {"es": "+34 612 345 004", "en": "+1 (212) 555-0004", "fr": "+33 6 12 34 56 04", "ta": "+91 44 6123 4004"},
        "email": {
            "es": "carmen.diaz@email.com",
            "en": "emma.taylor@email.com",
            "fr": "chloe.bertrand@email.com",
            "ta": "emma.taylor@email.com",
        },
        "date_of_birth": date(1995, 5, 30),
        "emergency_contact": {
            "es": {
                "name": "Pedro Díaz",
                "relationship": "Esposo",
                "phone": "+34 612 345 103",
                "email": "pedro.diaz@email.com",
                "is_legal_guardian": False,
            },
            "en": {
                "name": "Peter Taylor",
                "relationship": "Husband",
                "phone": "+1 (212) 555-0103",
                "email": "peter.taylor@email.com",
                "is_legal_guardian": False,
            },
            "fr": {
                "name": "Jean-Pierre Bertrand",
                "relationship": "Mari",
                "phone": "+33 6 12 34 56 54",
                "email": "jean-pierre.bertrand@email.com",
                "is_legal_guardian": False,
            },
            "ta": {
                "name": "பீட்டர் டேலர்",
                "relationship": "மனைவி",
                "phone": "+91 44 6123 4103",
                "email": "peter.taylor@email.com",
                "is_legal_guardian": False,
            },
        },
        "medical_history": {
            "allergies": [
                {
                    "name": {"es": "Látex", "en": "Latex", "fr": "Latex"},
                    "severity": "medium",
                    "reaction": {
                        "es": "Irritación cutánea",
                        "en": "Skin irritation",
                        "fr": "Irritation cutanée",
                    },
                },
            ],
            "adverse_reactions_to_anesthesia": True,
            "anesthesia_reaction_details": {
                "es": "Mareos y náuseas post-anestesia",
                "en": "Dizziness and nausea post-anesthesia",
                "fr": "Vertige et nausée post-anesthésie",
            },
            "systemic_diseases": [],
        },
    },
    {
        "id": PATIENT_IDS[4],
        "es": {"first_name": "David", "last_name": "Martín López", "notes": None},
        "en": {"first_name": "William", "last_name": "Thomas", "notes": None},
        "fr": {"first_name": "Alexandre", "last_name": "Moreau", "notes": None},
        "ta": {"first_name": "வில்லியம்", "last_name": "தாமஸ்", "notes": None},
        "phone": {"es": "+34 612 345 005", "en": "+1 (212) 555-0005", "fr": "+33 6 12 34 56 05", "ta": "+91 44 6123 4005"},
        "email": None,
        "date_of_birth": date(1992, 2, 14),
        "emergency_contact": None,
        "medical_history": {
            "allergies": [],
            "systemic_diseases": [],
        },
    },
    # Adults
    {
        "id": PATIENT_IDS[5],
        "es": {
            "first_name": "Elena",
            "last_name": "Ruiz Hernández",
            "notes": "Embarazada (tercer trimestre). Evitar radiografías.",
        },
        "en": {
            "first_name": "Sophia",
            "last_name": "Martinez",
            "notes": "Pregnant (third trimester). Avoid X-rays.",
        },
        "fr": {
            "first_name": "Manon",
            "last_name": "Lefebvre",
            "notes": "Enceinte (troisième trimestre). Éviter les radiographies.",
        },
        "ta": {
            "first_name": "சோபியா",
            "last_name": "மார்டினேஸ்",
            "notes": "கர்ப்பம் (மூன்றாம் காலம்). எக்ஸ்-ரேகளைத் தவிர்க்கவும்.",
        },
        "phone": {"es": "+34 612 345 006", "en": "+1 (212) 555-0006", "fr": "+33 6 12 34 56 06", "ta": "+91 44 6123 4006"},
        "email": {
            "es": "elena.ruiz@email.com",
            "en": "sophia.martinez@email.com",
            "fr": "manon.lefebvre@email.com",
            "ta": "sophia.martinez@email.com",
        },
        "date_of_birth": date(1985, 9, 3),
        "emergency_contact": {
            "es": {
                "name": "Andrés Ruiz",
                "relationship": "Esposo",
                "phone": "+34 612 345 104",
                "email": "andres.ruiz@email.com",
                "is_legal_guardian": False,
            },
            "en": {
                "name": "Andrew Martinez",
                "relationship": "Husband",
                "phone": "+1 (212) 555-0104",
                "email": "andrew.martinez@email.com",
                "is_legal_guardian": False,
            },
            "fr": {
                "name": "Antoine Lefebvre",
                "relationship": "Mari",
                "phone": "+33 6 12 34 56 55",
                "email": "antoine.lefebvre@email.com",
                "is_legal_guardian": False,
            },
            "ta": {
                "name": "அந்திரூ மார்டினேஸ்",
                "relationship": "மனைவி",
                "phone": "+91 44 6123 4104",
                "email": "andrew.martinez@email.com",
                "is_legal_guardian": False,
            },
        },
        "medical_history": {
            "allergies": [],
            "is_pregnant": True,
            "pregnancy_week": 32,
            "systemic_diseases": [],
        },
    },
    {
        "id": PATIENT_IDS[6],
        "es": {
            "first_name": "Javier",
            "last_name": "Sánchez Muñoz",
            "notes": "Diabético tipo 2. Control de cicatrización.",
        },
        "en": {
            "first_name": "Daniel",
            "last_name": "Garcia",
            "notes": "Type 2 diabetic. Monitor healing.",
        },
        "fr": {
            "first_name": "Nicolas",
            "last_name": "Simon",
            "notes": "Diabétique de type 2. Surveillance de la cicatrisation.",
        },
        "ta": {
            "first_name": "டானியல்",
            "last_name": "கார்க்கி",
            "notes": "டைப்பு 2 பிச்சை. சிகிச்சையை கண்காணிக்கவும்.",
        },
        "phone": {"es": "+34 612 345 007", "en": "+1 (212) 555-0007", "fr": "+33 6 12 34 56 07", "ta": "+91 44 6123 4007"},
        "email": {
            "es": "javier.sanchez@email.com",
            "en": "daniel.garcia@email.com",
            "fr": "nicolas.simon@email.com",
            "ta": "daniel.garcia@email.com",
        },
        "date_of_birth": date(1980, 12, 25),
        "emergency_contact": {
            "es": {
                "name": "Ana Muñoz",
                "relationship": "Esposa",
                "phone": "+34 612 345 105",
                "email": "ana.munoz@email.com",
                "is_legal_guardian": False,
            },
            "en": {
                "name": "Anna Garcia",
                "relationship": "Wife",
                "phone": "+1 (212) 555-0105",
                "email": "anna.garcia@email.com",
                "is_legal_guardian": False,
            },
            "fr": {
                "name": "Nathalie Simon",
                "relationship": "Épouse",
                "phone": "+33 6 12 34 56 56",
                "email": "nathalie.simon@email.com",
                "is_legal_guardian": False,
            },
            "ta": {
                "name": "அன்னா கார்க்கி",
                "relationship": "மனைவி",
                "phone": "+91 44 6123 4105",
                "email": "anna.garcia@email.com",
                "is_legal_guardian": False,
            },
        },
        "medical_history": {
            "allergies": [],
            "systemic_diseases": [
                {
                    "name": {
                        "es": "Diabetes Mellitus Tipo 2",
                        "en": "Type 2 Diabetes Mellitus",
                        "fr": "Diabète de type 2",
                        "ta": "வகை 2 நீரிழிவு நோய்",
                    },
                    "is_critical": True,
                    "notes": {
                        "es": "Controlada con metformina. HbA1c: 7.2%",
                        "en": "Controlled with metformin. HbA1c: 7.2%",
                        "fr": "Contrôlé avec metformine. HbA1c : 7,2%",
                        "ta": "மெத்த்போர்மின் மூலம் கட்டுப்பாடு செய்யப்பட்டது. HbA1c: 7.2%",
                    },
                },
            ],
        },
    },
    {
        "id": PATIENT_IDS[7],
        "es": {"first_name": "Isabel", "last_name": "López Navarro", "notes": None},
        "en": {"first_name": "Mia", "last_name": "Robinson", "notes": None},
        "fr": {"first_name": "Clémentine", "last_name": "Michel", "notes": None},
        "ta": {"first_name": "மியா", "last_name": "ராபின்ஸன்", "notes": None},
        "phone": {"es": "+34 612 345 008", "en": "+1 (212) 555-0008", "fr": "+33 6 12 34 56 08", "ta": "+91 44 2432 1348"},
        "email": None,
        "date_of_birth": date(1978, 6, 17),
        "emergency_contact": {
            "es": {
                "name": "Roberto López",
                "relationship": "Hermano",
                "phone": "+34 612 345 106",
                "email": None,
                "is_legal_guardian": False,
            },
            "en": {
                "name": "Robert Robinson",
                "relationship": "Brother",
                "phone": "+1 (212) 555-0106",
                "email": None,
                "is_legal_guardian": False,
            },
            "fr": {
                "name": "Philippe Michel",
                "relationship": "Frère",
                "phone": "+33 6 12 34 56 57",
                "email": None,
                "is_legal_guardian": False,
            },
            "ta": {
                "name": "ராபர்ட் ராபின்ஸன்",
                "relationship": "சகோதரர்",
                "phone": "+91 44 2432 1348",
                "email": None,
                "is_legal_guardian": False,
            },
        },
        "medical_history": {
            "allergies": [],
            "is_lactating": True,
            "systemic_diseases": [],
        },
    },
    {
        "id": PATIENT_IDS[8],
        "es": {
            "first_name": "Francisco",
            "last_name": "García Romero",
            "notes": "Alérgico a penicilina.",
        },
        "en": {
            "first_name": "Alexander",
            "last_name": "Clark",
            "notes": "Allergic to penicillin.",
        },
        "fr": {
            "first_name": "Guillaume",
            "last_name": "Laurent",
            "notes": "Allergique à la pénicilline.",
        },
        "ta": {
            "first_name": "அலெக்சாண்டர்",
            "last_name": "கிளார்க்",
            "notes": "பெனிசிலினுக்கு அலர்ஜி.",
        },
        "phone": {"es": "+34 612 345 009", "en": "+1 (212) 555-0009", "fr": "+33 6 12 34 56 09"},
        "email": {
            "es": "francisco.garcia@email.com",
            "en": "alexander.clark@email.com",
            "fr": "guillaume.laurent@email.com",
            "ta": "alexander.clark@email.com",
        },
        "date_of_birth": date(1975, 4, 9),
        "emergency_contact": {
            "es": {
                "name": "Marta Romero",
                "relationship": "Esposa",
                "phone": "+34 612 345 107",
                "email": "marta.romero@email.com",
                "is_legal_guardian": False,
            },
            "en": {
                "name": "Martha Clark",
                "relationship": "Wife",
                "phone": "+1 (212) 555-0107",
                "email": "martha.clark@email.com",
                "is_legal_guardian": False,
            },
            "fr": {
                "name": "Catherine Laurent",
                "relationship": "Épouse",
                "phone": "+33 6 12 34 56 58",
                "email": "catherine.laurent@email.com",
                "is_legal_guardian": False,
            },
            "ta": {
                "name": "கேத்தரின் லாரென்ட்",
                "relationship": "மனைவி",
                "phone": "+91 98765 43210",
                "email": "கேத்தரின்.லாரென்ட்@email.com",
                "is_legal_guardian": False,
            }
        },
        "medical_history": {
            "allergies": [
                {
                    "name": {"es": "Penicilina", "en": "Penicillin", "fr": "Pénicilline", "ta": "பெனிசிலின்",},
                    "severity": "critical",
                    "reaction": {"es": "Anafilaxia", "en": "Anaphylaxis", "fr": "Anaphylaxie",  "ta": "அனாபிலாக்சிஸ்"},
                },
                {
                    "name": {"es": "Amoxicilina", "en": "Amoxicillin", "fr": "Amoxicilline", "ta": "அமோக்சிலின்"},
                    "severity": "high",
                    "reaction": {
                        "es": "Urticaria severa",
                        "en": "Severe urticaria",
                        "fr": "Urticaire sévère",
                        "ta": "கடுமையான அர்டிகேரியா",
                    },
                },
            ],
            "systemic_diseases": [],
        },
    },
    {
        "id": PATIENT_IDS[9],
        "es": {
            "first_name": "Rosa",
            "last_name": "Martínez Jiménez",
            "notes": "Hipertensa. Verificar presión antes de procedimientos.",
        },
        "en": {
            "first_name": "Charlotte",
            "last_name": "Lewis",
            "notes": "Hypertensive. Check blood pressure before procedures.",
        },
        "fr": {
            "first_name": "Sophie",
            "last_name": "Garnier",
            "notes": "Hypertendue. Vérifier la tension avant les soins.",
        },
        "ta": {
            "first_name": "ரோசா",
            "last_name": "மார்டினேஸ் ஜிமீனேஸ்",
            "notes": "இரத்த அழுத்தம் உயர்ந்தது. செயல்பாடுகளுக்கு முன் இரத்த அழுத்தத்தை சரிபார்க்கவும்.",
        },
        "phone": {"es": "+34 612 345 010", "en": "+1 (212) 555-0010", "fr": "+33 6 12 34 56 10", "ta": "+91 44 2342 2345"},
        "email": {
            "es": "rosa.martinez@email.com",
            "en": "charlotte.lewis@email.com",
            "fr": "sophie.garnier@email.com",
            "ta": "charlotte.lewis@email.com",
        },
        "date_of_birth": date(1970, 8, 21),
        "emergency_contact": {
            "es": {
                "name": "Luis Jiménez",
                "relationship": "Esposo",
                "phone": "+34 612 345 108",
                "email": None,
                "is_legal_guardian": False,
            },
            "en": {
                "name": "Louis Lewis",
                "relationship": "Husband",
                "phone": "+1 (212) 555-0108",
                "email": None,
                "is_legal_guardian": False,
            },
            "fr": {
                "name": "Patrick Garnier",
                "relationship": "Mari",
                "phone": "+33 6 12 34 56 59",
                "email": None,
                "is_legal_guardian": False,
            },
            "ta": {
                "name": "Patrick Garnier",
                "relationship": "மனைவி",
                "phone": "+91 44 2342 2345",
                "email": None,
                "is_legal_guardian": False,
            },
        },
        "medical_history": {
            "allergies": [],
            "systemic_diseases": [
                {
                    "name": {
                        "es": "Hipertensión Arterial",
                        "en": "Arterial Hypertension",
                        "fr": "Hypertension artérielle",
                        "ta": "தமனி உயர் இரத்த அழுத்தம்",
                    },
                    "is_critical": True,
                    "notes": {
                        "es": "Tratamiento con enalapril 10mg/día. PA habitual: 130/85",
                        "en": "Treatment with enalapril 10mg/day. Usual BP: 130/85",
                        "fr": "Traitement par énalapril 10mg/j. PA habituelle : 130/85",
                        "ta": "எனலாப்ரில் 10 மி.கி./நாள் சிகிச்சை. வழக்கமான இரத்த அழுத்தம்: 130/85",
                    },
                },
            ],
        },
    },
    # Older Adults
    {
        "id": PATIENT_IDS[10],
        "es": {
            "first_name": "Antonio",
            "last_name": "Hernández Castro",
            "notes": "Prótesis parcial superior.",
        },
        "en": {
            "first_name": "Robert",
            "last_name": "Walker",
            "notes": "Upper partial denture.",
        },
        "fr": {
            "first_name": "François",
            "last_name": "David",
            "notes": "Prothèse partielle supérieure.",
        },
        "ta": {
            "first_name": "ஆண்டோனியோ",
            "last_name": "ஹெர்னாண்டேஸ் காஸ்ட்ரோ",
            "notes": "மேல் பகுதி போட்டி.",
        },
        "phone": {"es": "+34 612 345 011", "en": "+1 (212) 555-0011", "fr": "+33 6 12 34 56 11", "ta": "+91 44 2342 2346"},
        "email": None,
        "date_of_birth": date(1960, 1, 5),
        "emergency_contact": {
            "es": {
                "name": "Carmen Castro",
                "relationship": "Hija",
                "phone": "+34 612 345 109",
                "email": "carmen.castro@email.com",
                "is_legal_guardian": False,
            },
            "en": {
                "name": "Carmen Walker",
                "relationship": "Daughter",
                "phone": "+1 (212) 555-0109",
                "email": "carmen.walker@email.com",
                "is_legal_guardian": False,
            },
            "fr": {
                "name": "Marie-Anne David",
                "relationship": "Fille",
                "phone": "+33 6 12 34 56 60",
                "email": "marie-anne.david@email.com",
                "is_legal_guardian": False,
            },
            "ta": {
                "name": "மரியா-அன் டேவிட்",
                "relationship": "மகள்",
                "phone": "+91 44 2342 2346",
                "email": "marie-anne.david@email.com",
                "is_legal_guardian": False,
            },
        },
        "medical_history": {
            "allergies": [
                {
                    "name": {
                        "es": "Yodo",
                        "en": "Iodine",
                        "fr": "Iode",
                        "ta": "அயோடின்",
                    },
                    "severity": "medium",
                    "reaction": {
                        "es": "Erupción cutánea",
                        "en": "Skin rash",
                        "fr": "Éruption cutanée",
                        "ta": "தோல் தடிப்பு",
                    },
                },
            ],
            "systemic_diseases": [
                {
                    "name": {
                        "es": "Artrosis",
                        "en": "Osteoarthritis",
                        "fr": "Arthrose",
                        "ta": "எலும்பு மூட்டு தேய்மானம்",
                    },
                    "is_critical": False,
                    "notes": {
                        "es": "Afecta movilidad cervical",
                        "en": "Affects cervical mobility",
                        "fr": "Affecte la mobilité cervicale",
                        "ta": "கழுத்துப் பகுதியின் அசைவுத்திறனைப் பாதிக்கிறது",
                    },
                },
            ],
        },
    },
    {
        "id": PATIENT_IDS[11],
        "es": {
            "first_name": "María Teresa",
            "last_name": "Romero Vega",
            "notes": "Paciente con implantes. Revisión periódica.",
        },
        "en": {
            "first_name": "Patricia",
            "last_name": "Hall",
            "notes": "Patient with implants. Periodic review.",
        },
        "fr": {
            "first_name": "Anne-Marie",
            "last_name": "Bertrand",
            "notes": "Patiente avec implants. Révision périodique.",
        },
        "ta": {
            "first_name": "மரியா தெரேசா",
            "last_name": "ரோமேரோ வேகா",
            "notes": "இம்பில்ட்டுகளுடன் போதனை. காலநிலை சோதனை.",
        },
        "phone": {"es": "+34 612 345 012", "en": "+1 (212) 555-0012", "fr": "+33 6 12 34 56 12", "ta": "+91 44 2342 2347"},
        "email": None,
        "date_of_birth": date(1955, 10, 12),
        "emergency_contact": {
            "es": {
                "name": "Fernando Vega",
                "relationship": "Hijo",
                "phone": "+34 612 345 110",
                "email": "fernando.vega@email.com",
                "is_legal_guardian": False,
            },
            "en": {
                "name": "Fernando Hall",
                "relationship": "Son",
                "phone": "+1 (212) 555-0110",
                "email": "fernando.hall@email.com",
                "is_legal_guardian": False,
            },
            "fr": {
                "name": "Laurent Bertrand",
                "relationship": "Fils",
                "phone": "+33 6 12 34 56 61",
                "email": "laurent.bertrand@email.com",
                "is_legal_guardian": False,
            },
            "ta": {
                "name": "லாரன்ட் பெர்ட்ரான்",
                "relationship": "மகன்",
                "phone": "+91 44 2342 2347",
                "email": "laurent.bertrand@email.com",
                "is_legal_guardian": False,
            },
        },
        "medical_history": {
            "allergies": [],
            "systemic_diseases": [
                {
                    "name": {"es": "Osteoporosis", "en": "Osteoporosis", "fr": "Ostéoporose", "ta": "ஆஸ்டியோபோரோசிஸ்"},
                    "is_critical": False,
                    "notes": {
                        "es": "Tratamiento con bisfosfonatos. Precaución con extracciones.",
                        "en": "Treatment with bisphosphonates. Caution with extractions.",
                        "fr": "Traitement par bisphosphonates. Prudence avec les extractions.",
                        "ta": "பிஸ்பாஸ்போனேட் சிகிச்சை. பல் அகற்றும் சிகிச்சையில் கவனம் தேவை.",
                    },
                },
            ],
        },
    },
    {
        "id": PATIENT_IDS[12],
        "es": {
            "first_name": "José Luis",
            "last_name": "Muñoz Blanco",
            "notes": "Toma anticoagulantes. Coordinar con médico antes de extracciones.",
        },
        "en": {
            "first_name": "Richard",
            "last_name": "Allen",
            "notes": "On blood thinners. Coordinate with physician before extractions.",
        },
        "fr": {
            "first_name": "Pierre",
            "last_name": "Roux",
            "notes": "Prend des anticoagulants. Coordonné avec le médecin avant extractions.",
        },
        "ta": {
            "first_name": "ஜோசப் லூயிஸ்",
            "last_name": "முன்யோஸ் பிளாங்கோ",
            "notes": "இரத்தம் உறைவதைத் தடுக்கும் மருந்துகளை எடுத்துக்கொள்கிறார். பல் அகற்றும் சிகிச்சைக்கு முன் மருத்துவருடன் ஒருங்கிணைக்கவும்.",
        },
        "phone": {"es": "+34 612 345 013", "en": "+1 (212) 555-0013", "fr": "+33 6 12 34 56 13", "ta": "+91 44 2341 2342"},
        "email": {
            "es": "joseluis.munoz@email.com",
            "en": "richard.allen@email.com",
            "fr": "pierre.roux@email.com",
            "ta": "richard.allen@email.com"
        },
        "date_of_birth": date(1950, 3, 28),
        "emergency_contact": {
            "es": {
                "name": "Pilar Blanco",
                "relationship": "Esposa",
                "phone": "+34 612 345 111",
                "email": None,
                "is_legal_guardian": False,
            },
            "en": {
                "name": "Patricia Allen",
                "relationship": "Wife",
                "phone": "+1 (212) 555-0111",
                "email": None,
                "is_legal_guardian": False,
            },
            "fr": {
                "name": "Monique Roux",
                "relationship": "Épouse",
                "phone": "+33 6 12 34 56 62",
                "email": None,
                "is_legal_guardian": False,
            },
            "ta": {
                "name": "பாட்ரிஷியா ஏலன்",
                "relationship": "மனைவி",
                "phone": "+91 44 2341 2341",
                "email": None,
                "is_legal_guardian": False,
            }
        },
        "medical_history": {
            "allergies": [],
            "is_on_anticoagulants": True,
            "anticoagulant_medication": "Sintrom (Acenocumarol)",
            "inr_value": 2.5,
            "systemic_diseases": [
                {
                    "name": {
                        "es": "Fibrilación Auricular",
                        "en": "Atrial Fibrillation",
                        "fr": "Fibrillation auriculaire",
                        "ta": "ஏட்ரியல் ஃபைப்ரிலேஷன்",
                    },
                    "is_critical": True,
                    "notes": {
                        "es": "Anticoagulado. Requiere control INR antes de procedimientos.",
                        "en": "Anticoagulated. Requires INR control before procedures.",
                        "fr": "Anticoagulé. Contrôle INR requis avant les soins.",
                        "ta": "இரத்த உறைதலைத் தடுக்கும் மருந்து சிகிச்சையில் உள்ளார். சிகிச்சைக்கு முன் INR பரிசோதனை தேவை.",
                    },
                },
            ],
        },
    },
    {
        "id": PATIENT_IDS[13],
        "es": {"first_name": "Dolores", "last_name": "Vega Ortiz", "notes": None},
        "en": {"first_name": "Barbara", "last_name": "Young", "notes": None},
        "fr": {"first_name": "Catherine", "last_name": "Duval", "notes": None},
        "ta": {"first_name": "பாலா", "last_name": "யாங்", "notes": None},
        "phone": {"es": "+34 612 345 014", "en": "+1 (212) 555-0014", "fr": "+33 6 12 34 56 14", "ta": "+91 44 2341 2341"},
        "email": None,
        "date_of_birth": date(1948, 7, 7),
        "emergency_contact": {
            "es": {
                "name": "Jorge Vega",
                "relationship": "Hijo",
                "phone": "+34 612 345 112",
                "email": "jorge.vega@email.com",
                "is_legal_guardian": False,
            },
            "en": {
                "name": "George Young",
                "relationship": "Son",
                "phone": "+1 (212) 555-0112",
                "email": "george.young@email.com",
                "is_legal_guardian": False,
            },
            "fr": {
                "name": "Bernard Duval",
                "relationship": "Fils",
                "phone": "+33 6 12 34 56 63",
                "email": "bernard.duval@email.com",
                "is_legal_guardian": False,
            },
            "ta": {
                "name": "ஜார்ஜ் யாங்",
                "relationship": "மகன்",
                "phone": "+91 44 2341 2341",
                "email": "george.young@email.com",
                "is_legal_guardian": False,
            },
        },
        "medical_history": {
            "allergies": [],
            "systemic_diseases": [],
        },
    },
    {
        "id": PATIENT_IDS[14],
        "es": {
            "first_name": "Manuel",
            "last_name": "Castro Delgado",
            "notes": "Prótesis completa. Necesita ajustes frecuentes.",
        },
        "en": {
            "first_name": "Charles",
            "last_name": "King",
            "notes": "Complete denture. Requires frequent adjustments.",
        },
        "fr": {
            "first_name": "Philippe",
            "last_name": "Lambert",
            "notes": "Prothèse complète. Nécessite des ajustements fréquents.",
        },
        "ta": {
            "first_name": "சார்லஸ்",
            "last_name": "கிங்",
            "notes": "முழு மூத்து மாற்றம். அதிக சமயம் மாற்றம் தேவை.",
        },
        "phone": {"es": "+34 612 345 015", "en": "+1 (212) 555-0015", "fr": "+33 6 12 34 56 15", "ta": "+91 44 2341 2341"},
        "email": None,
        "date_of_birth": date(1945, 11, 19),
        "emergency_contact": {
            "es": {
                "name": "Teresa Delgado",
                "relationship": "Hija",
                "phone": "+34 612 345 113",
                "email": "teresa.delgado@email.com",
                "is_legal_guardian": False,
            },
            "en": {
                "name": "Teresa King",
                "relationship": "Daughter",
                "phone": "+1 (212) 555-0113",
                "email": "teresa.king@email.com",
                "is_legal_guardian": False,
            },
            "fr": {
                "name": "Sylvie Lambert",
                "relationship": "Fille",
                "phone": "+33 6 12 34 56 64",
                "email": "sylvie.lambert@email.com",
                "is_legal_guardian": False,
            },
            "ta": {
                "name": "சில்விய் லம்பெர்ட்",
                "relationship": "மகள்",
                "phone": "+91 44 2341 2341",
                "email": "sylvie.lambert@email.com",
                "is_legal_guardian": False,
            },
        },
        "medical_history": {
            "allergies": [
                {
                    "name": {"es": "AINEs", "en": "NSAIDs", "fr": "AINS", "ta": "NSAID மருந்துகள்",},
                    "severity": "high",
                    "reaction": {
                        "es": "Problemas gástricos severos",
                        "en": "Severe gastric problems",
                        "fr": "Problèmes gastriques sévères",
                        "ta": "கடுமையான வயிற்றுப் பிரச்சினைகள்",
                    },
                },
            ],
            "systemic_diseases": [
                {
                    "name": {
                        "es": "Insuficiencia Renal Crónica",
                        "en": "Chronic Kidney Disease",
                        "fr": "Insuffisance rénale chronique",
                        "ta": "நாள்பட்ட சிறுநீரக நோய்",
                    },
                    "is_critical": True,
                    "notes": {
                        "es": "Estadio 3. Ajustar dosis de medicamentos.",
                        "en": "Stage 3. Adjust medication doses.",
                        "fr": "Stade 3. Ajuster les doses de médicaments.",
                        "ta": "நிலை 3. மருந்துகளின் அளவைச் சரிசெய்யவும்.",
                    },
                },
                {
                    "name": {
                        "es": "Diabetes Mellitus Tipo 2",
                        "en": "Type 2 Diabetes Mellitus",
                        "fr": "Diabète de type 2",
                        "ta": "வகை 2 நீரிழிவு நோய்",
                    },
                    "is_critical": True,
                    "notes": {
                        "es": "Insulinodependiente",
                        "en": "Insulin-dependent",
                        "fr": "Insulino-dépendant",
                        "ta": "இன்சுலின் சார்ந்தது"
                    },
                },
            ],
        },
    },
]


def _translate_medical_history(mh: dict | None) -> dict | None:
    """Translate medical history fields that have language variants."""
    if not mh:
        return None

    result = {}

    # Copy simple fields
    for key in [
        "is_pregnant",
        "pregnancy_week",
        "is_lactating",
        "is_on_anticoagulants",
        "anticoagulant_medication",
        "inr_value",
        "adverse_reactions_to_anesthesia",
    ]:
        if key in mh:
            result[key] = mh[key]

    # Translate anesthesia_reaction_details
    if "anesthesia_reaction_details" in mh:
        details = mh["anesthesia_reaction_details"]
        result["anesthesia_reaction_details"] = t(details) if isinstance(details, dict) else details

    # Translate allergies
    if "allergies" in mh:
        result["allergies"] = []
        for allergy in mh["allergies"]:
            translated = {
                "name": t(allergy["name"])
                if isinstance(allergy["name"], dict)
                else allergy["name"],
                "severity": allergy["severity"],
            }
            if "reaction" in allergy:
                reaction = allergy["reaction"]
                translated["reaction"] = t(reaction) if isinstance(reaction, dict) else reaction
            result["allergies"].append(translated)

    # Translate systemic_diseases
    if "systemic_diseases" in mh:
        result["systemic_diseases"] = []
        for disease in mh["systemic_diseases"]:
            translated = {
                "name": t(disease["name"])
                if isinstance(disease["name"], dict)
                else disease["name"],
                "is_critical": disease.get("is_critical", False),
            }
            if "notes" in disease:
                notes = disease["notes"]
                translated["notes"] = t(notes) if isinstance(notes, dict) else notes
            result["systemic_diseases"].append(translated)

    return result


def get_patients_data() -> list[dict]:
    """Get patients data in current language."""
    patients = []
    for p in PATIENTS_I18N:
        # Handle phone: dict with translations or None
        phone = p["phone"]
        if isinstance(phone, dict):
            phone = t(phone)

        # Handle email: dict with translations, string, or None
        email = p["email"]
        if isinstance(email, dict):
            email = t(email)

        # Handle emergency_contact: dict with language keys or None
        emergency_contact = p.get("emergency_contact")
        if isinstance(emergency_contact, dict) and LANG in emergency_contact:
            emergency_contact = emergency_contact[LANG]

        # Handle medical_history: translate nested fields
        medical_history = _translate_medical_history(p.get("medical_history"))

        patient = {
            "id": p["id"],
            "first_name": p[LANG]["first_name"],
            "last_name": p[LANG]["last_name"],
            "phone": phone,
            "email": email,
            "date_of_birth": p["date_of_birth"],
            "notes": p[LANG]["notes"],
            # Consumed downstream by seed_demo._seed_patient_clinical to
            # populate the normalized patients_clinical_* tables (B.4).
            "emergency_contact": emergency_contact,
            "medical_history": medical_history,
            "legal_guardian": p.get("legal_guardian"),
        }
        patients.append(patient)
    return patients


# =============================================================================
# Scheduling helpers
# =============================================================================

# Time slots (morning and afternoon) used by the appointment generator.
MORNING_SLOTS = [
    "09:00",
    "09:30",
    "10:00",
    "10:30",
    "11:00",
    "11:30",
    "12:00",
    "12:30",
    "13:00",
    "13:30",
]
AFTERNOON_SLOTS = ["16:00", "16:30", "17:00", "17:30", "18:00", "18:30", "19:00", "19:30"]


# =============================================================================
# Odontogram Seed Data
# =============================================================================

# Fixed UUIDs for tooth records (for consistent references)
# Using format: e0eebc99-9c0b-4ef8-NNNN-6bb9bd380a00
TOOTH_RECORD_IDS = [
    UUID(f"e0eebc99-9c0b-4ef8-{i:04x}-6bb9bd380a00") for i in range(0xBB6D, 0xBB6D + 500)
]

TREATMENT_IDS = [
    UUID(f"f0eebc99-9c0b-4ef8-{i:04x}-6bb9bd380b00") for i in range(0xBB6D, 0xBB6D + 500)
]

# Permanent teeth numbers (FDI notation)
PERMANENT_TEETH = [
    18,
    17,
    16,
    15,
    14,
    13,
    12,
    11,  # Upper right
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,  # Upper left
    38,
    37,
    36,
    35,
    34,
    33,
    32,
    31,  # Lower left
    41,
    42,
    43,
    44,
    45,
    46,
    47,
    48,  # Lower right
]

# Deciduous teeth numbers (for children)
DECIDUOUS_TEETH = [
    55,
    54,
    53,
    52,
    51,  # Upper right
    61,
    62,
    63,
    64,
    65,  # Upper left
    75,
    74,
    73,
    72,
    71,  # Lower left
    81,
    82,
    83,
    84,
    85,  # Lower right
]

SURFACES = ["M", "D", "O", "V", "L"]


def _is_child(patient_dob: date) -> bool:
    """Check if patient is a child (under 12 years old)."""
    age = (date.today() - patient_dob).days // 365
    return age < 12


def _get_patient_teeth(patient_dob: date) -> list[int]:
    """Get appropriate teeth for patient based on age."""
    if _is_child(patient_dob):
        return DECIDUOUS_TEETH
    return PERMANENT_TEETH


# Realistic odontogram scenarios for different patient profiles
def _single(
    clinical_type: str, tooth: int, *, surfaces: list[str] | None = None, status: str = "performed"
) -> dict:
    """Shortcut for single-tooth Treatment dicts in ODONTOGRAM_PROFILES."""
    return {
        "clinical_type": clinical_type,
        "status": status,
        "teeth": [{"tooth": tooth, "role": None, "surfaces": surfaces}],
    }


ODONTOGRAM_PROFILES = {
    # Each profile holds:
    #   tooth_conditions: {tooth_number: condition} — applied to ToothRecord.general_condition.
    #   treatments: list of {clinical_type, status, teeth: [{tooth, role, surfaces}]}.
    "healthy_adult": {
        "description": "Adult with good dental health",
        "tooth_conditions": {},
        "treatments": [],
    },
    "adult_with_fillings": {
        "description": "Adult with common fillings",
        "tooth_conditions": {},
        "treatments": [
            _single("filling_composite", 16, surfaces=["O"]),
            _single("filling_composite", 26, surfaces=["M", "O"]),
            _single("filling_composite", 36, surfaces=["O", "D"]),
            _single("filling_amalgam", 46, surfaces=["O"]),
            _single("filling_composite", 47, surfaces=["O"], status="planned"),
        ],
    },
    "adult_with_crowns": {
        "description": "Adult with crowns and root canals",
        "tooth_conditions": {},
        "treatments": [
            _single("root_canal_full", 36),
            _single("crown", 36),
            _single("crown", 46),
            _single("filling_composite", 17, surfaces=["O", "D"]),
            _single("filling_composite", 27, surfaces=["M", "O"]),
            _single("crown", 26, status="planned"),
        ],
    },
    "adult_with_implant": {
        "description": "Adult with implant",
        "tooth_conditions": {36: "missing"},
        "treatments": [
            _single("implant", 36),
            _single("filling_composite", 16, surfaces=["O"]),
            _single("filling_composite", 26, surfaces=["M", "O"]),
            _single("filling_amalgam", 46, surfaces=["O", "D"]),
        ],
    },
    "adult_with_bridge": {
        "description": "Adult with dental bridge 34-35-36",
        "tooth_conditions": {35: "missing"},
        "treatments": [
            {
                "clinical_type": "bridge",
                "status": "performed",
                "teeth": [
                    {"tooth": 34, "role": "pillar", "surfaces": None},
                    {"tooth": 35, "role": "pontic", "surfaces": None},
                    {"tooth": 36, "role": "pillar", "surfaces": None},
                ],
            },
            _single("filling_composite", 16, surfaces=["O"]),
            _single("filling_composite", 47, surfaces=["M", "O", "D"]),
        ],
    },
    "adult_needs_work": {
        "description": "Adult needing multiple treatments",
        "tooth_conditions": {},
        "treatments": [
            _single("filling_composite", 16, surfaces=["O"]),
            _single("filling_amalgam", 36, surfaces=["O", "D"]),
            _single("filling_composite", 17, surfaces=["O", "D"], status="planned"),
            _single("filling_composite", 26, surfaces=["M"], status="planned"),
            _single("crown", 37, status="planned"),
            _single("root_canal_full", 46, status="planned"),
        ],
    },
    "orthodontic_patient": {
        "description": "Patient with orthodontic treatment",
        "tooth_conditions": {},
        "treatments": [
            _single("bracket", 13),
            _single("bracket", 12),
            _single("bracket", 11),
            _single("bracket", 21),
            _single("bracket", 22),
            _single("bracket", 23),
            _single("tube", 16),
            _single("tube", 26),
            _single("bracket", 33),
            _single("bracket", 32),
            _single("bracket", 31),
            _single("bracket", 41),
            _single("bracket", 42),
            _single("bracket", 43),
        ],
        # Positional flags are handled via tooth_conditions — no need to emit
        # pseudo-treatments for 'rotated'/'displaced'.
        "positional": {23: {"is_rotated": True}, 13: {"is_displaced": True}},
    },
    "healthy_child": {
        "description": "Child with healthy deciduous teeth",
        "tooth_conditions": {},
        "treatments": [
            _single("sealant", 54, surfaces=["O"]),
            _single("sealant", 64, surfaces=["O"]),
            _single("sealant", 74, surfaces=["O"]),
            _single("sealant", 84, surfaces=["O"]),
        ],
    },
    "child_with_caries": {
        "description": "Child with fillings and planned restorations",
        "tooth_conditions": {},
        "treatments": [
            _single("filling_composite", 54, surfaces=["O"]),
            _single("filling_composite", 74, surfaces=["O", "D"]),
            _single("filling_composite", 64, surfaces=["O"], status="planned"),
            _single("filling_composite", 84, surfaces=["M", "O"], status="planned"),
        ],
    },
}

# Patient ID to profile mapping (deterministic based on patient index)
PATIENT_ODONTOGRAM_MAPPING = [
    # Index 0-1: Children (PATIENT_IDS[0], PATIENT_IDS[1])
    "healthy_child",  # Pablo/Ethan - first visit
    "child_with_caries",  # Lucía/Olivia - orthodontic treatment in progress (has caries)
    # Index 2-14: Adults with various profiles
    "healthy_adult",  # Miguel/James - young adult, healthy
    "adult_with_fillings",  # Carmen/Emma - sensitivity, has fillings
    "adult_with_fillings",  # David/William - simple fillings
    "healthy_adult",  # Elena/Sophia - pregnant, minimal treatment
    "adult_with_crowns",  # Javier/Daniel - diabetic, has crowns
    "adult_with_fillings",  # Isabel/Mia - standard fillings
    "adult_needs_work",  # Francisco/Alexander - allergic, needs work
    "adult_with_crowns",  # Rosa/Charlotte - hypertensive, crowns
    "adult_with_bridge",  # Antonio/Robert - partial denture (bridge)
    "adult_with_implant",  # María Teresa/Patricia - has implants
    "adult_needs_work",  # José Luis/Richard - on blood thinners, needs work
    "adult_with_fillings",  # Dolores/Barbara - standard
    "adult_with_crowns",  # Manuel/Charles - complete denture adjustments
]


def generate_odontogram_data() -> dict:
    """Generate odontogram seed data for all patients.

    Returns:
        Dictionary with:
        - tooth_records: List of ToothRecord data
        - treatments: List of Treatment headers
        - treatment_teeth: List of TreatmentTooth children
    """
    tooth_records = []
    treatments = []
    treatment_teeth = []
    patients_data = get_patients_data()

    tooth_record_idx = 0
    treatment_idx = 0

    for patient_idx, patient in enumerate(patients_data):
        patient_id = patient["id"]
        patient_dob = patient["date_of_birth"]

        # Get profile for this patient
        profile_name = PATIENT_ODONTOGRAM_MAPPING[patient_idx]
        profile = ODONTOGRAM_PROFILES[profile_name]

        # Get appropriate teeth based on age
        teeth = _get_patient_teeth(patient_dob)
        tooth_type = "deciduous" if _is_child(patient_dob) else "permanent"

        # Create tooth records for all teeth
        patient_tooth_records = {}  # tooth_number -> record
        for tooth_number in teeth:
            # Check if tooth has specific condition
            general_condition = profile["tooth_conditions"].get(tooth_number, "healthy")

            tooth_record_id = TOOTH_RECORD_IDS[tooth_record_idx]
            tooth_record_idx += 1

            record = {
                "id": tooth_record_id,
                "clinic_id": CLINIC_ID,
                "patient_id": patient_id,
                "tooth_number": tooth_number,
                "tooth_type": tooth_type,
                "general_condition": general_condition,
                "surfaces": {
                    "M": "healthy",
                    "D": "healthy",
                    "O": "healthy",
                    "V": "healthy",
                    "L": "healthy",
                },
                "notes": None,
                "is_displaced": False,
                "is_rotated": False,
                "displacement_notes": None,
            }

            tooth_records.append(record)
            patient_tooth_records[tooth_number] = record

        # Create treatments
        # Apply explicit positional flags if the profile sets them.
        for tooth_num, flags in profile.get("positional", {}).items():
            rec = patient_tooth_records.get(tooth_num)
            if rec:
                rec.update(flags)

        for treatment_def in profile["treatments"]:
            # Skip treatments whose teeth don't exist for this patient.
            teeth_defs = treatment_def["teeth"]
            if any(t["tooth"] not in patient_tooth_records for t in teeth_defs):
                continue

            treatment_id = TREATMENT_IDS[treatment_idx]
            treatment_idx += 1

            status = treatment_def["status"]
            recorded_at = datetime.now() - timedelta(days=30)
            performed_at = recorded_at if status == "performed" else None

            treatments.append(
                {
                    "id": treatment_id,
                    "clinic_id": CLINIC_ID,
                    "patient_id": patient_id,
                    "clinical_type": treatment_def["clinical_type"],
                    "catalog_item_id": None,
                    "status": status,
                    "recorded_at": recorded_at,
                    "performed_at": performed_at,
                    "performed_by": USER_DENTIST_ID if status == "performed" else None,
                    "price_snapshot": None,
                    "duration_snapshot": None,
                    "vat_rate_snapshot": None,
                    "budget_item_id": None,
                    "notes": None,
                    "source_module": "odontogram",
                    "deleted_at": None,
                }
            )

            for t in teeth_defs:
                treatment_teeth.append(
                    {
                        "treatment_id": treatment_id,
                        "tooth_record_id": patient_tooth_records[t["tooth"]]["id"],
                        "tooth_number": t["tooth"],
                        "role": t.get("role"),
                        "surfaces": t.get("surfaces"),
                    }
                )

    return {
        "tooth_records": tooth_records,
        "treatments": treatments,
        "treatment_teeth": treatment_teeth,
    }


# =============================================================================
# Patient Journey Data — single source of truth for plan/budget/appointment/invoice
# =============================================================================

# Fixed UUID pools for clinical journey entities.
TREATMENT_PLAN_IDS = [UUID(f"fe00bc99-9c0b-4ef8-bb6d-6bb9bd380{i:03x}") for i in range(20)]
PLAN_TREATMENT_IDS = [UUID(f"fa00bc99-9c0b-4ef8-bb6d-6bb9bd381{i:03x}") for i in range(200)]
PLANNED_ITEM_IDS = [UUID(f"ff00bc99-9c0b-4ef8-bb6d-6bb9bd380{i:03x}") for i in range(200)]
# Pre-allocated UUIDs for per-item sessions (up to 10 sessions per planned item).
PLAN_ITEM_SESSION_IDS = [UUID(f"f100bc99-9c0b-4ef8-bb6d-6bb9bd38{i:04x}") for i in range(2000)]
PATIENT_EARNED_ENTRY_IDS = [UUID(f"f200bc99-9c0b-4ef8-bb6d-6bb9bd38{i:04x}") for i in range(2000)]

BUDGET_IDS = [UUID(f"aa00bc99-9c0b-4ef8-bb6d-6bb9bd380b{i:02x}") for i in range(10)]
BUDGET_ITEM_IDS = [UUID(f"bb00bc99-9c0b-4ef8-bb6d-6bb9bd380c{i:02x}") for i in range(50)]
BUDGET_SIGNATURE_IDS = [UUID(f"cc00bc99-9c0b-4ef8-bb6d-6bb9bd380d{i:02x}") for i in range(10)]

INVOICE_SERIES_IDS = [UUID(f"fa00bc99-9c0b-4ef8-bb6d-6bb9bd380e{i:02x}") for i in range(5)]
INVOICE_IDS = [UUID(f"fb00bc99-9c0b-4ef8-bb6d-6bb9bd380f{i:02x}") for i in range(20)]
INVOICE_ITEM_IDS = [UUID(f"fc00bc99-9c0b-4ef8-bb6d-6bb9bd380{i:03x}") for i in range(100)]
PAYMENT_IDS = [UUID(f"fd00bc99-9c0b-4ef8-bb6d-6bb9bd380{i:03x}") for i in range(30)]


# Appointment visuals + duration by catalog_code prefix. Ordered most-specific first.
_APPT_LOOK_BY_PREFIX: list[tuple[str, dict]] = [
    (
        "DX-VISIT",
        {
            "name": {"es": "Revisión", "en": "Checkup", "fr": "Contrôle", "ta": "பரிசோதனை"},
            "duration": 30,
            "color": "#3B82F6",
        },
    ),
    (
        "DX-RX",
        {
            "name": {"es": "Radiografía", "en": "X-ray", "fr": "Radiographie", "ta": "எக்ஸ்-ரே"},
            "duration": 30,
            "color": "#60A5FA",
        },
    ),
    (
        "DX",
        {
            "name": {"es": "Diagnóstico", "en": "Diagnosis", "fr": "Diagnostic", "ta": "நோயறிதல்",},
            "duration": 30,
            "color": "#3B82F6",
        },
    ),
    (
        "PREV",
        {
            "name": {"es": "Limpieza dental", "en": "Dental cleaning", "fr": "Détartrage", "ta": "பல் சுத்தம்"},
            "duration": 45,
            "color": "#10B981",
        },
    ),
    (
        "REST-CROWN",
        {
            "name": {"es": "Corona", "en": "Crown", "fr": "Couronne","ta": "பல் கிரீடம்",},
            "duration": 60,
            "color": "#A855F7",
        },
    ),
    (
        "REST-VEN",
        {
            "name": {"es": "Carilla", "en": "Veneer", "fr": "Facette", "ta": "பல் முகப்பு",},
            "duration": 60,
            "color": "#F472B6",
        },
    ),
    (
        "REST-COMP",
        {
            "name": {"es": "Empaste", "en": "Filling", "fr": "Plombage", "ta": "பல் நிரப்பு"},
            "duration": 45,
            "color": "#F59E0B",
        },
    ),
    (
        "REST",
        {
            "name": {"es": "Restauración", "en": "Restoration", "fr": "Restauration","ta": "பல் மறுசீரமைப்பு", },
            "duration": 45,
            "color": "#F59E0B",
        },
    ),
    (
        "SURG-EXT",
        {
            "name": {"es": "Extracción", "en": "Extraction", "fr": "Extraction",  "ta": "பல் அகற்றுதல்"},
            "duration": 60,
            "color": "#EF4444",
        },
    ),
    (
        "SURG",
        {
            "name": {"es": "Cirugía", "en": "Surgery", "fr": "Chirurgie", "ta": "அறுவைச் சிகிச்சை",},
            "duration": 60,
            "color": "#DC2626",
        },
    ),
    (
        "ENDO-MULTI",
        {
            "name": {
                "es": "Endodoncia multirradicular",
                "en": "Multi-root canal",
                "fr": "Endodontie multiradiculaire",
                "ta": "பல வேர் கால்வாய் சிகிச்சை",
            },
            "duration": 90,
            "color": "#8B5CF6",
        },
    ),
    (
        "ENDO",
        {
            "name": {"es": "Endodoncia", "en": "Root canal", "fr": "Endodontie", "ta": "வேர் கால்வாய் சிகிச்சை",},
            "duration": 75,
            "color": "#8B5CF6",
        },
    ),
    (
        "PERIO",
        {
            "name": {"es": "Periodoncia", "en": "Periodontics", "fr": "Parodontie", "ta": "பல் சுற்றுத்திசு சிகிச்சை",},
            "duration": 60,
            "color": "#14B8A6",
        },
    ),
    (
        "EST-BLAN",
        {
            "name": {"es": "Blanqueamiento", "en": "Whitening", "fr": "Blanchiment", "ta": "பற்கள் வெண்மையாக்குதல்",},
            "duration": 60,
            "color": "#06B6D4",
        },
    ),
    (
        "EST",
        {
            "name": {"es": "Estética", "en": "Aesthetics", "fr": "Esthétique", "ta": "பல் அழகியல்",},
            "duration": 45,
            "color": "#06B6D4",
        },
    ),
    (
        "PROT",
        {
            "name": {"es": "Prótesis", "en": "Prosthesis", "fr": "Prothèse", "ta": "செயற்கைப் பல்"},
            "duration": 90,
            "color": "#84CC16",
        },
    ),
]


def _appt_look_for(code: str) -> dict:
    """Map a catalog internal_code to its display (name/duration/color) for appointments."""
    for prefix, meta in _APPT_LOOK_BY_PREFIX:
        if code.startswith(prefix):
            return meta
    return {
        "name": {"es": "Tratamiento", "en": "Treatment", "fr": "Traitement",  "ta": "சிகிச்சை"},
        "duration": 45,
        "color": "#64748B",
    }


# PATIENT_JOURNEYS: one entry per patient captures the full clinical narrative.
#
#   plan.items       : the items the patient needs. Both the budget and the appointments
#                      draw from this list (by index). Mark "completed": True for items
#                      already performed — this flips the backing Treatment to performed
#                      and the PlannedTreatmentItem to completed.
#   budget (opt.)    : financial materialization of the plan. items are 1-to-1 with
#                      plan.items and snap each item's unit_price / vat from catalog.
#   appointments     : 2-3 per patient. `covers` holds plan.items indexes this visit
#                      performs. `week` is past/current/future relative to "today".
#   invoice (opt.)   : bills a subset of budget items. `covers` lists the budget-item
#                      indexes (= plan-item indexes) this invoice invoices.
PATIENT_JOURNEYS = [
    # Patient 0 — Pablo / Ethan (pediatric, first visit)
    {
        "patient_idx": 0,
        "plan": {
            "id_idx": 0,
            "status": "active",
            "title": {
                "es": "Plan preventivo infantil",
                "en": "Pediatric preventive plan",
                "fr": "Plan préventif pédiatrique",
                "ta": "குழந்தைகளுக்கான தடுப்பு சிகிச்சைத் திட்டம்",
            },
            "diagnosis_notes": {
                "es": "Primera visita. Revisión pediátrica.",
                "en": "First visit. Pediatric checkup.",
                "fr": "Première visite. Contrôle pédiatrique.",
                "ta": "முதல் வருகை. குழந்தைகளுக்கான பல் பரிசோதனை.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True},
                {"catalog_code": "PREV-CLEAN", "is_global": True},
                {"catalog_code": "REST-COMP", "tooth": 54, "is_global": False},
            ],
        },
        "appointments": [
            {"week": "past", "covers": [0], "status": "completed"},
            {"week": "current", "covers": [1], "status": "confirmed"},
            {"week": "future", "covers": [2], "status": "scheduled"},
        ],
    },
    # Patient 1 — Lucía / Olivia (ortho + caries in deciduous molars)
    {
        "patient_idx": 1,
        "plan": {
            "id_idx": 1,
            "status": "active",
            "title": {
                "es": "Tratamiento conservador",
                "en": "Conservative treatment",
                "fr": "Traitement conservateur",
                "ta": "பாதுகாப்பு சிகிச்சை",
            },
            "diagnosis_notes": {
                "es": "Caries en molares inferiores deciduos.",
                "en": "Caries on lower deciduous molars.",
                "fr": "Caries sur les molaires inférieures temporaires.",
                "ta": "கீழ்த் தாடையின் பால் கடைவாய்ப் பற்களில் பல் சொத்தை.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True},
                {"catalog_code": "REST-COMP", "tooth": 74, "is_global": False},
                {"catalog_code": "REST-COMP", "tooth": 84, "is_global": False},
            ],
        },
        "appointments": [
            {"week": "past", "covers": [0], "status": "completed"},
            {"week": "current", "covers": [1], "status": "confirmed"},
            {"week": "future", "covers": [2], "status": "scheduled"},
        ],
    },
    # Patient 2 — Miguel / James (pending plan with draft budget, surfaces in
    # bandeja tab "Por presupuestar")
    {
        "patient_idx": 2,
        "plan": {
            "id_idx": 2,
            "status": "pending",
            "title": {
                "es": "Revisión y limpieza",
                "en": "Checkup and cleaning",
                "fr": "Contrôle et détartrage",
                "ta": "பரிசோதனை மற்றும் பல் சுத்தம்",
            },
            "diagnosis_notes": {
                "es": "Paciente joven, buen estado general.",
                "en": "Young patient, good general condition.",
                "fr": "Patient jeune, bon état général.",
                "ta": "இளம் நோயாளர், நல்ல பொது உடல்நிலை.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True},
                {"catalog_code": "PREV-CLEAN", "is_global": True},
            ],
        },
        "budget": {
            "id_idx": 0,
            "status": "draft",
            "global_discount": None,
            "signature": False,
            "notes": {
                "es": "Borrador pendiente de revisión",
                "en": "Draft pending review",
                "fr": "Brouillon en attente de révision",
                "ta": "மதிப்பாய்வுக்காக நிலுவையில் உள்ள வரைவு",
            },
        },
        "appointments": [],
        "invoice": {
            "id_idx": 0,
            "status": "draft",
            "payments": [],
            "covers": [0, 1],
            "notes": {
                "es": "Borrador - pendiente de emitir",
                "en": "Draft - pending issuance",
                "fr": "Brouillon - en attente d'émission",
                "ta": "வரைவு - வழங்குவதற்காக நிலுவையில் உள்ளது",
            },
        },
    },
    # Patient 3 — Carmen / Emma (pending plan with sent budget, surfaces in
    # bandeja tab "Esperando paciente")
    {
        "patient_idx": 3,
        "plan": {
            "id_idx": 3,
            "status": "pending",
            "title": {
                "es": "Plan de tratamiento inicial",
                "en": "Initial treatment plan",
                "fr": "Plan de traitement initial",
                "ta": "ஆரம்ப சிகிச்சைத் திட்டம்",
            },
            "diagnosis_notes": {
                "es": "Paciente con sensibilidad dental. Requiere empaste en molar.",
                "en": "Patient with dental sensitivity. Requires filling on molar.",
                "fr": "Patiente avec sensibilité dentaire. Nécessite un plombage sur la molaire.",
                "ta": "பல் உணர்திறன் உள்ள நோயாளர். கடைவாய்ப் பல்லில் நிரப்பு சிகிச்சை தேவை.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True},
                {"catalog_code": "DX-RXPAN", "is_global": True},
                {"catalog_code": "REST-COMP", "tooth": 16, "is_global": False},
            ],
        },
        "budget": {
            "id_idx": 1,
            "status": "sent",
            "global_discount": None,
            "signature": False,
            "notes": {
                "es": "Presupuesto enviado, esperando respuesta",
                "en": "Quote sent, awaiting response",
                "fr": "Devis envoyé, en attente de réponse",
                "ta": "மதிப்பீடு அனுப்பப்பட்டது, பதிலுக்காகக் காத்திருக்கிறது",
            },
        },
        "appointments": [],
        "invoice": None,
    },
    # Patient 4 — David / William (aesthetic; draft budget, no invoice yet)
    {
        "patient_idx": 4,
        "plan": {
            "id_idx": 4,
            "status": "active",
            "title": {"es": "Plan estético", "en": "Aesthetic plan", "fr": "Plan esthétique", "ta": "பல் அழகியல் சிகிச்சைத் திட்டம்"},
            "diagnosis_notes": {
                "es": "Paciente interesado en blanqueamiento.",
                "en": "Patient interested in whitening.",
                "fr": "Patient intéressé par le blanchiment.",
                "ta": "நோயாளர் பற்களை வெண்மையாக்கும் சிகிச்சையில் ஆர்வமாக உள்ளார்.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True, "completed": True},
                {"catalog_code": "PREV-CLEAN", "is_global": True},
                {"catalog_code": "EST-BLAN-CLIN", "is_global": True},
            ],
        },
        "budget": {
            "id_idx": 2,
            "status": "accepted",
            "global_discount": {"type": "percentage", "value": 5},
            "signature": True,
            "notes": {
                "es": "Aceptado, pendiente de agendar",
                "en": "Accepted, pending scheduling",
                "fr": "Accepté, en attente de planification",
                "ta": "ஏற்றுக்கொள்ளப்பட்டது, சந்திப்பு திட்டமிடப்பட வேண்டியுள்ளது",
            },
        },
        # No appointments — surfaces in bandeja tab "Sin cita".
        "appointments": [],
    },
    # Patient 5 — Elena / Sophia (pregnant; accepted budget with signature, partial invoice)
    {
        "patient_idx": 5,
        "plan": {
            "id_idx": 5,
            "status": "active",
            "title": {
                "es": "Diagnóstico y restauración",
                "en": "Diagnosis and restoration",
                "fr": "Diagnostic et restauration",
                "ta": "நோயறிதல் மற்றும் பல் மறுசீரமைப்பு",
            },
            "diagnosis_notes": {
                "es": "Embarazada. Evitar radiografías no esenciales.",
                "en": "Pregnant. Avoid non-essential x-rays.",
                "fr": "Enceinte. Éviter les radiographies non essentielles.",
                "ta": "கர்ப்பிணி. அவசியமற்ற எக்ஸ்-ரே பரிசோதனைகளைத் தவிர்க்கவும்.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True, "completed": True},
                {"catalog_code": "DX-RXPAN", "is_global": True, "completed": True},
                {"catalog_code": "REST-COMP", "tooth": 26, "is_global": False},
            ],
        },
        "budget": {
            "id_idx": 3,
            "status": "accepted",
            "global_discount": None,
            "signature": True,
            "notes": {
                "es": "Paciente embarazada - tratamiento en curso",
                "en": "Pregnant patient - treatment in progress",
                "fr": "Patiente enceinte - traitement en cours",
                "ta": "கர்ப்பிணி நோயாளர் - சிகிச்சை நடைபெற்று வருகிறது",
            },
        },
        "appointments": [
            {"week": "past", "covers": [0, 1], "status": "completed"},
            {"week": "current", "covers": [2], "status": "confirmed"},
        ],
        "invoice": {
            "id_idx": 2,
            "status": "partial",
            "payments": [{"method": "card", "percent": 50}],
            "covers": [0, 1, 2],
            "notes": {
                "es": "Pago parcial recibido",
                "en": "Partial payment received",
                "fr": "Paiement partiel reçu",
                "ta": "பகுதி பணப்பரிவர்த்தனை பெறப்பட்டது",
            },
        },
    },
    # Patient 6 — Javier / Daniel (diabetic; accepted+signed budget, paid invoice)
    {
        "patient_idx": 6,
        "plan": {
            "id_idx": 6,
            "status": "active",
            "title": {
                "es": "Endodoncia y corona",
                "en": "Root canal and crown",
                "fr": "Endodontie et couronne",
                "ta": "வேர் கால்வாய் சிகிச்சை மற்றும் பல் கிரீடம்",
            },
            "diagnosis_notes": {
                "es": "Paciente diabético. Control especial de cicatrización.",
                "en": "Diabetic patient. Special healing monitoring.",
                "fr": "Patient diabétique. Surveillance spéciale de la cicatrisation.",
                "ta": "நீரிழிவு நோயாளர். காயம் ஆறும் நிலையை சிறப்பாகக் கண்காணிக்க வேண்டும்.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True, "completed": True},
                {"catalog_code": "ENDO-MULTI", "tooth": 36, "is_global": False, "completed": True},
                {"catalog_code": "REST-CROWN-MC", "tooth": 36, "is_global": False},
            ],
        },
        "budget": {
            "id_idx": 4,
            "status": "accepted",
            "global_discount": None,
            "signature": True,
            "notes": {
                "es": "Paciente diabético - control especial",
                "en": "Diabetic patient - special care",
                "fr": "Patient diabétique - soins spéciaux",
                "ta": "நீரிழிவு நோயாளர் - சிறப்பு கவனிப்பு",
            },
        },
        # Past appointments only — surfaces in bandeja tab "Sin próxima cita".
        "appointments": [
            {"week": "past", "covers": [0], "status": "completed"},
            {"week": "past", "covers": [1], "status": "completed"},
        ],
        "invoice": {
            "id_idx": 3,
            "status": "paid",
            "payments": [{"method": "bank_transfer", "percent": 100}],
            "covers": [0, 1],
            "notes": {
                "es": "Pagado por transferencia",
                "en": "Paid by bank transfer",
                "fr": "Payé par virement",
                "ta": "வங்கி பரிமாற்றம் மூலம் செலுத்தப்பட்டது",
            },
        },
    },
    # Patient 7 — Isabel / Mia (rejected budget, no invoice)
    {
        "patient_idx": 7,
        "plan": {
            "id_idx": 7,
            "status": "closed",
            "closure_reason": "rejected_by_patient",
            "closure_note": {
                "es": "Paciente rechazó carillas estéticas por precio.",
                "en": "Patient rejected aesthetic veneers due to pricing.",
                "fr": "Patiente a rejeté les facettes esthétiques en raison du prix.",
                "ta": "விலை காரணமாக நோயாளர் பல் அழகியல் முகப்புகளை நிராகரித்தார்.",
            },
            "title": {
                "es": "Plan estético rechazado",
                "en": "Rejected aesthetic plan",
                "fr": "Plan esthétique rejeté",
                "ta": "நிராகரிக்கப்பட்ட பல் அழகியல் சிகிச்சைத் திட்டம்",
            },
            "diagnosis_notes": {
                "es": "Control semestral. Paciente rechazó carillas estéticas.",
                "en": "Bi-annual checkup. Patient rejected aesthetic veneers.",
                "fr": "Contrôle semestriel. Patiente a rejeté les facettes esthétiques.",
                "ta": "ஆறு மாதப் பரிசோதனை. நோயாளர் பல் அழகியல் முகப்புகளை நிராகரித்தார்.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True, "completed": True},
                {"catalog_code": "PREV-CLEAN", "is_global": True},
                {"catalog_code": "REST-VEN-COMP", "tooth": 11, "is_global": False},
            ],
        },
        "budget": {
            "id_idx": 5,
            "status": "rejected",
            "rejection_reason": "price",
            "rejection_note": {
                "es": "Precio de carillas demasiado alto",
                "en": "Veneer pricing too high",
                "fr": "Prix des facettes trop élevé",
                "ta": "பல் முகப்புகளுக்கான விலை மிகவும் அதிகம்",
            },
            "global_discount": None,
            "signature": False,
            "notes": {
                "es": "Rechazado por precio de carillas",
                "en": "Rejected due to veneer pricing",
                "fr": "Rejeté en raison du prix des facettes",
                "ta": "பல் முகப்புகளின் விலை காரணமாக நிராகரிக்கப்பட்டது",
            },
        },
        "appointments": [
            {"week": "past", "covers": [0], "status": "completed"},
        ],
    },
    # Patient 8 — Francisco / Alexander (penicillin allergic; accepted, paid split)
    {
        "patient_idx": 8,
        "plan": {
            "id_idx": 8,
            "status": "active",
            "title": {
                "es": "Tratamiento periodontal",
                "en": "Periodontal treatment",
                "fr": "Traitement parodontal",
                "ta": "பல் சுற்றுத்திசு சிகிச்சை",
            },
            "diagnosis_notes": {
                "es": "ALÉRGICO A PENICILINA. Usar alternativas.",
                "en": "ALLERGIC TO PENICILLIN. Use alternatives.",
                "fr": "ALLERGIQUE À LA PÉNICILLINE. Utiliser des alternatives.",
                "ta": "பெனிசிலினுக்கு ஒவ்வாமை உள்ளது. மாற்று மருந்துகளைப் பயன்படுத்தவும்.",
            },
            "items": [
                {"catalog_code": "PERIO-RAR", "is_global": True, "completed": True},
                {"catalog_code": "REST-COMP", "tooth": 17, "is_global": False, "completed": True},
                {"catalog_code": "REST-COMP", "tooth": 26, "is_global": False},
            ],
        },
        "budget": {
            "id_idx": 6,
            "status": "accepted",
            "global_discount": {"type": "absolute", "value": 50},
            "signature": True,
            "notes": {
                "es": "Alérgico a penicilina",
                "en": "Allergic to penicillin",
                "fr": "Allergique à la pénicilline",
                "ta": "பெனிசிலினுக்கு ஒவ்வாமை உள்ளது",
            },
        },
        "appointments": [
            {"week": "past", "covers": [0], "status": "completed"},
            {"week": "past", "covers": [1], "status": "completed"},
            {"week": "future", "covers": [2], "status": "scheduled"},
        ],
        "invoice": {
            "id_idx": 4,
            "status": "paid",
            "payments": [
                {"method": "cash", "percent": 40},
                {"method": "card", "percent": 60},
            ],
            "covers": [0, 1],
            "notes": {
                "es": "Pagado en dos plazos",
                "en": "Paid in two installments",
                "fr": "Payé en deux tranches",
                "ta": "இரண்டு தவணைகளில் செலுத்தப்பட்டது",
            },
        },
    },
    # Patient 9 — Rosa / Charlotte (hypertensive; accepted+signed, paid invoice)
    {
        "patient_idx": 9,
        "plan": {
            "id_idx": 9,
            "status": "active",
            "title": {
                "es": "Rehabilitación oral",
                "en": "Oral rehabilitation",
                "fr": "Réhabilitation bucco-dentaire",
                "ta": "வாய்வழி பல் மறுசீரமைப்பு",
            },
            "diagnosis_notes": {
                "es": "Hipertensa - verificar presión antes de procedimientos.",
                "en": "Hypertensive - check blood pressure before procedures.",
                "fr": "Hypertendue - vérifier la tension avant les soins.",
                "ta": "உயர் இரத்த அழுத்தம் உள்ளது - சிகிச்சைக்கு முன் இரத்த அழுத்தத்தைச் சரிபார்க்கவும்.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True, "completed": True},
                {
                    "catalog_code": "REST-CROWN-MC",
                    "tooth": 46,
                    "is_global": False,
                    "completed": True,
                },
                {"catalog_code": "ENDO-MULTI", "tooth": 36, "is_global": False},
                {"catalog_code": "REST-CROWN-MC", "tooth": 36, "is_global": False},
            ],
        },
        "budget": {
            "id_idx": 7,
            "status": "accepted",
            "global_discount": {"type": "percentage", "value": 10},
            "signature": True,
            "notes": {
                "es": "Tratamiento en curso",
                "en": "Treatment in progress",
                "fr": "Traitement en cours",
                "ta": "சிகிச்சை நடைபெற்று வருகிறது",
            },
        },
        "appointments": [
            {"week": "past", "covers": [0], "status": "completed"},
            {"week": "past", "covers": [1], "status": "completed"},
            {"week": "future", "covers": [2, 3], "status": "scheduled"},
        ],
        "invoice": {
            "id_idx": 5,
            "status": "paid",
            "payments": [{"method": "card", "percent": 100}],
            "covers": [0, 1],
            "notes": {
                "es": "Primera fase facturada",
                "en": "First phase billed",
                "fr": "Première phase facturée",
                "ta": "முதல் கட்டத்திற்கான விலைப்பட்டியல் வழங்கப்பட்டது",
            },
        },
    },
    # Patient 10 — Antonio / Robert (completed prosthetic workflow)
    {
        "patient_idx": 10,
        "plan": {
            "id_idx": 10,
            "status": "completed",
            "title": {
                "es": "Prótesis parcial superior",
                "en": "Upper partial denture",
                "fr": "Prothèse partielle supérieure",
                "ta": "மேல் தாடைக்கான பகுதி செயற்கைப் பல்",
            },
            "diagnosis_notes": {
                "es": "Prótesis parcial superior entregada y ajustada.",
                "en": "Upper partial denture delivered and adjusted.",
                "fr": "Prothèse partielle supérieure livrée et ajustée.",
                "ta": "மேல் தாடைக்கான பகுதி செயற்கைப் பல் வழங்கப்பட்டு பொருத்தம் சரிசெய்யப்பட்டது.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True, "completed": True},
                {"catalog_code": "PROT-PART-METAL", "is_global": True, "completed": True},
            ],
        },
        "budget": {
            "id_idx": 8,
            "status": "completed",
            "global_discount": None,
            "signature": True,
            "notes": {
                "es": "Prótesis parcial entregada",
                "en": "Partial denture delivered",
                "fr": "Prothèse partielle livrée",
                "ta": "பகுதி செயற்கைப் பல் வழங்கப்பட்டது",
            },
        },
        "appointments": [
            {"week": "past", "covers": [0], "status": "completed"},
            {"week": "past", "covers": [1], "status": "completed"},
        ],
        "invoice": {
            "id_idx": 6,
            "status": "paid",
            "payments": [{"method": "direct_debit", "percent": 100}],
            "covers": [0, 1],
            "notes": None,
        },
    },
    # Patient 11 — María Teresa / Patricia (corona multi-sesión en curso).
    # Demo del flujo de cobro fraccionado: la corona MC se compone de dos
    # sesiones ("Toma de medidas" 150€ + "Colocación" 250€). La primera ya
    # se hizo hoy y nadie la ha cobrado todavía → la pestaña Pagos de la
    # ficha mostrará "Pendiente de cobrar 150 €" con botón directo.
    {
        "patient_idx": 11,
        "plan": {
            "id_idx": 11,
            "status": "active",
            "title": {
                "es": "Corona en dos sesiones",
                "en": "Two-session crown",
                "fr": "Couronne en deux séances",
                "ta": "இரண்டு அமர்வுகளில் பல் கிரீடம்",
            },
            "diagnosis_notes": {
                "es": "Corona metal-cerámica en 36 — cobro fraccionado por sesión.",
                "en": "Metal-ceramic crown on tooth 36 — billed per session.",
                "fr": "Couronne métal-céramique sur 36 - facturation par séance.",
                "ta": "36-ஆம் பல்லில் உலோகம்-செராமிக் கிரீடம் — ஒவ்வொரு அமர்விற்கும் தனித்தனியாகக் கட்டணம் வசூலிக்கப்படும்.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True, "completed": True},
                {
                    "catalog_code": "REST-CROWN-MC",
                    "tooth": 36,
                    "is_global": False,
                    # Sesión 1 hecha y aún no cobrada; sesión 2 pendiente.
                    "sessions_completed": 1,
                },
            ],
        },
        "appointments": [
            {"week": "past", "covers": [0], "status": "completed"},
            {"week": "future", "covers": [1], "status": "scheduled"},
        ],
    },
    # Patient 12 — José Luis / Richard (anticoagulated; overdue invoice)
    {
        "patient_idx": 12,
        "plan": {
            "id_idx": 12,
            "status": "completed",
            "title": {
                "es": "Endodoncia urgente",
                "en": "Urgent root canal",
                "fr": "Endodontie urgente",
                "ta": "அவசர வேர் கால்வாய் சிகிச்சை",
            },
            "diagnosis_notes": {
                "es": "Endodoncia urgente por absceso. Paciente anticoagulado.",
                "en": "Urgent root canal due to abscess. Anticoagulated patient.",
                "fr": "Endodontie urgente pour abcès. Patient anticoagulé.",
                "ta": "பல் சீழ்க்கட்டியின் காரணமாக அவசர வேர் கால்வாய் சிகிச்சை. இரத்த உறைதலைத் தடுக்கும் மருந்து சிகிச்சையில் உள்ள நோயாளர்.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True, "completed": True},
                {"catalog_code": "ENDO-MULTI", "tooth": 46, "is_global": False, "completed": True},
            ],
        },
        "budget": {
            "id_idx": 9,
            "status": "accepted",
            "global_discount": None,
            "signature": True,
            "notes": {
                "es": "Anticoagulado - cuidado post-operatorio",
                "en": "Anticoagulated - post-op care",
                "fr": "Anticoagulé - soins post-opératoires",
                "ta": "இரத்த உறைதலைத் தடுக்கும் மருந்து சிகிச்சையில் உள்ளார் - அறுவைச் சிகிச்சைக்குப் பிந்தைய கவனிப்பு",
            },
        },
        "appointments": [
            {"week": "past", "covers": [0], "status": "completed"},
            {"week": "past", "covers": [1], "status": "completed"},
        ],
        "invoice": {
            "id_idx": 7,
            "status": "issued",
            "overdue": True,
            "payments": [],
            "covers": [0, 1],
            "notes": {"es": "Factura vencida", "en": "Overdue invoice", "fr": "Facture échue", "ta": "காலக்கெடு கடந்த விலைப்பட்டியல்",},
        },
    },
    # Patient 13 — Dolores / Barbara (evaluation; no budget)
    {
        "patient_idx": 13,
        "plan": {
            "id_idx": 13,
            "status": "active",
            "title": {
                "es": "Evaluación y limpieza",
                "en": "Evaluation and cleaning",
                "fr": "Évaluation et détartrage",
                "ta": "மதிப்பீடு மற்றும் பல் சுத்தம்",
            },
            "diagnosis_notes": {
                "es": "Evaluación periódica.",
                "en": "Periodic evaluation.",
                "fr": "Évaluation périodique.",
                "ta": "வழக்கமான மதிப்பீடு.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True},
                {"catalog_code": "DX-RXPAN", "is_global": True},
                {"catalog_code": "PREV-CLEAN", "is_global": True},
            ],
        },
        "appointments": [
            {"week": "current", "covers": [0, 1], "status": "confirmed"},
            {"week": "future", "covers": [2], "status": "scheduled"},
        ],
    },
    # Patient 14 — Manuel / Charles (prosthetic maintenance; no budget)
    {
        "patient_idx": 14,
        "plan": {
            "id_idx": 14,
            "status": "active",
            "title": {
                "es": "Mantenimiento protésico",
                "en": "Prosthetic maintenance",
                "fr": "Entretien prothétique",
                "ta": "செயற்கைப் பல் பராமரிப்பு",
            },
            "diagnosis_notes": {
                "es": "Ajustes periódicos de prótesis completa.",
                "en": "Periodic complete denture adjustments.",
                "fr": "Ajustements périodiques de prothèse complète.",
                "ta": "முழுமையான செயற்கைப் பல்லுக்கான வழக்கமான பொருத்தச் சரிசெய்தல்கள்.",
            },
            "items": [
                {"catalog_code": "DX-VISIT", "is_global": True, "completed": True},
                {"catalog_code": "PREV-CLEAN", "is_global": True},
            ],
        },
        "appointments": [
            {"week": "past", "covers": [0], "status": "completed"},
            {"week": "future", "covers": [1], "status": "scheduled"},
        ],
    },
]


def _calculate_line_totals(
    unit_price: Decimal, quantity: int, vat_rate: float | None
) -> tuple[Decimal, Decimal, Decimal]:
    """Return (line_subtotal, line_tax, line_total). Shared by budgets and invoices."""
    subtotal = Decimal(str(unit_price)) * quantity
    tax = subtotal * Decimal(str(vat_rate or 0)) / 100
    return subtotal, tax, subtotal + tax


def _global_discount_amount(subtotal: Decimal, global_discount: dict | None) -> Decimal:
    """Compute total discount from a {"type": percentage|absolute, "value": N} dict."""
    if not global_discount:
        return Decimal("0.00")
    value = Decimal(str(global_discount["value"]))
    if global_discount["type"] == "percentage":
        return subtotal * value / 100
    return value


# =============================================================================
# Treatment Plan Generator
# =============================================================================


def generate_treatment_plans_data(catalog_items_map: dict[str, dict]) -> dict:
    """Build TreatmentPlan + backing Treatment + PlannedTreatmentItem rows per journey.

    Args:
        catalog_items_map: internal_code -> {id, default_price, vat_type_id, vat_rate,
                           odontogram_treatment_type, sessions[]}.

    Returns:
        dict with:
          plans: list of TreatmentPlan dicts (budget_id=None; wired by seed_demo.py)
          plan_treatments: list of backing Treatment dicts
          items: list of PlannedTreatmentItem dicts
          item_sessions: list of PlannedTreatmentItemSession dicts (snapshot
              of catalog session template; one row per session of every
              multi-session item).
          earned_entries: list of PatientEarnedEntry dicts (one per
              completed session). Drives the "Pendiente de cobrar" panel
              on the patient ficha when net_paid < total_earned.
          plan_details: {plan_id: {
              "patient_id", "plan_number", "status", "assigned_professional_id",
              "items": [{"idx", "plan_item_id", "treatment_id", "catalog_code",
                         "catalog_item_id", "unit_price", "vat_type_id", "vat_rate",
                         "tooth_number", "is_global", "is_completed"}]}}
    """
    patients_data = get_patients_data()
    plans = []
    planned_items = []
    plan_treatments = []
    item_sessions: list[dict] = []
    earned_entries: list[dict] = []
    plan_details: dict = {}

    plan_item_idx = 0
    session_uuid_idx = 0
    earned_uuid_idx = 0

    for scenario_idx, journey in enumerate(PATIENT_JOURNEYS):
        plan_scenario = journey["plan"]
        patient = patients_data[journey["patient_idx"]]
        plan_id = TREATMENT_PLAN_IDS[plan_scenario["id_idx"]]

        plan_number = f"PLAN-2024-{scenario_idx + 1:04d}"
        plan_status = plan_scenario["status"]

        # Workflow timestamps. Active and completed plans went through
        # the confirm step; closed plans carry a closure reason.
        confirmed_at = None
        closed_at = None
        closure_reason = plan_scenario.get("closure_reason")
        closure_note = plan_scenario.get("closure_note")
        if plan_status in ("pending", "active", "completed"):
            confirmed_at = datetime.now() - timedelta(days=30 - scenario_idx)
        if plan_status == "closed":
            closed_at = datetime.now() - timedelta(days=15 - scenario_idx)
            closure_reason = closure_reason or "cancelled_by_clinic"

        plans.append(
            {
                "id": plan_id,
                "clinic_id": CLINIC_ID,
                "patient_id": patient["id"],
                "plan_number": plan_number,
                "title": t(plan_scenario["title"]) if plan_scenario.get("title") else None,
                "status": plan_status,
                "budget_id": None,  # wired by seed_demo after budgets are created
                "assigned_professional_id": USER_DENTIST_ID,
                "created_by": USER_DENTIST_ID,
                "diagnosis_notes": t(plan_scenario["diagnosis_notes"])
                if plan_scenario.get("diagnosis_notes")
                else None,
                "internal_notes": None,
                "deleted_at": None,
                # Workflow rework fields (PR1).
                "confirmed_at": confirmed_at,
                "closed_at": closed_at,
                "closure_reason": closure_reason,
                "closure_note": t(closure_note) if isinstance(closure_note, dict) else closure_note,
            }
        )

        details_items = []
        for seq_order, item_scenario in enumerate(plan_scenario.get("items", []), start=1):
            catalog_code = item_scenario["catalog_code"]
            catalog_item = catalog_items_map.get(catalog_code)
            if not catalog_item:
                continue

            planned_item_id = PLANNED_ITEM_IDS[plan_item_idx]
            treatment_id = PLAN_TREATMENT_IDS[plan_item_idx]
            plan_item_idx += 1

            is_completed = item_scenario.get("completed", False)
            plan_treatment_status = "performed" if is_completed else "planned"
            recorded_at = datetime.now() - timedelta(days=30)
            performed_at = datetime.now() - timedelta(days=10) if is_completed else None

            plan_treatments.append(
                {
                    "id": treatment_id,
                    "clinic_id": CLINIC_ID,
                    "patient_id": patient["id"],
                    "clinical_type": catalog_item.get("odontogram_treatment_type")
                    or "filling_composite",
                    "catalog_item_id": catalog_item["id"],
                    "status": plan_treatment_status,
                    "recorded_at": recorded_at,
                    "performed_at": performed_at,
                    "performed_by": USER_DENTIST_ID if is_completed else None,
                    "price_snapshot": catalog_item.get("default_price"),
                    "duration_snapshot": None,
                    "vat_rate_snapshot": None,
                    "budget_item_id": None,
                    "notes": None,
                    "source_module": "treatment_plan",
                    "deleted_at": None,
                }
            )

            # Per-item doctor assignment. Items inherit the plan's doctor by
            # default; hygiene-typical codes (cleanings, scaling) are assigned
            # to the hygienist instead so the demo plans visibly show a mix
            # of professionals — that's the whole point of the per-item field.
            is_hygiene_code = catalog_code in ("PREV-CLEAN", "PERIO-RAR")
            assigned_professional_id = USER_HYGIENIST_ID if is_hygiene_code else USER_DENTIST_ID

            planned_items.append(
                {
                    "id": planned_item_id,
                    "clinic_id": CLINIC_ID,
                    "treatment_plan_id": plan_id,
                    "treatment_id": treatment_id,
                    "sequence_order": seq_order,
                    "status": "completed" if is_completed else "pending",
                    "completed_without_appointment": is_completed,
                    "completed_at": datetime.now() - timedelta(days=10) if is_completed else None,
                    "completed_by": (assigned_professional_id if is_completed else None),
                    "assigned_professional_id": assigned_professional_id,
                    "notes": None,
                }
            )

            # Sessions: snapshot the catalog template (if any) into one
            # PlannedTreatmentItemSession per session. ``sessions_completed``
            # in the scenario overrides the count of completed sessions,
            # enabling partial-progress demos (first session done, rest
            # pending → "Pendiente de cobrar" surfaces on the Pagos tab).
            catalog_sessions = catalog_item.get("sessions") or []
            if not catalog_sessions:
                fallback_amount = catalog_item.get("default_price") or Decimal("0")
                snapshot_sessions = [{"sequence": 1, "label": None, "amount": fallback_amount}]
            else:
                snapshot_sessions = [
                    {
                        "sequence": cs["sequence"],
                        "label": (cs.get("labels") or {}).get("es")
                        or (cs.get("labels") or {}).get("en"),
                        "amount": cs["default_price"],
                    }
                    for cs in catalog_sessions
                ]

            override = item_scenario.get("sessions_completed")
            if is_completed and override is None:
                completed_count = len(snapshot_sessions)
            elif override is not None:
                completed_count = max(0, min(int(override), len(snapshot_sessions)))
            else:
                completed_count = 0

            for snap in snapshot_sessions:
                session_uuid = PLAN_ITEM_SESSION_IDS[session_uuid_idx]
                session_uuid_idx += 1
                session_completed = snap["sequence"] <= completed_count
                session_completed_at = (
                    datetime.now() - timedelta(days=10 - snap["sequence"])
                    if session_completed
                    else None
                )
                item_sessions.append(
                    {
                        "id": session_uuid,
                        "plan_item_id": planned_item_id,
                        "sequence": snap["sequence"],
                        "label": snap["label"],
                        "amount": snap["amount"],
                        "status": "completed" if session_completed else "pending",
                        "completed_at": session_completed_at,
                        "completed_by": assigned_professional_id if session_completed else None,
                        "notes": None,
                    }
                )

                if session_completed:
                    earned_entries.append(
                        {
                            "id": PATIENT_EARNED_ENTRY_IDS[earned_uuid_idx],
                            "clinic_id": CLINIC_ID,
                            "patient_id": patient["id"],
                            "treatment_id": treatment_id,
                            "catalog_item_id": catalog_item["id"],
                            "source_session_id": session_uuid,
                            "description": snap["label"],
                            "amount": snap["amount"],
                            "performed_at": session_completed_at,
                            "professional_id": assigned_professional_id,
                            "source_event": "treatment_plan.item_session_completed",
                        }
                    )
                    earned_uuid_idx += 1

            details_items.append(
                {
                    "idx": len(details_items),
                    "plan_item_id": planned_item_id,
                    "treatment_id": treatment_id,
                    "catalog_code": catalog_code,
                    "catalog_item_id": catalog_item["id"],
                    "unit_price": catalog_item["default_price"],
                    "vat_type_id": catalog_item.get("vat_type_id"),
                    "vat_rate": catalog_item.get("vat_rate", 0.0) or 0.0,
                    "tooth_number": item_scenario.get("tooth"),
                    "is_global": item_scenario.get("is_global", True),
                    "is_completed": is_completed,
                }
            )

        plan_details[plan_id] = {
            "patient_id": patient["id"],
            "plan_number": plan_number,
            "status": plan_scenario["status"],
            "assigned_professional_id": USER_DENTIST_ID,
            "items": details_items,
            "journey_idx": scenario_idx,
        }

    return {
        "plans": plans,
        "plan_treatments": plan_treatments,
        "items": planned_items,
        "item_sessions": item_sessions,
        "earned_entries": earned_entries,
        "plan_details": plan_details,
    }


# =============================================================================
# Budget Generator
# =============================================================================


def generate_budgets_data(catalog_items_map: dict[str, dict], plans_result: dict) -> dict:
    """Build Budget + BudgetItem + BudgetSignature rows derived from plans.

    Each budget is 1-to-1 with the journey's plan: items mirror plan.items (same
    catalog, same tooth_number) and each BudgetItem.treatment_id points to the
    plan's backing Treatment row.

    Returns dict with:
      budgets, items, signatures
      plan_to_budget: {plan_id: budget_id} — consumed by seed_demo.py to wire
                      TreatmentPlan.budget_id after budgets are committed.
      budget_item_details: {budget_id: [{"idx", "budget_item_id", "quantity",
                           "unit_price", "vat_type_id", "vat_rate", "catalog_code",
                           "catalog_item_id", "tooth_number"}]}
                           — consumed by the invoice generator.
    """
    budgets = []
    items = []
    signatures = []
    plan_to_budget: dict = {}
    budget_item_details: dict = {}

    item_idx = 0
    signature_idx = 0

    patients_data = get_patients_data()

    for journey_idx, journey in enumerate(PATIENT_JOURNEYS):
        budget_scenario = journey.get("budget")
        if not budget_scenario:
            continue

        patient = patients_data[journey["patient_idx"]]
        plan_id = TREATMENT_PLAN_IDS[journey["plan"]["id_idx"]]
        plan_detail = plans_result["plan_details"][plan_id]
        budget_id = BUDGET_IDS[budget_scenario["id_idx"]]

        plan_to_budget[plan_id] = budget_id

        budget_number = f"PRES-2024-{journey_idx + 1:04d}"
        valid_from = date.today() - timedelta(days=max(5, 30 - journey_idx * 5))
        valid_until = valid_from + timedelta(days=60)

        budget_items_local = []
        subtotal = Decimal("0.00")

        for plan_item in plan_detail["items"]:
            quantity = 1
            catalog_item = catalog_items_map.get(plan_item["catalog_code"])
            if not catalog_item:
                continue

            item_id = BUDGET_ITEM_IDS[item_idx]
            item_idx += 1

            unit_price = catalog_item["default_price"]
            vat_rate = catalog_item.get("vat_rate", 0.0) or 0.0
            line_subtotal, line_tax, line_total = _calculate_line_totals(
                unit_price, quantity, vat_rate
            )
            subtotal += line_subtotal

            budget_items_local.append(
                {
                    "id": item_id,
                    "clinic_id": CLINIC_ID,
                    "budget_id": budget_id,
                    "catalog_item_id": catalog_item["id"],
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "discount_type": None,
                    "discount_value": None,
                    "vat_type_id": catalog_item.get("vat_type_id"),
                    "vat_rate": vat_rate,
                    "line_subtotal": line_subtotal,
                    "line_discount": Decimal("0.00"),
                    "line_tax": line_tax,
                    "line_total": line_total,
                    "tooth_number": plan_item["tooth_number"],
                    "surfaces": None,
                    "treatment_id": plan_item["treatment_id"],
                    "invoiced_quantity": 0,
                    "display_order": len(budget_items_local) + 1,
                    "notes": None,
                }
            )

        items.extend(budget_items_local)

        global_discount_type = None
        global_discount_value = None
        gd = budget_scenario.get("global_discount")
        if gd:
            global_discount_type = gd["type"]
            global_discount_value = Decimal(str(gd["value"]))
        total_discount = _global_discount_amount(subtotal, gd)
        total_tax = sum((bi["line_tax"] for bi in budget_items_local), Decimal("0.00"))
        total = subtotal - total_discount + total_tax

        b_status = budget_scenario["status"]
        accepted_via = "manual" if b_status == "accepted" else None
        rejection_reason = (
            budget_scenario.get("rejection_reason") if b_status == "rejected" else None
        )
        rejection_note = budget_scenario.get("rejection_note") if b_status == "rejected" else None

        budgets.append(
            {
                "id": budget_id,
                "clinic_id": CLINIC_ID,
                "patient_id": patient["id"],
                "budget_number": budget_number,
                "version": 1,
                "parent_budget_id": None,
                "status": b_status,
                "valid_from": valid_from,
                "valid_until": valid_until,
                "created_by": USER_DENTIST_ID,
                "assigned_professional_id": USER_DENTIST_ID,
                "global_discount_type": global_discount_type,
                "global_discount_value": global_discount_value,
                "subtotal": subtotal,
                "total_discount": total_discount,
                "total_tax": total_tax,
                "total": total,
                "internal_notes": t(budget_scenario["notes"])
                if budget_scenario.get("notes")
                else None,
                "patient_notes": None,
                "insurance_estimate": None,
                "deleted_at": None,
                # Workflow rework fields (PR1).
                "accepted_via": accepted_via,
                "rejection_reason": rejection_reason,
                "rejection_note": t(rejection_note)
                if isinstance(rejection_note, dict)
                else rejection_note,
                "public_token": uuid4(),
                "viewed_at": None,
                "last_reminder_sent_at": None,
                "public_auth_method": "phone_last4",
                "public_auth_secret_hash": None,
                "public_locked_at": None,
                "plan_number_snapshot": plan_detail["plan_number"],
                "plan_status_snapshot": plan_detail["status"],
            }
        )

        if budget_scenario.get("signature") and budget_scenario["status"] not in (
            "draft",
            "rejected",
        ):
            signature_id = BUDGET_SIGNATURE_IDS[signature_idx]
            signature_idx += 1
            signatures.append(
                {
                    "id": signature_id,
                    "clinic_id": CLINIC_ID,
                    "budget_id": budget_id,
                    "signature_type": "full_acceptance",
                    "signed_items": [str(bi["id"]) for bi in budget_items_local],
                    "signed_by_name": f"{patient['first_name']} {patient['last_name']}",
                    "signed_by_email": patient.get("email"),
                    "relationship_to_patient": "patient",
                    "signature_method": "click_accept",
                    "signature_data": {
                        "accepted_terms": True,
                        "timestamp": datetime.now().isoformat(),
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Demo Browser)",
                    "signed_at": datetime.now() - timedelta(days=15),
                    "external_signature_id": None,
                    "external_provider": None,
                    "document_hash": None,
                }
            )

        budget_item_details[budget_id] = [
            {
                "idx": local_idx,
                "budget_item_id": bi["id"],
                "quantity": bi["quantity"],
                "unit_price": bi["unit_price"],
                "vat_type_id": bi["vat_type_id"],
                "vat_rate": bi["vat_rate"],
                "catalog_code": plan_detail["items"][local_idx]["catalog_code"],
                "catalog_item_id": bi["catalog_item_id"],
                "tooth_number": bi["tooth_number"],
            }
            for local_idx, bi in enumerate(budget_items_local)
        ]

    return {
        "budgets": budgets,
        "items": items,
        "signatures": signatures,
        "plan_to_budget": plan_to_budget,
        "budget_item_details": budget_item_details,
    }


# =============================================================================
# Appointment Generator
# =============================================================================


def generate_appointments_data(plans_result: dict, reference_date: date | None = None) -> dict:
    """Build Appointment + AppointmentTreatment rows anchored to plan items.

    Each journey declares its appointments with a `covers` list of plan-item indexes
    the visit performs. The generator:
      - places each appointment in an available slot (past/current/future week)
      - sets patient/professional from the plan
      - derives duration/color/treatment_type from the first covered item's
        catalog code
      - emits one AppointmentTreatment row per covered item, linking to the
        corresponding PlannedTreatmentItem and catalog_item.

    Returns:
        dict with:
          appointments: list of Appointment dicts
          appointment_treatments: list of AppointmentTreatment dicts
    """
    from uuid import uuid4

    if reference_date is None:
        reference_date = date.today()

    current_monday = reference_date - timedelta(days=reference_date.weekday())
    week_starts = {
        "past": current_monday - timedelta(days=7),
        "current": current_monday,
        "future": current_monday + timedelta(days=7),
    }

    clinic_data = get_clinic_data()
    cabinets = [c["name"] for c in clinic_data["cabinets"]]

    appointments: list[dict] = []
    appointment_treatments: list[dict] = []
    used_slots: set[tuple[str, str, datetime]] = set()

    # Spread visits across days/slots deterministically: counter drives day/slot pick.
    pick_counter = 0

    for journey in PATIENT_JOURNEYS:
        plan_id = TREATMENT_PLAN_IDS[journey["plan"]["id_idx"]]
        plan_detail = plans_result["plan_details"][plan_id]
        patient_id = plan_detail["patient_id"]
        professional_id = plan_detail["assigned_professional_id"]

        for appt_scenario in journey.get("appointments", []):
            covers = appt_scenario.get("covers", [])
            if not covers:
                continue

            covered_items = [plan_detail["items"][idx] for idx in covers]
            first_code = covered_items[0]["catalog_code"]
            look = _appt_look_for(first_code)
            total_duration = sum(
                _appt_look_for(ci["catalog_code"])["duration"] for ci in covered_items
            )
            # round up to the next 30-minute slot
            total_duration = ((total_duration + 29) // 30) * 30

            week_start = week_starts[appt_scenario["week"]]

            # Find a free slot (avoid conflicts on cabinet + professional + datetime).
            start_time = None
            for attempt in range(80):
                day_offset = (pick_counter + attempt) % 5  # Mon-Fri
                slot_pool = MORNING_SLOTS if (pick_counter + attempt) % 3 != 0 else AFTERNOON_SLOTS
                time_str = slot_pool[(pick_counter + attempt) % len(slot_pool)]
                hour, minute = map(int, time_str.split(":"))
                candidate = datetime(
                    week_start.year,
                    week_start.month,
                    week_start.day,
                    hour,
                    minute,
                    0,
                ) + timedelta(days=day_offset)
                cabinet_pick = cabinets[(pick_counter + attempt) % len(cabinets)]
                slot_key = (cabinet_pick, str(professional_id), candidate)
                if slot_key in used_slots:
                    continue
                used_slots.add(slot_key)
                start_time = candidate
                cabinet = cabinet_pick
                break
            if start_time is None:
                continue
            pick_counter += 1

            end_time = start_time + timedelta(minutes=total_duration)
            appointment_id = uuid4()

            appointments.append(
                {
                    "id": appointment_id,
                    "clinic_id": CLINIC_ID,
                    "patient_id": patient_id,
                    "professional_id": professional_id,
                    "cabinet": cabinet,
                    "start_time": start_time,
                    "end_time": end_time,
                    "treatment_type": t(look["name"]),
                    "status": appt_scenario["status"],
                    "color": look["color"],
                }
            )

            for display_order, ci in enumerate(covered_items):
                appointment_treatments.append(
                    {
                        "appointment_id": appointment_id,
                        "planned_treatment_item_id": ci["plan_item_id"],
                        "catalog_item_id": ci["catalog_item_id"],
                        "display_order": display_order,
                    }
                )

    return {
        "appointments": appointments,
        "appointment_treatments": appointment_treatments,
    }


# =============================================================================
# Invoice Generator
# =============================================================================


def generate_invoice_series_data() -> list[dict]:
    """Generate invoice series seed data."""
    current_year = date.today().year
    num_invoices = sum(1 for j in PATIENT_JOURNEYS if j.get("invoice"))
    definitions = [
        {
            "id": INVOICE_SERIES_IDS[0],
            "prefix": "FAC",
            "series_type": "invoice",
            "description": t(
                {
                    "es": "Serie principal de facturas",
                    "en": "Main invoice series",
                    "fr": "Série principale de factures",
                    "ta": "முதன்மை விலைப்பட்டியல் தொடர்",
                }
            ),
            "current_number": num_invoices + 1,
            "is_default": True,
        },
        {
            "id": INVOICE_SERIES_IDS[1],
            "prefix": "RECT",
            "series_type": "credit_note",
            "description": t(
                {"es": "Notas de crédito", "en": "Credit notes", "fr": "Notes de crédit", "ta": "கடன் குறிப்புகள்",}
            ),
            "current_number": 1,
            "is_default": True,
        },
    ]
    return [
        {
            "id": s["id"],
            "clinic_id": CLINIC_ID,
            "prefix": s["prefix"],
            "series_type": s["series_type"],
            "description": s["description"],
            "current_number": s["current_number"],
            "reset_yearly": True,
            "last_reset_year": current_year,
            "is_default": s["is_default"],
            "is_active": True,
        }
        for s in definitions
    ]


def generate_invoices_data(catalog_items_map: dict[str, dict], budgets_result: dict) -> dict:
    """Build Invoice + InvoiceItem + Payment rows anchored to budgets.

    After the payments-module extraction (issue #53, ADR 0010) the
    Payment model lives outside billing. Each invoice that records
    payments now produces three correlated rows:

    - ``Payment`` (patient-centric, currency snapshot, ``on_account``
      allocation that the InvoicePayment immediately "consumes")
    - ``PaymentAllocation(target='on_account')``
    - ``InvoicePayment`` link row binding the payment to the invoice

    Returns dict with:
      series, invoices, items, payments, payment_allocations,
      invoice_payments
      invoiced_quantity_by_budget_item: {budget_item_id: total_qty}
    """
    import uuid

    patients_data = get_patients_data()
    invoices: list[dict] = []
    items: list[dict] = []
    payments: list[dict] = []
    payment_allocations: list[dict] = []
    invoice_payments: list[dict] = []
    invoiced_quantity: dict = {}

    invoice_idx = 0
    item_idx = 0
    payment_idx = 0
    sequential_number = 0
    current_year = date.today().year
    series = generate_invoice_series_data()

    for journey_idx, journey in enumerate(PATIENT_JOURNEYS):
        invoice_scenario = journey.get("invoice")
        if not invoice_scenario:
            continue
        budget_scenario = journey.get("budget")
        if not budget_scenario:
            continue  # cannot invoice without a budget

        patient = patients_data[journey["patient_idx"]]
        budget_id = BUDGET_IDS[budget_scenario["id_idx"]]
        budget_items = budgets_result["budget_item_details"][budget_id]

        invoice_id = INVOICE_IDS[invoice_scenario["id_idx"]]
        invoice_idx += 1
        sequential_number += 1
        invoice_number = f"FAC-{current_year}-{sequential_number:04d}"

        is_overdue = invoice_scenario.get("overdue", False)
        if invoice_scenario["status"] == "draft":
            issue_date = None
            due_date = None
        elif is_overdue:
            issue_date = date.today() - timedelta(days=45)
            due_date = date.today() - timedelta(days=15)
        else:
            days_ago = max(5, (7 - journey_idx) * 3 + 5)
            issue_date = date.today() - timedelta(days=days_ago)
            due_date = issue_date + timedelta(days=30)

        invoice_items_local: list[dict] = []
        subtotal = Decimal("0.00")
        total_tax = Decimal("0.00")

        for budget_item in [budget_items[i] for i in invoice_scenario["covers"]]:
            item_id = INVOICE_ITEM_IDS[item_idx]
            item_idx += 1

            unit_price = budget_item["unit_price"]
            quantity = budget_item["quantity"]
            vat_rate = budget_item["vat_rate"]
            line_subtotal, line_tax, line_total = _calculate_line_totals(
                unit_price, quantity, vat_rate
            )
            subtotal += line_subtotal
            total_tax += line_tax

            invoice_items_local.append(
                {
                    "id": item_id,
                    "clinic_id": CLINIC_ID,
                    "invoice_id": invoice_id,
                    "budget_item_id": budget_item["budget_item_id"],
                    "catalog_item_id": budget_item["catalog_item_id"],
                    "description": t(
                        {
                            "es": f"Tratamiento {budget_item['catalog_code']}",
                            "en": f"Treatment {budget_item['catalog_code']}",
                        }
                    ),
                    "internal_code": budget_item["catalog_code"],
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "discount_type": None,
                    "discount_value": None,
                    "vat_type_id": budget_item["vat_type_id"],
                    "vat_rate": vat_rate,
                    "vat_exempt_reason": None,
                    "line_subtotal": line_subtotal,
                    "line_discount": Decimal("0.00"),
                    "line_tax": line_tax,
                    "line_total": line_total,
                    "tooth_number": budget_item["tooth_number"],
                    "surfaces": None,
                    "display_order": len(invoice_items_local) + 1,
                }
            )
            invoiced_quantity[budget_item["budget_item_id"]] = (
                invoiced_quantity.get(budget_item["budget_item_id"], 0) + quantity
            )

        items.extend(invoice_items_local)
        total = subtotal + total_tax

        total_paid = Decimal("0.00")
        for payment_data in invoice_scenario.get("payments", []):
            payment_id = PAYMENT_IDS[payment_idx]
            payment_idx += 1
            amount = (total * Decimal(str(payment_data["percent"]))) / 100
            total_paid += amount
            pay_date = issue_date + timedelta(days=3) if issue_date else date.today()
            payments.append(
                {
                    "id": payment_id,
                    "clinic_id": CLINIC_ID,
                    "patient_id": patient["id"],
                    "amount": amount,
                    "currency": "EUR",
                    "method": payment_data["method"],
                    "payment_date": pay_date,
                    "reference": f"REF-{payment_idx:04d}",
                    "notes": None,
                    "recorded_by": USER_RECEPTIONIST_ID,
                }
            )
            # Each payment carries one on_account allocation so the
            # invariant Σ allocation.amount == payment.amount holds.
            # The InvoicePayment link rides on top — that's how billing
            # imputes the cobro without payments knowing about invoices.
            payment_allocations.append(
                {
                    "id": uuid.uuid4(),
                    "clinic_id": CLINIC_ID,
                    "payment_id": payment_id,
                    "target_type": "on_account",
                    "budget_id": None,
                    "amount": amount,
                    "created_by": USER_RECEPTIONIST_ID,
                }
            )
            invoice_payments.append(
                {
                    "id": uuid.uuid4(),
                    "clinic_id": CLINIC_ID,
                    "invoice_id": invoice_id,
                    "payment_id": payment_id,
                    "amount": amount,
                    "created_by": USER_RECEPTIONIST_ID,
                }
            )

        invoices.append(
            {
                "id": invoice_id,
                "clinic_id": CLINIC_ID,
                "patient_id": patient["id"],
                "invoice_number": invoice_number,
                "series_id": INVOICE_SERIES_IDS[0],
                "sequential_number": sequential_number,
                "budget_id": budget_id,
                "credit_note_for_id": None,
                "status": invoice_scenario["status"],
                "issue_date": issue_date,
                "due_date": due_date,
                "payment_term_days": 30,
                "billing_name": f"{patient['first_name']} {patient['last_name']}",
                "billing_tax_id": None,
                "billing_address": None,
                "billing_email": patient.get("email"),
                "subtotal": subtotal,
                "total_discount": Decimal("0.00"),
                "total_tax": total_tax,
                "total": total,
                "internal_notes": t(invoice_scenario["notes"])
                if invoice_scenario.get("notes")
                else None,
                "public_notes": None,
                "compliance_data": None,
                "document_hash": None,
                "created_by": USER_RECEPTIONIST_ID,
                "issued_by": USER_RECEPTIONIST_ID
                if invoice_scenario["status"] != "draft"
                else None,
                "deleted_at": None,
            }
        )

    return {
        "series": series,
        "invoices": invoices,
        "items": items,
        "payments": payments,
        "payment_allocations": payment_allocations,
        "invoice_payments": invoice_payments,
        "invoiced_quantity_by_budget_item": invoiced_quantity,
    }
