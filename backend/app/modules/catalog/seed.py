"""Seed data for the catalog module.

Creates VAT types, categories and a broad catalog of billable treatments. Includes
pricing strategies (flat / per_tooth / per_surface / per_role) so that multi-tooth
treatments can scale price with the tooth count automatically.

Visualization rules use the new layered JSONB format:

    visualization_rules = [
        {"layer": "cenital_pattern", "pattern": "diagonal_stripes", "color": "#F59E0B"},
        {"layer": "lateral_icon",    "icon": "implant",            "color": "#10B981"}
    ]

Diagnostic findings (caries, fracture, etc.) are NOT billable and therefore are
not seeded here. Their visualization is driven by the odontogram module's
default rules for clinical_type.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    CatalogItemSession,
    TreatmentCatalogItem,
    TreatmentCategory,
    TreatmentOdontogramMapping,
    VatType,
)

# ============================================================================
# VAT types
# ============================================================================

VAT_TYPES: list[dict[str, Any]] = [
    {
        "key": "exempt",
        "names": {"es": "Exento", "en": "Exempt", "fr": "Exonéré", "ta": "விலக்கு"},
        "rate": 0.0,
        "is_default": True,
    },
    {
        "key": "reduced",
        "names": {
            "es": "Reducido (10%)",
            "en": "Reduced (10%)",
            "fr": "Réduit (10%)",
            "ta": "குறைக்கப்பட்டது (10%)",
        },
        "rate": 10.0,
        "is_default": False,
    },
    {
        "key": "standard",
        "names": {
            "es": "General (21%)",
            "en": "Standard (21%)",
            "fr": "Général (21%)",
            "ta": "பொதுவானது (21%)",
        },
        "rate": 21.0,
        "is_default": False,
    },
]

# ============================================================================
# Categories
# ============================================================================

CATEGORIES: list[dict[str, Any]] = [
    {
        "key": "diagnostico",
        "names": {"es": "Diagnóstico", "en": "Diagnostic", "fr": "Diagnostic", "ta": "நோயறிதல்"},
        "descriptions": {
            "es": "Servicios de diagnóstico y evaluación",
            "en": "Diagnostic and evaluation services",
            "fr": "Services de diagnostique et d'évaluation",
            "ta": "நோயறிதல் மற்றும் மதிப்பீட்டு சேவைகள்",
        },
        "display_order": 1,
        "icon": "i-lucide-stethoscope",
    },
    {
        "key": "preventivo",
        "names": {"es": "Preventivo", "en": "Preventive", "fr": "Préventif", "ta": "தடுப்பு"},
        "descriptions": {
            "es": "Prevención e higiene dental",
            "en": "Preventive and hygiene",
            "fr": "Prévention et hygiène dentaire",
            "ta": "நோய் தடுப்பு மற்றும் பல் சுகாதாரம்",
        },
        "display_order": 2,
        "icon": "i-lucide-shield-check",
    },
    {
        "key": "restauradora",
        "names": {
            "es": "Restauradora",
            "en": "Restorative",
            "fr": "Restauration",
            "ta": "பல் மறுசீரமைப்பு",
        },
        "descriptions": {
            "es": "Restauración dental",
            "en": "Dental restoration",
            "fr": "Restauration dentaire",
            "ta": "பல் மறுசீரமைப்பு",
        },
        "display_order": 3,
        "icon": "i-lucide-brush",
    },
    {
        "key": "endodoncia",
        "names": {
            "es": "Endodoncia",
            "en": "Endodontics",
            "fr": "Endodontie",
            "ta": "பல்லுட்புறச் சிகிச்சை",
        },
        "descriptions": {
            "es": "Tratamientos de conducto radicular",
            "en": "Root canal treatments",
            "fr": "Traitements des canaux radiculaires",
            "ta": "பல் வேர் சிகிச்சைகள்",
        },
        "display_order": 4,
        "icon": "i-lucide-activity",
    },
    {
        "key": "periodoncia",
        "names": {
            "es": "Periodoncia",
            "en": "Periodontics",
            "fr": "Parodontie",
            "ta": "பல்லைச் சுற்றிய திசு மருத்துவம்",
        },
        "descriptions": {
            "es": "Encías y tejidos de soporte",
            "en": "Gums and supporting tissues",
            "fr": "Gencives et tissus de soutien",
            "ta": "ஈறுகள் மற்றும் பற்களைத் தாங்கும் திசுக்கள்",
        },
        "display_order": 5,
        "icon": "i-lucide-heart-pulse",
    },
    {
        "key": "cirugia",
        "names": {"es": "Cirugía", "en": "Surgery", "fr": "Chirurgie", "ta": "பல் அறுவைச் சிகிச்சை"},
        "descriptions": {
            "es": "Procedimientos quirúrgicos dentales",
            "en": "Dental surgical procedures",
            "fr": "Procédures chirurgicales dentaires",
            "ta": "பல் அறுவைச் சிகிச்சை நடைமுறைகள்",
        },
        "display_order": 6,
        "icon": "i-lucide-scissors",
    },
    {
        "key": "ortodoncia",
        "names": {"es": "Ortodoncia", "en": "Orthodontics", "fr": "Orthodontie", "ta": "பற்சீரமைப்பு"},
        "descriptions": {
            "es": "Ortodoncia y alineación",
            "en": "Orthodontics and alignment",
            "fr": "Orthodontie et alignement",
            "ta": "பற்சீரமைப்பு மற்றும் பற்கள் சீரமைத்தல்",
        },
        "display_order": 7,
        "icon": "i-lucide-align-center",
    },
    {
        "key": "estetica",
        "names": {"es": "Estética", "en": "Cosmetic", "fr": "Esthétique", "ta": "அழகியல்"},
        "descriptions": {
            "es": "Estética dental",
            "en": "Cosmetic dentistry",
            "fr": "Esthétique dentaire",
            "ta": "அழகியல் பல் மருத்துவம்",
        },
        "display_order": 8,
        "icon": "i-lucide-sparkles",
    },
    {
        "key": "protesis",
        "names": {"es": "Prótesis", "en": "Prosthetics", "fr": "Prothèses", "ta": "செயற்கைப் பற்கள்"},
        "descriptions": {
            "es": "Prótesis y férulas",
            "en": "Prosthetics and splints",
            "fr": "Prothèses et gouttières",
            "ta": "செயற்கைப் பற்கள் மற்றும் பல் நிலைப்படுத்தும் கருவிகள்",
        },
        "display_order": 9,
        "icon": "i-lucide-puzzle",
    },
    {
        "key": "pediatrica",
        "names": {
            "es": "Odontopediatría",
            "en": "Pediatric",
            "fr": "Odontologie pédiatrique",
            "ta": "குழந்தைகள் பல் மருத்துவம்",
        },
        "descriptions": {
            "es": "Tratamientos para niños",
            "en": "Treatments for children",
            "fr": "Traitements pour enfants",
            "ta": "குழந்தைகளுக்கான மருத்துவ சிகிச்சைகள்",
        },
        "display_order": 10,
        "icon": "i-lucide-baby",
    },
]


# ============================================================================
# Visualization presets
# ============================================================================
#
# Keep helpers tiny and explicit to make adding new items obvious.


def pattern_fill(pattern: str, color: str) -> dict[str, Any]:
    """Cenital (occlusal) pattern fill. Common for crowns, bridges, inlays."""
    return {"layer": "cenital_pattern", "pattern": pattern, "color": color}


def lateral_icon(icon: str, color: str) -> dict[str, Any]:
    """Lateral view SVG icon. Common for implants, extractions, brackets."""
    return {"layer": "lateral_icon", "icon": icon, "color": color}


def pulp_fill(color: str, extent: str = "full") -> dict[str, Any]:
    """Pulp chamber fill on lateral view. Root canals."""
    return {"layer": "pulp_fill", "color": color, "extent": extent}


def occlusal_surface(color: str, kind: str = "solid_fill") -> dict[str, Any]:
    """Per-surface fill on occlusal view. Fillings, sealants, veneers."""
    return {"layer": "occlusal_surface", "color": color, "kind": kind}


# ============================================================================
# Treatments
# ============================================================================

TREATMENTS: dict[str, list[dict[str, Any]]] = {
    # ---------- Diagnóstico ----------
    "diagnostico": [
        {
            "internal_code": "DX-VISIT",
            "names": {
                "es": "Primera Visita",
                "en": "First Visit",
                "fr": "Première visite",
                "ta": "முதல் வருகை",
            },
            "descriptions": {
                "es": "Consulta inicial con exploración y diagnóstico",
                "en": "Initial consultation with examination and diagnosis",
                "fr": "Consultation initiale avec examen et diagnostique",
                "ta": "பரிசோதனை மற்றும் நோயறிதலுடன் கூடிய ஆரம்ப ஆலோசனை",
            },
            "treatment_scope": "global_mouth",
            "is_diagnostic": False,
            "requires_surfaces": False,
            "default_price": Decimal("30.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "DX-REVIEW",
            "names": {"es": "Revisión", "en": "Follow-up", "fr": "Contrôle", "ta": "தொடர் பரிசோதனை"},
            "treatment_scope": "global_mouth",
            "default_price": Decimal("20.00"),
            "default_duration_minutes": 20,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "DX-RXPA",
            "names": {
                "es": "Radiografía Periapical",
                "en": "Periapical X-Ray",
                "fr": "Radiographie périapicale",
                "ta": "பல் வேர் முனைப்பகுதி எக்ஸ்ரே",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("15.00"),
            "default_duration_minutes": 10,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "DX-RXPAN",
            "names": {
                "es": "Radiografía Panorámica",
                "en": "Panoramic X-Ray",
                "fr": "Radiographie panoramique",
                "ta": "முழு வாய் பனோரமிக் எக்ஸ்ரே",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("45.00"),
            "default_duration_minutes": 10,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "DX-CBCT",
            "names": {
                "es": "CBCT (TAC 3D)",
                "en": "CBCT (3D Scan)",
                "fr": "CBCT (Tomodensitométrie 3D)",
                "ta": "CBCT (முப்பரிமாண ஸ்கேன்)",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("120.00"),
            "default_duration_minutes": 20,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "DX-STUDY",
            "names": {
                "es": "Estudio Ortodóncico",
                "en": "Orthodontic Study",
                "fr": "Étude orthodontique",
                "ta": "பற்சீரமைப்பு ஆய்வு",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("90.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "DX-PHOTO",
            "names": {
                "es": "Fotografías intraorales",
                "en": "Intraoral Photos",
                "fr": "Photographies intraorales",
                "ta": "வாயின் உட்புறப் புகைப்படங்கள்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("30.00"),
            "default_duration_minutes": 15,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "DX-URGENT",
            "names": {
                "es": "Visita de urgencia",
                "en": "Emergency visit",
                "fr": "Visite d'urgence",
                "ta": "அவசர பல் மருத்துவ வருகை",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("60.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "DX-2ND-OPINION",
            "names": {
                "es": "Segunda opinión",
                "en": "Second opinion",
                "fr": "Deuxième avis",
                "ta": "இரண்டாவது மருத்துவக் கருத்து",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("50.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "DX-TELE",
            "names": {
                "es": "Telerradiografía lateral",
                "en": "Lateral cephalogram",
                "fr": "Téléradiographie latérale",
                "ta": "பக்கவாட்டு செபலோமெட்ரிக் எக்ஸ்ரே",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("45.00"),
            "default_duration_minutes": 15,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
    ],
    # ---------- Preventivo ----------
    "preventivo": [
        {
            "internal_code": "PREV-CLEAN",
            "names": {
                "es": "Limpieza dental",
                "en": "Dental Cleaning",
                "fr": "Détartrage",
                "ta": "பல் சுத்தம்",
            },
            "descriptions": {
                "es": "Tartrectomía y pulido",
                "en": "Scaling and polishing",
                "fr": "Détartrage et polissage",
                "ta": "பல் கல் அகற்றுதல் மற்றும் மெருகூட்டுதல்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("60.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PREV-FLUOR",
            "names": {
                "es": "Fluorización",
                "en": "Fluoride Application",
                "fr": "Fluoration",
                "ta": "ஃப்ளூரைடு சிகிச்சை",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("25.00"),
            "default_duration_minutes": 15,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PREV-CHECKUP",
            "names": {
                "es": "Revisión",
                "en": "Checkup",
                "fr": "Contrôle",
                "ta": "பரிசோதனை",
            },
            "descriptions": {
                "es": "Revisión general",
                "en": "General checkup",
                "fr": "Contrôle général",
                "ta": "பொது பல் பரிசோதனை",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("30.00"),
            "default_duration_minutes": 20,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PREV-SEAL",
            "names": {
                "es": "Sellador de fosas y fisuras",
                "en": "Pit and Fissure Sealant",
                "fr": "Scellement de sillons et fissures",
                "ta": "பல் குழிகள் மற்றும் பிளவுகளுக்கான சீலன்ட்",
            },
            "treatment_scope": "tooth",
            "requires_surfaces": True,
            "default_price": Decimal("30.00"),
            "default_duration_minutes": 15,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "sealant",
            "visualization_rules": [occlusal_surface("#06B6D4", "solid_fill")],
            "visualization_config": {"color": "#06B6D4"},
        },
        {
            "internal_code": "PREV-HYGIENE-EDU",
            "names": {
                "es": "Instrucciones de higiene",
                "en": "Oral Hygiene Instruction",
                "fr": "Instructions d'hygiène buccale",
                "ta": "வாய்வழி சுகாதார வழிகாட்டுதல்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("20.00"),
            "default_duration_minutes": 20,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PREV-CLEAN-CURETTAGE",
            "names": {
                "es": "Tartrectomía con curetaje",
                "en": "Scaling with curettage",
                "fr": "Détartrage avec curetage",
                "ta": "கியூரட்டேஜ் உடன் பல் கல் அகற்றுதல்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("110.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PREV-CLEAN-PED",
            "names": {
                "es": "Profilaxis infantil",
                "en": "Pediatric prophylaxis",
                "fr": "Prophylaxie pédiatrique",
                "ta": "குழந்தைகளுக்கான தடுப்பு பல் சுத்தம்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("40.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
    ],
    # ---------- Restauradora ----------
    "restauradora": [
        # Obturaciones (empastes) — un item por material con precio por
        # tramos de superficies (1→5). El precio se calcula al picar las
        # superficies en el diente.
        {
            "internal_code": "REST-COMP",
            "names": {
                "es": "Obturación composite",
                "en": "Composite filling",
                "fr": "Obturation composite",
                "ta": "காம்பசிட் பல் நிரப்புதல்",
            },
            "treatment_scope": "tooth",
            "requires_surfaces": True,
            "default_price": Decimal("60.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "per_surface",
            "surface_prices": {
                "1": "60.00",
                "2": "85.00",
                "3": "110.00",
                "4": "125.00",
                "5": "135.00",
            },
            "odontogram_treatment_type": "filling_composite",
            "visualization_rules": [occlusal_surface("#3B82F6", "solid_fill")],
            "visualization_config": {"color": "#3B82F6"},
        },
        {
            "internal_code": "REST-AMAL",
            "names": {
                "es": "Obturación amalgama",
                "en": "Amalgam filling",
                "fr": "Obturation amalgame",
                "name": "அமல்கம் பல் நிரப்புதல்",
            },
            "treatment_scope": "tooth",
            "requires_surfaces": True,
            "default_price": Decimal("55.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "per_surface",
            "surface_prices": {
                "1": "55.00",
                "2": "75.00",
                "3": "95.00",
                "4": "110.00",
                "5": "120.00",
            },
            "odontogram_treatment_type": "filling_amalgam",
            "visualization_rules": [occlusal_surface("#6B7280", "solid_fill")],
            "visualization_config": {"color": "#6B7280"},
        },
        {
            "internal_code": "REST-TEMP",
            "names": {
                "es": "Obturación temporal",
                "en": "Temporary filling",
                "fr": "Obturation temporaire",
                "ta": "தற்காலிக பல் நிரப்புதல்",
            },
            "treatment_scope": "tooth",
            "requires_surfaces": True,
            "default_price": Decimal("40.00"),
            "default_duration_minutes": 20,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "filling_temporary",
            "visualization_rules": [occlusal_surface("#FBBF24", "solid_fill")],
            "visualization_config": {"color": "#FBBF24"},
        },
        # Incrustaciones
        {
            "internal_code": "REST-INLAY-COMP",
            "names": {
                "es": "Inlay composite",
                "en": "Composite inlay",
                "fr": "Inlay composite",
                "ta": "காம்பசிட் இன்லே",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("180.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "inlay",
            "visualization_rules": [pattern_fill("dots", "#60A5FA")],
            "visualization_config": {"color": "#60A5FA"},
        },
        {
            "internal_code": "REST-INLAY-CER",
            "names": {
                "es": "Inlay cerámico",
                "en": "Ceramic inlay",
                "fr": "Inlay céramique",
                "ta": "செராமிக் இன்லே",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("350.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "inlay",
            "visualization_rules": [pattern_fill("dots", "#38BDF8")],
            "visualization_config": {"color": "#38BDF8"},
        },
        {
            "internal_code": "REST-OVER-COMP",
            "names": {
                "es": "Overlay composite",
                "en": "Composite overlay",
                "fr": "Overlay composite",
                "ta": "காம்பசிட் ஓவர்லே",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("240.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "overlay",
            "visualization_rules": [pattern_fill("grid", "#60A5FA")],
            "visualization_config": {"color": "#60A5FA"},
        },
        {
            "internal_code": "REST-OVER-CER",
            "names": {
                "es": "Overlay cerámico",
                "en": "Ceramic overlay",
                "fr": "Overlay céramique",
                "ta": "செராமிக் ஓவர்லே",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("450.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "overlay",
            "visualization_rules": [pattern_fill("grid", "#38BDF8")],
            "visualization_config": {"color": "#38BDF8"},
        },
        # Carillas (per_tooth pricing — ideal for "carillas múltiples")
        {
            "internal_code": "REST-VEN-COMP",
            "names": {
                "es": "Carilla composite",
                "en": "Composite veneer",
                "fr": "Facette composite",
                "ta": "காம்பசிட் பல் வெனீர்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("280.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "veneer",
            "visualization_rules": [occlusal_surface("#F472B6", "outline")],
            "visualization_config": {"color": "#F472B6"},
        },
        {
            "internal_code": "REST-VEN-PORC",
            "names": {
                "es": "Carilla porcelana",
                "en": "Porcelain veneer",
                "fr": "Facette céramique",
                "ta": "பீங்கான் பல் வெனீர்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("480.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "veneer",
            "visualization_rules": [occlusal_surface("#F472B6", "outline")],
            "visualization_config": {"color": "#F472B6"},
        },
        {
            "internal_code": "REST-VEN-ZIR",
            "names": {
                "es": "Carilla zirconio",
                "en": "Zirconia veneer",
                "fr": "Facette zircone",
                "ta": "சிர்கோனியா பல் வெனீர்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("550.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "veneer",
            "visualization_rules": [occlusal_surface("#EC4899", "outline")],
            "visualization_config": {"color": "#EC4899"},
        },
        # Coronas unitarias / múltiples (per_tooth pricing)
        {
            "internal_code": "REST-CROWN-MC",
            "names": {
                "es": "Corona metal-cerámica",
                "en": "Metal-ceramic crown",
                "fr": "Couronne métal-céramique",
                "ta": "உலோகம்-செராமிக் பல் கிரீடம்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("400.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "crown",
            "visualization_rules": [pattern_fill("diagonal_stripes", "#F59E0B")],
            "visualization_config": {"color": "#F59E0B"},
            "sessions": [
                {
                    "labels": {
                        "es": "Toma de medidas",
                        "en": "Impressions",
                        "fr": "Prise d'empreinte",
                        "ta": "பல் அளவெடுப்பு",
                    },
                    "default_price": Decimal("150.00"),
                },
                {
                    "labels": {
                        "es": "Colocación",
                        "en": "Placement",
                        "fr": "Pose",
                        "ta": "பொருத்துதல்",
                    },
                    "default_price": Decimal("250.00"),
                },
            ],
        },
        {
            "internal_code": "REST-CROWN-ZIR",
            "names": {
                "es": "Corona zirconio",
                "en": "Zirconia crown",
                "fr": "Couronne zircone",
                "ta": "சிர்கோனியா பல் கிரீடம்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("550.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "crown",
            "visualization_rules": [pattern_fill("diagonal_stripes", "#FBBF24")],
            "visualization_config": {"color": "#FBBF24"},
            "sessions": [
                {
                    "labels": {
                        "es": "Toma de medidas",
                        "en": "Impressions",
                        "fr": "Prise d'empreinte",
                        "ta": "பல் அளவெடுப்பு",
                    },
                    "default_price": Decimal("200.00"),
                },
                {
                    "labels": {
                        "es": "Colocación",
                        "en": "Placement",
                        "fr": "Pose",
                        "ta": "பொருத்துதல்",
                    },
                    "default_price": Decimal("350.00"),
                },
            ],
        },
        {
            "internal_code": "REST-CROWN-DISI",
            "names": {
                "es": "Corona disilicato de litio",
                "en": "Lithium disilicate crown",
                "fr": "Couronne disilicate de lithium",
                "ta": "லித்தியம் டிசிலிகேட் பல் கிரீடம்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("650.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "crown",
            "visualization_rules": [pattern_fill("diagonal_stripes", "#FDE68A")],
            "visualization_config": {"color": "#FDE68A"},
            "sessions": [
                {
                    "labels": {
                        "es": "Toma de medidas",
                        "en": "Impressions",
                        "fr": "Prise d'empreinte",
                        "ta": "பல் அளவெடுப்பு",
                    },
                    "default_price": Decimal("250.00"),
                },
                {
                    "labels": {
                        "es": "Colocación",
                        "en": "Placement",
                        "fr": "Pose",
                        "ta": "பொருத்துதல்",
                    },
                    "default_price": Decimal("400.00"),
                },
            ],
        },
        {
            "internal_code": "REST-CROWN-METAL",
            "names": {
                "es": "Corona metal",
                "en": "Metal crown",
                "fr": "Couronne métallique",
                "ta": "உலோக பல் கிரீடம்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("350.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "crown",
            "visualization_rules": [pattern_fill("diagonal_stripes", "#9CA3AF")],
            "visualization_config": {"color": "#9CA3AF"},
        },
        {
            "internal_code": "REST-CROWN-PROV",
            "names": {
                "es": "Corona provisional",
                "en": "Provisional crown",
                "fr": "Couronne provisoire",
                "ta": "தற்காலிக பல் கிரீடம்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("150.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "crown",
            "visualization_rules": [pattern_fill("outline", "#D1D5DB")],
            "visualization_config": {"color": "#D1D5DB"},
        },
        # Coronas sobre implante — render as solid lateral-crown fill
        # (the runtime in ToothDualView treats `crown_on_implant` and
        # `provisional_crown_on_implant` the same way as a bridge).
        {
            "internal_code": "REST-CROWN-IMPL-MC",
            "names": {
                "es": "Corona sobre implante metal-cerámica",
                "en": "Metal-ceramic crown on implant",
                "fr": "Couronne sur implant métal-céramique",
                "ta": "உள்வைப்பின் மீது உலோகம்-செராமிக் பல் கிரீடம்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("600.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "crown_on_implant",
            "visualization_rules": [pattern_fill("solid", "#F59E0B")],
            "visualization_config": {"color": "#F59E0B"},
            "sessions": [
                {
                    "labels": {
                        "es": "Toma de medidas",
                        "en": "Impressions",
                        "fr": "Prise d'empreinte",
                        "ta": "பல் அளவெடுப்பு",
                    },
                    "default_price": Decimal("200.00"),
                },
                {
                    "labels": {
                        "es": "Colocación",
                        "en": "Placement",
                        "fr": "Pose",
                        "ta": "பொருத்துதல்",
                    },
                    "default_price": Decimal("400.00"),
                },
            ],
        },
        {
            "internal_code": "REST-CROWN-IMPL-ZIR",
            "names": {
                "es": "Corona sobre implante zirconio",
                "en": "Zirconia crown on implant",
                "fr": "Couronne sur implant zircone",
                "ta": "உள்வைப்பின் மீது சிர்கோனியா பல் கிரீடம்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("750.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "crown_on_implant",
            "visualization_rules": [pattern_fill("solid", "#FBBF24")],
            "visualization_config": {"color": "#FBBF24"},
            "sessions": [
                {
                    "labels": {
                        "es": "Toma de medidas",
                        "en": "Impressions",
                        "fr": "Prise d'empreinte",
                        "ta": "பல் அளவெடுப்பு",
                    },
                    "default_price": Decimal("250.00"),
                },
                {
                    "labels": {
                        "es": "Colocación",
                        "en": "Placement",
                        "fr": "Pose",
                        "ta": "பொருத்துதல்",
                    },
                    "default_price": Decimal("500.00"),
                },
            ],
        },
        {
            "internal_code": "REST-CROWN-IMPL-PROV",
            "names": {
                "es": "Corona provisional sobre implante",
                "en": "Provisional crown on implant",
                "fr": "Couronne provisoire sur implant",
                "ta": "உள்வைப்பின் மீது தற்காலிக பல் கிரீடம்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("180.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "provisional_crown_on_implant",
            "visualization_rules": [pattern_fill("solid", "#FCD34D")],
            "visualization_config": {"color": "#FCD34D"},
        },
        # Puentes (per_role pricing)
        {
            "internal_code": "REST-BRIDGE-MC",
            "names": {
                "es": "Puente metal-cerámica",
                "en": "Metal-ceramic bridge",
                "fr": "Pont métal-céramique",
                "ta": "உலோகம்-செராமிக் பல் பாலம்",
            },
            "treatment_scope": "multi_tooth",
            "default_price": Decimal("400.00"),
            "default_duration_minutes": 120,
            "vat_type": "exempt",
            "pricing_strategy": "per_role",
            "pricing_config": {"pillar": 400, "pontic": 300},
            "odontogram_treatment_type": "bridge",
            "visualization_rules": [pattern_fill("horizontal_stripes", "#F59E0B")],
            "visualization_config": {"color": "#F59E0B"},
        },
        {
            "internal_code": "REST-BRIDGE-ZIR",
            "names": {
                "es": "Puente zirconio",
                "en": "Zirconia bridge",
                "fr": "Pont zircone",
                "ta": "சிர்கோனியா பல் பாலம்",
            },
            "treatment_scope": "multi_tooth",
            "default_price": Decimal("500.00"),
            "default_duration_minutes": 120,
            "vat_type": "exempt",
            "pricing_strategy": "per_role",
            "pricing_config": {"pillar": 500, "pontic": 400},
            "odontogram_treatment_type": "bridge",
            "visualization_rules": [pattern_fill("horizontal_stripes", "#FBBF24")],
            "visualization_config": {"color": "#FBBF24"},
        },
        {
            "internal_code": "REST-BRIDGE-MARY",
            "names": {
                "es": "Puente Maryland",
                "en": "Maryland bridge",
                "fr": "Pont du Maryland",
                "ta": "மேரிலாண்ட் பல் பாலம்",
            },
            "treatment_scope": "multi_tooth",
            "default_price": Decimal("350.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "per_role",
            "pricing_config": {"pillar": 350, "pontic": 300},
            "odontogram_treatment_type": "bridge",
            "visualization_rules": [pattern_fill("horizontal_stripes", "#FDE68A")],
            "visualization_config": {"color": "#FDE68A"},
        },
        # Férulas
        {
            "internal_code": "REST-SPLINT-OCC",
            "names": {
                "es": "Férula de descarga",
                "en": "Occlusal splint",
                "fr": "Gouttière d'occlusion",
                "ta": "கடிப்பு அழுத்தத் தடுப்பு ஸ்ப்ளிண்ட்",
            },
            "treatment_scope": "global_arch",
            "default_price": Decimal("220.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "splint",
            "visualization_rules": [lateral_icon("splint", "#3B82F6")],
            "visualization_config": {"color": "#3B82F6"},
        },
        {
            "internal_code": "REST-SPLINT-PERIO",
            "names": {
                "es": "Férula periodontal de contención",
                "en": "Periodontal retention splint",
                "fr": "Gouttière de contention parodontale",
                "ta": "பல் சுற்றுத்திசு நிலைப்படுத்தும் ஸ்ப்ளிண்ட்",
            },
            "treatment_scope": "multi_tooth",
            "default_price": Decimal("80.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "splint",
            "visualization_rules": [lateral_icon("splint", "#8B5CF6")],
            "visualization_config": {"color": "#8B5CF6"},
        },
        {
            "internal_code": "REST-RECONSTR",
            "names": {
                "es": "Reconstrucción amplia con composite",
                "en": "Large composite reconstruction",
                "fr": "Reconstruction extensive en composite",
                "ta": "காம்பசிட் மூலம் விரிவான பல் மறுசீரமைப்பு",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("160.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "filling_composite",
            "visualization_rules": [occlusal_surface("#8B5CF6", "solid_fill")],
            "visualization_config": {"color": "#8B5CF6"},
        },
        {
            "internal_code": "REST-FILL-REPAIR",
            "names": {
                "es": "Reparación de obturación",
                "en": "Filling repair",
                "fr": "Réparation d'obturation",
                "ta": "பல் நிரப்புதல் பழுது சரிசெய்தல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("55.00"),
            "default_duration_minutes": 20,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "filling_composite",
            "visualization_rules": [occlusal_surface("#3B82F6", "solid_fill")],
            "visualization_config": {"color": "#3B82F6"},
        },
        {
            "internal_code": "REST-CROWN-RECEMENT",
            "names": {
                "es": "Recementado de corona",
                "en": "Crown recementation",
                "fr": "Recimentation de couronne",
                "ta": "பல் கிரீடத்தை மீண்டும் பொருத்துதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("60.00"),
            "default_duration_minutes": 20,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "crown",
            "visualization_rules": [pattern_fill("diagonal_stripes", "#94A3B8")],
            "visualization_config": {"color": "#94A3B8"},
        },
        {
            "internal_code": "REST-CROWN-POST-ENDO",
            "names": {
                "es": "Corona sobre diente endodonciado",
                "en": "Crown over endodontically treated tooth",
                "fr": "Couronne sur dent dévitalisée",
                "ta": "வேர் சிகிச்சை செய்யப்பட்ட பல்லின் மீது பல் கிரீடம்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("450.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "crown",
            "visualization_rules": [pattern_fill("diagonal_stripes", "#A78BFA")],
            "visualization_config": {"color": "#A78BFA"},
        },
        {
            "internal_code": "REST-HEAL-ABUT",
            "names": {
                "es": "Pilar de cicatrización",
                "en": "Healing abutment",
                "fr": "Pilier de cicatrisation",
                "ta": "குணமடைதல் அபட்மென்ட்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("150.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "implant",
            "visualization_rules": [lateral_icon("implant", "#22C55E")],
            "visualization_config": {"color": "#22C55E"},
        },
        {
            "internal_code": "REST-DEF-ABUT",
            "names": {
                "es": "Pilar definitivo",
                "en": "Definitive abutment",
                "fr": "Pilier définitif",
                "ta": "நிரந்தர அபட்மென்ட்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("250.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "implant",
            "visualization_rules": [lateral_icon("implant", "#16A34A")],
            "visualization_config": {"color": "#16A34A"},
        },
    ],
    # ---------- Endodoncia ----------
    "endodoncia": [
        {
            "internal_code": "ENDO-UNI",
            "names": {
                "es": "Endodoncia unirradicular",
                "en": "Single-root endodontics",
                "fr": "Endodontie uniradiculaire",
                "ta": "ஒரு வேர் பல்லுக்கான வேர் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("180.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "root_canal_full",
            "visualization_rules": [pulp_fill("#8B5CF6", "full")],
            "visualization_config": {"color": "#8B5CF6"},
        },
        {
            "internal_code": "ENDO-BI",
            "names": {
                "es": "Endodoncia birradicular",
                "en": "Two-root endodontics",
                "fr": "Endodontie biradiculaire",
                "ta": "இரு வேர் பல்லுக்கான வேர் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("280.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "root_canal_full",
            "visualization_rules": [pulp_fill("#8B5CF6", "full")],
            "visualization_config": {"color": "#8B5CF6"},
        },
        {
            "internal_code": "ENDO-MULTI",
            "names": {
                "es": "Endodoncia molar",
                "en": "Molar endodontics",
                "fr": "Endodontie molaire",
                "ta": "கடைவாய்ப்பல்லுக்கான வேர் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("380.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "root_canal_full",
            "visualization_rules": [pulp_fill("#7C3AED", "full")],
            "visualization_config": {"color": "#7C3AED"},
            "sessions": [
                {
                    "labels": {
                        "es": "Apertura y conductometría",
                        "en": "Access and length",
                        "fr": "Ouverture et détermination",
                        "ta": "பல் அணுகல் மற்றும் வேர் கால்வாய் நீள அளவீடு",
                    },
                    "default_price": Decimal("130.00"),
                },
                {
                    "labels": {
                        "es": "Limpieza y conformación",
                        "en": "Cleaning and shaping",
                        "fr": "Nettoyage et mise en forme",
                        "ta": "சுத்தம் செய்தல் மற்றும் வடிவமைத்தல்",
                    },
                    "default_price": Decimal("130.00"),
                },
                {
                    "labels": {
                        "es": "Obturación",
                        "en": "Obturation",
                        "fr": "Obturation",
                        "ta": "வேர் கால்வாய் நிரப்புதல்",
                    },
                    "default_price": Decimal("120.00"),
                },
            ],
        },
        {
            "internal_code": "ENDO-RETREAT",
            "names": {
                "es": "Re-tratamiento endodóncico",
                "en": "Endodontic retreatment",
                "fr": "Retraitement endodontique",
                "ta": "மீண்டும் வேர் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("380.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "root_canal_full",
            "visualization_rules": [pulp_fill("#A78BFA", "full")],
            "visualization_config": {"color": "#A78BFA"},
        },
        {
            "internal_code": "ENDO-POST-FIBER",
            "names": {
                "es": "Perno de fibra",
                "en": "Fiber post",
                "fr": "Pivot en fibre",
                "ta": "நார் போஸ்ட்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("120.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "post",
            "visualization_rules": [lateral_icon("post", "#8B5CF6")],
            "visualization_config": {"color": "#8B5CF6"},
        },
        {
            "internal_code": "ENDO-POST-METAL",
            "names": {
                "es": "Perno colado",
                "en": "Cast post",
                "fr": "Pivot coulé",
                "ta": "வார்ப்புப் போஸ்ட்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("180.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "post",
            "visualization_rules": [lateral_icon("post", "#6B7280")],
            "visualization_config": {"color": "#6B7280"},
        },
        {
            "internal_code": "ENDO-URGENT",
            "names": {
                "es": "Apertura cameral urgente",
                "en": "Emergency pulp chamber opening",
                "fr": "Ouverture d'urgence de la chambre pulpaire",
                "ta": "அவசர பற்கூழ் அறை திறப்பு",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("80.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "root_canal_half",
            "visualization_rules": [pulp_fill("#C084FC", "partial_1_2")],
            "visualization_config": {"color": "#C084FC"},
        },
        {
            "internal_code": "ENDO-MED-REFRESH",
            "names": {
                "es": "Recambio de medicación intraconducto",
                "en": "Intracanal medication refresh",
                "fr": "Renouvellement de médicament intraradiculaire",
                "ta": "வேர் கால்வாயின் உள்ளமை மருந்து மாற்றம்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("60.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "root_canal_two_thirds",
            "visualization_rules": [pulp_fill("#C4B5FD", "partial_2_3")],
            "visualization_config": {"color": "#C4B5FD"},
        },
        {
            "internal_code": "ENDO-APICOFORM",
            "names": {
                "es": "Apicoformación",
                "en": "Apexification",
                "fr": "Apexification",
                "ta": "வேர் முனை உருவாக்கச் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("280.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "root_canal_full",
            "visualization_rules": [pulp_fill("#A78BFA", "full")],
            "visualization_config": {"color": "#A78BFA"},
        },
        {
            "internal_code": "ENDO-PED",
            "names": {
                "es": "Endodoncia en pieza temporal",
                "en": "Endodontics on primary tooth",
                "fr": "Endodontie sur dent temporaire",
                "ta": "பால் பல்லுக்கான வேர் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("140.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "root_canal_full",
            "visualization_rules": [pulp_fill("#A78BFA", "full")],
            "visualization_config": {"color": "#A78BFA"},
        },
    ],
    # ---------- Periodoncia ----------
    "periodoncia": [
        {
            "internal_code": "PERIO-SCAL",
            "names": {
                "es": "Tartrectomía simple",
                "en": "Simple scaling",
                "fr": "Détartrage simple",
                "ta": "எளிய பல் கல் அகற்றுதல்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("60.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PERIO-RAR",
            "names": {
                "es": "Raspado y alisado radicular (por cuadrante)",
                "en": "Root scaling and planing (per quadrant)",
                "fr": "Détartrage et surfaçage radiculaire (par quadrant)",
                "ta": "ஒவ்வொரு குவாட்ரண்டிற்குமான வேர் சுத்தம் மற்றும் சமப்படுத்துதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("180.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PERIO-SURG",
            "names": {
                "es": "Cirugía periodontal",
                "en": "Periodontal surgery",
                "fr": "Chirurgie parodontale",
                "ta": "பல் சுற்றுத்திசு அறுவைச் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("450.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PERIO-GRAFT",
            "names": {
                "es": "Injerto gingival",
                "en": "Gingival graft",
                "fr": "Greffe gingivale",
                "ta": "ஈறு திசு ஒட்டுதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("380.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PERIO-BONE",
            "names": {
                "es": "Regeneración ósea guiada",
                "en": "Guided bone regeneration",
                "fr": "Régénération osseuse guidée",
                "ta": "வழிகாட்டப்பட்ட எலும்பு மறுஉருவாக்கம்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("550.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PERIO-MAINT",
            "names": {
                "es": "Mantenimiento periodontal",
                "en": "Periodontal maintenance",
                "fr": "Entretien parodontal",
                "ta": "பல் சுற்றுத்திசு பராமரிப்பு",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("90.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PERIO-CURET-SEXT",
            "names": {
                "es": "Curetaje por sextante",
                "en": "Curettage per sextant",
                "fr": "Curetage par sextant",
                "ta": "ஒவ்வொரு செக்ஸ்டண்டிற்குமான கியூரட்டேஜ்",
            },
            "treatment_scope": "multi_tooth",
            "default_price": Decimal("90.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PERIO-STUDY",
            "names": {
                "es": "Estudio periodontal (sondaje)",
                "en": "Periodontal probing study",
                "fr": "Étude parodontale (sondage)",
                "ta": "பல் சுற்றுத்திசு ஆய்வு (ஆய்வுக் கருவி பரிசோதனை)",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("70.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PERIO-SPLINT-RAR",
            "names": {
                "es": "Férula de contención post-RAR",
                "en": "Post-SRP retention splint",
                "fr": "Gouttière de contention post-DDR",
                "ta": "வேர் சுத்தம் மற்றும் சமப்படுத்தலுக்குப் பிந்தைய நிலைப்படுத்தும் ஸ்ப்ளிண்ட்",
            },
            "treatment_scope": "multi_tooth",
            "default_price": Decimal("150.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "splint",
            "visualization_rules": [lateral_icon("splint", "#8B5CF6")],
            "visualization_config": {"color": "#8B5CF6"},
        },
        {
            "internal_code": "PERIO-GINGIV",
            "names": {
                "es": "Gingivectomía",
                "en": "Gingivectomy",
                "fr": "Gingivectomie",
                "ta": "ஈறு அகற்றுச் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("180.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PERIO-SURG-RESECT",
            "names": {
                "es": "Cirugía periodontal resectiva",
                "en": "Resective periodontal surgery",
                "fr": "Chirurgie parodontale résécative",
                "ta": "பல் சுற்றுத்திசு அகற்றுச் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("480.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PERIO-SURG-REGEN",
            "names": {
                "es": "Cirugía periodontal regenerativa",
                "en": "Regenerative periodontal surgery",
                "fr": "Chirurgie parodontale régénérative",
                "ta": "பல் சுற்றுத்திசு மறுஉருவாக்க அறுவைச் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("580.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
    ],
    # ---------- Cirugía ----------
    "cirugia": [
        {
            "internal_code": "SURG-EXT-SIMPLE",
            "names": {
                "es": "Extracción simple",
                "en": "Simple extraction",
                "fr": "Extraction simple",
                "ta": "எளிய பல் அகற்றுதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("80.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "extraction",
            "visualization_rules": [lateral_icon("extraction", "#DC2626")],
            "visualization_config": {"color": "#DC2626"},
        },
        {
            "internal_code": "SURG-EXT-COMPLEX",
            "names": {
                "es": "Extracción compleja",
                "en": "Complex extraction",
                "fr": "Extraction compliquée",
                "ta": "சிக்கலான பல் அகற்றுதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("140.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "extraction",
            "visualization_rules": [lateral_icon("extraction", "#DC2626")],
            "visualization_config": {"color": "#DC2626"},
        },
        {
            "internal_code": "SURG-EXT-3MOLAR",
            "names": {
                "es": "Extracción tercer molar",
                "en": "Wisdom tooth extraction",
                "fr": "Extraction de la dent de sagesse",
                "ta": "ஞானப்பல் அகற்றுதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("200.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "extraction",
            "visualization_rules": [lateral_icon("extraction", "#DC2626")],
            "visualization_config": {"color": "#DC2626"},
        },
        {
            "internal_code": "SURG-EXT-OST",
            "names": {
                "es": "Extracción quirúrgica con ostectomía",
                "en": "Surgical extraction with osteotomy",
                "fr": "Extraction chirurgicale avec ostéotomie",
                "ta": "எலும்பு அகற்றலுடன் கூடிய அறுவை பல் அகற்றுதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("280.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "extraction",
            "visualization_rules": [lateral_icon("extraction", "#991B1B")],
            "visualization_config": {"color": "#991B1B"},
        },
        {
            "internal_code": "SURG-IMP-TI",
            "names": {
                "es": "Implante de titanio",
                "en": "Titanium implant",
                "fr": "Implant en titane",
                "ta": "டைட்டானியம் பல் உள்வைப்பு",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("1100.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "implant",
            "visualization_rules": [lateral_icon("implant", "#10B981")],
            "visualization_config": {"color": "#10B981"},
            "sessions": [
                {
                    "labels": {
                        "es": "Cirugía de implante",
                        "en": "Implant surgery",
                        "fr": "Chirurgie implantaire",
                        "ta": "பல் உள்வைப்பு அறுவைச் சிகிச்சை",
                    },
                    "default_price": Decimal("700.00"),
                },
                {
                    "labels": {
                        "es": "Pilar de cicatrización",
                        "en": "Healing abutment",
                        "fr": "Pilier de cicatrisation",
                        "ta": "குணமடைதல் அபட்மென்ட்",
                    },
                    "default_price": Decimal("150.00"),
                },
                {
                    "labels": {
                        "es": "Colocación de corona",
                        "en": "Crown placement",
                        "fr": "Pose de couronne",
                        "ta": "பல் கிரீடம் பொருத்துதல்",
                    },
                    "default_price": Decimal("250.00"),
                },
            ],
        },
        {
            "internal_code": "SURG-IMP-ZIR",
            "names": {
                "es": "Implante de zirconio",
                "en": "Zirconia implant",
                "fr": "Implant en zircone",
                "ta": "சிர்கோனியா பல் உள்வைப்பு",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("1500.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "implant",
            "visualization_rules": [lateral_icon("implant", "#14B8A6")],
            "visualization_config": {"color": "#14B8A6"},
        },
        {
            "internal_code": "SURG-SINUS",
            "names": {
                "es": "Elevación de seno",
                "en": "Sinus lift",
                "fr": "Élévation sinusienne",
                "ta": "சைனஸ் உயர்த்துதல் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("800.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-BONE-GRAFT",
            "names": {
                "es": "Injerto óseo",
                "en": "Bone graft",
                "fr": "Greffe osseuse",
                "ta": "எலும்பு ஒட்டுதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("450.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-APEC",
            "names": {
                "es": "Apicectomía",
                "en": "Apicoectomy",
                "fr": "Apicectomie",
                "ta": "வேர் முனை அறுவைச் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("320.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "apicoectomy",
            "visualization_rules": [lateral_icon("apicoectomy", "#F59E0B")],
            "visualization_config": {"color": "#F59E0B"},
        },
        {
            "internal_code": "SURG-FREN",
            "names": {
                "es": "Frenectomía",
                "en": "Frenectomy",
                "fr": "Frénectomie",
                "ta": "தசை இணைப்புத் திசு அகற்றுச் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("180.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-BIOPSY",
            "names": {"es": "Biopsia", "en": "Biopsy", "fr": "Biopsie", "ta": "திசுப் பரிசோதனை"},
            "treatment_scope": "tooth",
            "default_price": Decimal("220.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-CONN-GRAFT",
            "names": {
                "es": "Injerto de tejido conectivo",
                "en": "Connective tissue graft",
                "fr": "Greffe de tissu conjonctif",
                "ta": "இணைப்புத் திசு ஒட்டுதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("420.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-CROWN-LENGTH",
            "names": {
                "es": "Alargamiento coronario",
                "en": "Crown lengthening",
                "fr": "Allongement coronaire",
                "ta": "பல் கிரீட நீட்டிப்பு சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("380.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-CYST",
            "names": {
                "es": "Exéresis de quiste",
                "en": "Cyst removal",
                "fr": "Exérèse de kyste",
                "ta": "நீர்க்கட்டி அகற்றுதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("550.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "apicoectomy",
            "visualization_rules": [lateral_icon("apicoectomy", "#F59E0B")],
            "visualization_config": {"color": "#F59E0B"},
        },
        {
            "internal_code": "SURG-EXT-INCLUIDO",
            "names": {
                "es": "Extracción de pieza incluida",
                "en": "Impacted tooth extraction",
                "fr": "Extraction de dent incluse",
                "ta": "புதைந்த பல் அகற்றுதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("250.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "extraction",
            "visualization_rules": [lateral_icon("extraction", "#DC2626")],
            "visualization_config": {"color": "#DC2626"},
        },
        {
            "internal_code": "SURG-BONE-REGUL",
            "names": {
                "es": "Regularización ósea",
                "en": "Bone reshaping",
                "fr": "Régularisation osseuse",
                "ta": "எலும்பு வடிவச் சீரமைப்பு",
            },
            "treatment_scope": "multi_tooth",
            "default_price": Decimal("220.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-PRP",
            "names": {
                "es": "Plasma rico en plaquetas",
                "en": "Platelet-rich plasma",
                "fr": "Plasma riche en plaquettes",
                "ta": "பிளேட்லெட் நிறைந்த பிளாஸ்மா",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("180.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-PERIIMP",
            "names": {
                "es": "Tratamiento de periimplantitis",
                "en": "Peri-implantitis treatment",
                "fr": "Traitement de péri-implantite",
                "ta": "பல் உள்வைப்பைச் சுற்றிய தொற்று சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("420.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-BONE-VERT",
            "names": {
                "es": "Aumento óseo vertical",
                "en": "Vertical bone augmentation",
                "fr": "Augmentation osseuse verticale",
                "ta": "செங்குத்து எலும்பு பெருக்கச் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("750.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-BONE-HORIZ",
            "names": {
                "es": "Aumento óseo horizontal",
                "en": "Horizontal bone augmentation",
                "fr": "Augmentation osseuse horizontale",
                "ta": "கிடைமட்ட எலும்பு பெருக்கச் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("650.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-SINUS-CLOSED",
            "names": {
                "es": "Elevación de seno cerrada (atraumática)",
                "en": "Closed sinus lift (atraumatic)",
                "fr": "Élévation sinusienne fermée (atraumatique)",
                "ta": "மூடிய சைனஸ் உயர்த்துதல் (காயமில்லா முறை)",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("500.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
    ],
    # ---------- Ortodoncia ----------
    "ortodoncia": [
        {
            "internal_code": "ORTO-METAL",
            "names": {
                "es": "Ortodoncia brackets metálicos",
                "en": "Metal braces",
                "fr": "Bagues métalliques",
                "ta": "உலோக பற்சீரமைப்பு பிரேஸ்கள்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("2500.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-CERAM",
            "names": {
                "es": "Ortodoncia brackets estéticos",
                "en": "Ceramic braces",
                "fr": "Bagues esthétiques",
                "ta": "செராமிக் பற்சீரமைப்பு பிரேஸ்கள்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("3500.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-LINGUAL",
            "names": {
                "es": "Ortodoncia lingual",
                "en": "Lingual braces",
                "fr": "Bagues linguales",
                "ta": "நாக்குப்புற பற்சீரமைப்பு பிரேஸ்கள்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("5500.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-INV-LITE",
            "names": {
                "es": "Invisalign Lite",
                "en": "Invisalign Lite",
                "fr": "Invisalign Lite",
                "ta": "Invisalign Lite",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("2900.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-INV-FULL",
            "names": {
                "es": "Invisalign Full",
                "en": "Invisalign Full",
                "fr": "Invisalign Full",
                "ta": "Invisalign Full",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("4500.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-BRACK",
            "names": {
                "es": "Bracket individual (reposición)",
                "en": "Bracket (replacement)",
                "fr": "Bracket individuel (remplacement)",
                "ta": "தனிப்பட்ட பிராக்கெட் மாற்றீடு",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("45.00"),
            "default_duration_minutes": 20,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "bracket",
            "visualization_rules": [lateral_icon("bracket", "#475569")],
            "visualization_config": {"color": "#475569"},
        },
        {
            "internal_code": "ORTO-REVIEW",
            "names": {
                "es": "Revisión de ortodoncia",
                "en": "Orthodontic review",
                "fr": "Contrôle d'orthodontie",
                "ta": "பற்சீரமைப்பு தொடர் பரிசோதனை",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("40.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-RET-FIX",
            "names": {
                "es": "Retenedor fijo",
                "en": "Fixed retainer",
                "fr": "Contention fixe",
                "ta": "நிலையான பற்சீரமைப்பு ரிடெய்னர்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("180.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "retainer",
            "visualization_rules": [lateral_icon("retainer", "#0EA5E9")],
            "visualization_config": {"color": "#0EA5E9"},
        },
        {
            "internal_code": "ORTO-RET-REM",
            "names": {
                "es": "Retenedor removible",
                "en": "Removable retainer",
                "fr": "Contention amovible",
                "ta": "அகற்றக்கூடிய பற்சீரமைப்பு ரிடெய்னர்",
            },
            "treatment_scope": "global_arch",
            "default_price": Decimal("120.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-ATTACH",
            "names": {
                "es": "Ataches de Invisalign",
                "en": "Invisalign attachments",
                "fr": "Attachements Invisalign",
                "ta": "Invisalign இணைப்புகள்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("60.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "attachment",
            "visualization_rules": [lateral_icon("attachment", "#0891B2")],
            "visualization_config": {"color": "#0891B2"},
        },
        {
            "internal_code": "ORTO-BRACK-CEMENT",
            "names": {
                "es": "Cementado de bracket",
                "en": "Bracket bonding",
                "fr": "Collage de bracket",
                "ta": "பிராக்கெட் ஒட்டுதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("35.00"),
            "default_duration_minutes": 15,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "bracket",
            "visualization_rules": [lateral_icon("bracket", "#475569")],
            "visualization_config": {"color": "#475569"},
        },
        {
            "internal_code": "ORTO-BRACK-DEBOND",
            "names": {
                "es": "Descementado de brackets",
                "en": "Bracket removal",
                "fr": "Dépose des bagues",
                "ta": "பிராக்கெட் அகற்றுதல்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("120.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-SEPARATOR",
            "names": {
                "es": "Separadores ortodóncicos",
                "en": "Orthodontic separators",
                "fr": "Séparateurs orthodontiques",
                "ta": "பற்சீரமைப்பு இடைவெளி பிரிப்பிகள்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("50.00"),
            "default_duration_minutes": 20,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-PALATAL-EXP",
            "names": {
                "es": "Expansor palatino",
                "en": "Palatal expander",
                "fr": "Dilatateur palatin",
                "ta": "அண்ணப் பகுதி விரிவாக்கி",
            },
            "treatment_scope": "global_arch",
            "default_price": Decimal("450.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-TAD",
            "names": {
                "es": "Microtornillo / anclaje esquelético temporal (TAD)",
                "en": "Temporary anchorage device (TAD)",
                "fr": "Dispositif d'ancrage temporaire (TAD)",
                "ta": "தற்காலிக எலும்பு நங்கூரக் கருவி (TAD)",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("250.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
        },
    ],
    # ---------- Estética ----------
    "estetica": [
        {
            "internal_code": "EST-BLAN-AMB",
            "names": {
                "es": "Blanqueamiento ambulatorio",
                "en": "At-home whitening",
                "fr": "Blanchiment à domicile",
                "ta": "வீட்டிலேயே பற்களை வெண்மைப்படுத்துதல்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("250.00"),
            "default_duration_minutes": 30,
            "vat_type": "standard",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "EST-BLAN-CLIN",
            "names": {
                "es": "Blanqueamiento en clínica",
                "en": "In-office whitening",
                "fr": "Blanchiment en cabinet",
                "ta": "மருத்துவமனையில் பற்களை வெண்மைப்படுத்துதல்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("400.00"),
            "default_duration_minutes": 90,
            "vat_type": "standard",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "EST-BLAN-COMBO",
            "names": {
                "es": "Blanqueamiento combinado",
                "en": "Combined whitening",
                "fr": "Blanchiment combiné",
                "ta": "ஒருங்கிணைந்த பற்கள் வெண்மைப்படுத்துதல்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("550.00"),
            "default_duration_minutes": 120,
            "vat_type": "standard",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "EST-MICROAB",
            "names": {
                "es": "Microabrasión",
                "en": "Microabrasion",
                "fr": "Microabrasion",
                "ta": "நுண் உராய்வு சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("120.00"),
            "default_duration_minutes": 45,
            "vat_type": "standard",
            "pricing_strategy": "per_tooth",
        },
        {
            "internal_code": "EST-REMIN",
            "names": {
                "es": "Remineralización estética",
                "en": "Aesthetic remineralization",
                "fr": "Reminéralisation esthétique",
                "ta": "அழகியல் பல் கனிமமயமாக்கல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("90.00"),
            "default_duration_minutes": 30,
            "vat_type": "standard",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "EST-COMP-AESTH",
            "names": {
                "es": "Reconstrucción estética con composite",
                "en": "Aesthetic composite reconstruction",
                "fr": "Reconstruction esthétique en composite",
                "ta": "காம்பசிட் மூலம் அழகியல் பல் மறுசீரமைப்பு",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("220.00"),
            "default_duration_minutes": 60,
            "vat_type": "standard",
            "pricing_strategy": "per_tooth",
        },
        {
            "internal_code": "EST-PIG-REMOVE",
            "names": {
                "es": "Eliminación de pigmentación",
                "en": "Pigmentation removal",
                "fr": "Élimination des pigmentations",
                "ta": "பல் நிறமாற்றப் படிவங்களை அகற்றுதல்",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("90.00"),
            "default_duration_minutes": 30,
            "vat_type": "standard",
            "pricing_strategy": "flat",
        },
    ],
    # ---------- Prótesis ----------
    "protesis": [
        {
            "internal_code": "PROT-FULL-SUP",
            "names": {
                "es": "Prótesis completa superior",
                "en": "Full upper denture",
                "fr": "Prothèse complète supérieure",
                "ta": "மேல் தாடைக்கான முழு செயற்கைப் பற்கள்",
            },
            "treatment_scope": "global_arch",
            "default_price": Decimal("900.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PROT-FULL-INF",
            "names": {
                "es": "Prótesis completa inferior",
                "en": "Full lower denture",
                "fr": "Prothèse complète inférieure",
                "ta": "கீழ் தாடைக்கான முழு செயற்கைப் பற்கள்",
            },
            "treatment_scope": "global_arch",
            "default_price": Decimal("900.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PROT-PART-METAL",
            "names": {
                "es": "Prótesis parcial esquelética",
                "en": "Partial metal denture",
                "fr": "Prothèse partielle squelettique",
                "ta": "பகுதி உலோக செயற்கைப் பற்கள்",
            },
            "treatment_scope": "global_arch",
            "default_price": Decimal("750.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PROT-PART-ACR",
            "names": {
                "es": "Prótesis parcial acrílica",
                "en": "Partial acrylic denture",
                "fr": "Prothèse partielle acrylique",
                "ta": "பகுதி அக்ரிலிக் செயற்கைப் பற்கள்",
            },
            "treatment_scope": "global_arch",
            "default_price": Decimal("450.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PROT-OVERDENT",
            "names": {
                "es": "Sobredentadura sobre implantes",
                "en": "Implant-supported overdenture",
                "fr": "Surprothèse sur implants",
                "ta": "பல் உள்வைப்பு ஆதரவு செயற்கைப் பற்கள்",
            },
            "treatment_scope": "global_arch",
            "default_price": Decimal("1800.00"),
            "default_duration_minutes": 120,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PROT-REBASE",
            "names": {
                "es": "Rebasado de prótesis",
                "en": "Denture reline",
                "fr": "Rebasage de prothèse",
                "ta": "செயற்கைப் பல் அடிப்பகுதி மறுசீரமைப்பு",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("120.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PROT-REPAIR",
            "names": {
                "es": "Reparación de prótesis",
                "en": "Denture repair",
                "fr": "Réparation de prothèse",
                "ta": "செயற்கைப் பல் பழுது சரிசெய்தல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("80.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PROT-PROV-REMOV",
            "names": {
                "es": "Prótesis provisional removible",
                "en": "Provisional removable denture",
                "fr": "Prothèse provisoire amovible",
                "ta": "தற்காலிக அகற்றக்கூடிய செயற்கைப் பற்கள்",
            },
            "treatment_scope": "global_arch",
            "default_price": Decimal("350.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PROT-OCC-ADJ",
            "names": {
                "es": "Ajuste oclusal",
                "en": "Occlusal adjustment",
                "fr": "Ajustement occlusal",
                "ta": "கடிப்பு சீரமைப்பு",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("60.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
    ],
    # ---------- Odontopediatría ----------
    "pediatrica": [
        {
            "internal_code": "PED-FLUOR",
            "names": {
                "es": "Fluorización pediátrica",
                "en": "Pediatric fluoride",
                "fr": "Fluoration pédiatrique",
                "ta": "குழந்தைகளுக்கான ஃப்ளூரைடு சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("25.00"),
            "default_duration_minutes": 15,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PED-SEAL",
            "names": {
                "es": "Sellador pediátrico",
                "en": "Pediatric sealant",
                "fr": "Scellement de sillons pédiatrique",
                "ta": "குழந்தைகளுக்கான பல் குழி மற்றும் பிளவு சீலன்ட்",
            },
            "treatment_scope": "tooth",
            "requires_surfaces": True,
            "default_price": Decimal("25.00"),
            "default_duration_minutes": 15,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "sealant",
            "visualization_rules": [occlusal_surface("#06B6D4", "solid_fill")],
            "visualization_config": {"color": "#06B6D4"},
        },
        {
            "internal_code": "PED-PULPOTOMY",
            "names": {
                "es": "Pulpotomía",
                "en": "Pulpotomy",
                "fr": "Pulpotomie",
                "ta": "குழந்தைகளுக்கான பற்கூழ் பகுதி அகற்றுச் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("150.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "root_canal_half",
            "visualization_rules": [pulp_fill("#A78BFA", "partial_1_2")],
            "visualization_config": {"color": "#A78BFA"},
        },
        {
            "internal_code": "PED-CROWN-SS",
            "names": {
                "es": "Corona preformada pediátrica",
                "en": "Stainless steel crown",
                "fr": "Couronne préformée pédiatrique",
                "ta": "குழந்தைகளுக்கான ஸ்டெயின்லெஸ் ஸ்டீல் பல் கிரீடம்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("180.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "per_tooth",
            "odontogram_treatment_type": "crown",
            "visualization_rules": [pattern_fill("diagonal_stripes", "#9CA3AF")],
            "visualization_config": {"color": "#9CA3AF"},
        },
        {
            "internal_code": "PED-SPACE",
            "names": {
                "es": "Mantenedor de espacio simple",
                "en": "Simple space maintainer",
                "fr": "Mainteneur d'espace simple",
                "ta": "எளிய பல் இடைவெளி பராமரிப்பி",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("150.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PED-SPACE-COMPOUND",
            "names": {
                "es": "Mantenedor de espacio compuesto",
                "en": "Compound space maintainer",
                "fr": "Mainteneur d'espace composé",
                "ta": "கூட்டு பல் இடைவெளி பராமரிப்பி",
            },
            "treatment_scope": "multi_tooth",
            "default_price": Decimal("220.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PED-EXT-TEMP",
            "names": {
                "es": "Extracción de pieza temporal",
                "en": "Primary tooth extraction",
                "fr": "Extraction de dent temporaire",
                "ta": "பால் பல் அகற்றுதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("55.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "extraction",
            "visualization_rules": [lateral_icon("extraction", "#DC2626")],
            "visualization_config": {"color": "#DC2626"},
        },
        {
            "internal_code": "PED-FILL-TEMP",
            "names": {
                "es": "Obturación en dentición temporal",
                "en": "Primary tooth filling",
                "fr": "Obturation sur dent temporaire",
                "ta": "பால் பல் நிரப்புதல்",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("45.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "per_surface",
            "surface_prices": {
                "1": "45.00",
                "2": "65.00",
                "3": "85.00",
                "4": "95.00",
                "5": "105.00",
            },
            "requires_surfaces": True,
            "odontogram_treatment_type": "filling_composite",
            "visualization_rules": [occlusal_surface("#3B82F6", "solid_fill")],
            "visualization_config": {"color": "#3B82F6"},
        },
        {
            "internal_code": "PED-PULPECTOMY",
            "names": {
                "es": "Pulpectomía pediátrica",
                "en": "Pediatric pulpectomy",
                "fr": "Pulpectomie pédiatrique",
                "ta": "குழந்தைகளுக்கான பற்கூழ் முழு அகற்றுச் சிகிச்சை",
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("160.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
            "odontogram_treatment_type": "root_canal_full",
            "visualization_rules": [pulp_fill("#A78BFA", "full")],
            "visualization_config": {"color": "#A78BFA"},
        },
    ],
}


# ============================================================================
# Seeding logic
# ============================================================================


async def _ensure_vat_types(db: AsyncSession, clinic_id: UUID) -> dict[str, UUID]:
    vat_type_map: dict[str, UUID] = {}
    for vat_data in VAT_TYPES:
        existing = await db.execute(
            select(VatType).where(
                VatType.clinic_id == clinic_id,
                VatType.rate == vat_data["rate"],
            )
        )
        vat = existing.scalar_one_or_none()
        if not vat:
            vat = VatType(
                clinic_id=clinic_id,
                names=vat_data["names"],
                rate=vat_data["rate"],
                is_default=vat_data["is_default"],
                is_system=True,
            )
            db.add(vat)
            await db.flush()
        vat_type_map[vat_data["key"]] = vat.id
    return vat_type_map


async def seed_catalog(db: AsyncSession, clinic_id: UUID) -> dict:
    """Seed catalog items for a clinic. Idempotent (skips existing internal_codes)."""
    vat_type_map = await _ensure_vat_types(db, clinic_id)

    categories_created = 0
    items_created = 0
    category_map: dict[str, UUID] = {}

    for cat_data in CATEGORIES:
        existing = await db.execute(
            select(TreatmentCategory).where(
                TreatmentCategory.clinic_id == clinic_id,
                TreatmentCategory.key == cat_data["key"],
            )
        )
        category = existing.scalar_one_or_none()
        if not category:
            category = TreatmentCategory(clinic_id=clinic_id, is_system=True, **cat_data)
            db.add(category)
            await db.flush()
            categories_created += 1
        category_map[cat_data["key"]] = category.id

    for category_key, treatments in TREATMENTS.items():
        category_id = category_map.get(category_key)
        if not category_id:
            continue

        for treatment_raw in treatments:
            treatment_data = dict(treatment_raw)

            odontogram_type = treatment_data.pop("odontogram_treatment_type", None)
            viz_rules = treatment_data.pop("visualization_rules", None)
            viz_config = treatment_data.pop("visualization_config", None) or {}
            vat_type_key = treatment_data.pop("vat_type", "exempt")
            vat_type_id = vat_type_map.get(vat_type_key, vat_type_map.get("exempt"))
            session_template = treatment_data.pop("sessions", None)

            existing = await db.execute(
                select(TreatmentCatalogItem).where(
                    TreatmentCatalogItem.clinic_id == clinic_id,
                    TreatmentCatalogItem.internal_code == treatment_data["internal_code"],
                )
            )
            if existing.scalar_one_or_none():
                continue

            item = TreatmentCatalogItem(
                clinic_id=clinic_id,
                category_id=category_id,
                vat_type_id=vat_type_id,
                is_system=True,
                **treatment_data,
            )
            db.add(item)
            await db.flush()

            if odontogram_type and viz_rules:
                mapping = TreatmentOdontogramMapping(
                    clinic_id=clinic_id,
                    catalog_item_id=item.id,
                    odontogram_treatment_type=odontogram_type,
                    visualization_rules=viz_rules,
                    visualization_config=viz_config,
                    clinical_category=category_key,
                )
                db.add(mapping)

            # Per-session template (multi-session billing). Treatment plans
            # snapshot this when the item is added — see ``treatment_plan``.
            if session_template:
                for idx, session_data in enumerate(session_template, start=1):
                    db.add(
                        CatalogItemSession(
                            catalog_item_id=item.id,
                            sequence=session_data.get("sequence") or idx,
                            labels=session_data.get("labels") or {},
                            default_price=session_data["default_price"],
                        )
                    )

            items_created += 1

    await db.flush()

    return {
        "categories": categories_created,
        "items": items_created,
        "vat_types": len(vat_type_map),
    }


async def seed_all_clinics(db: AsyncSession) -> dict:
    """Seed catalog for every clinic in the database."""
    from app.core.auth.models import Clinic

    result = await db.execute(select(Clinic))
    clinics = result.scalars().all()

    summary = {}
    for clinic in clinics:
        summary[str(clinic.id)] = await seed_catalog(db, clinic.id)
    return summary
