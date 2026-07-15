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
        "names": {"es": "Exento", "en": "Exempt", "fr": "Exonéré"},
        "rate": 0.0,
        "is_default": True,
    },
    {
        "key": "reduced",
        "names": {"es": "Reducido (10%)", "en": "Reduced (10%)", "fr": "Réduit (10%)"},
        "rate": 10.0,
        "is_default": False,
    },
    {
        "key": "standard",
        "names": {"es": "General (21%)", "en": "Standard (21%)", "fr": "Général (21%)"},
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
        "names": {"es": "Diagnóstico", "en": "Diagnostic", "fr": "Diagnostic"},
        "descriptions": {
            "es": "Servicios de diagnóstico y evaluación",
            "en": "Diagnostic and evaluation services",
            "fr": "Services de diagnostique et d'évaluation",
        },
        "display_order": 1,
        "icon": "i-lucide-stethoscope",
    },
    {
        "key": "preventivo",
        "names": {"es": "Preventivo", "en": "Preventive", "fr": "Préventif"},
        "descriptions": {
            "es": "Prevención e higiene dental",
            "en": "Preventive and hygiene",
            "fr": "Prévention et hygiène dentaire",
        },
        "display_order": 2,
        "icon": "i-lucide-shield-check",
    },
    {
        "key": "restauradora",
        "names": {"es": "Restauradora", "en": "Restorative", "fr": "Restauration"},
        "descriptions": {
            "es": "Restauración dental",
            "en": "Dental restoration",
            "fr": "Restauration dentaire",
        },
        "display_order": 3,
        "icon": "i-lucide-brush",
    },
    {
        "key": "endodoncia",
        "names": {"es": "Endodoncia", "en": "Endodontics", "fr": "Endodontie"},
        "descriptions": {
            "es": "Tratamientos de conducto radicular",
            "en": "Root canal treatments",
            "fr": "Traitements des canaux radiculaires",
        },
        "display_order": 4,
        "icon": "i-lucide-activity",
    },
    {
        "key": "periodoncia",
        "names": {"es": "Periodoncia", "en": "Periodontics", "fr": "Parodontie"},
        "descriptions": {
            "es": "Encías y tejidos de soporte",
            "en": "Gums and supporting tissues",
            "fr": "Gencives et tissus de soutien",
        },
        "display_order": 5,
        "icon": "i-lucide-heart-pulse",
    },
    {
        "key": "cirugia",
        "names": {"es": "Cirugía", "en": "Surgery", "fr": "Chirurgie"},
        "descriptions": {
            "es": "Procedimientos quirúrgicos dentales",
            "en": "Dental surgical procedures",
            "fr": "Procédures chirurgicales dentaires",
        },
        "display_order": 6,
        "icon": "i-lucide-scissors",
    },
    {
        "key": "ortodoncia",
        "names": {"es": "Ortodoncia", "en": "Orthodontics", "fr": "Orthodontie"},
        "descriptions": {
            "es": "Ortodoncia y alineación",
            "en": "Orthodontics and alignment",
            "fr": "Orthodontie et alignement",
        },
        "display_order": 7,
        "icon": "i-lucide-align-center",
    },
    {
        "key": "estetica",
        "names": {"es": "Estética", "en": "Cosmetic", "fr": "Esthétique"},
        "descriptions": {
            "es": "Estética dental",
            "en": "Cosmetic dentistry",
            "fr": "Esthétique dentaire",
        },
        "display_order": 8,
        "icon": "i-lucide-sparkles",
    },
    {
        "key": "protesis",
        "names": {"es": "Prótesis", "en": "Prosthetics", "fr": "Prothèses"},
        "descriptions": {
            "es": "Prótesis y férulas",
            "en": "Prosthetics and splints",
            "fr": "Prothèses et gouttières",
        },
        "display_order": 9,
        "icon": "i-lucide-puzzle",
    },
    {
        "key": "pediatrica",
        "names": {"es": "Odontopediatría", "en": "Pediatric", "fr": "Odontologie pédiatrique"},
        "descriptions": {
            "es": "Tratamientos para niños",
            "en": "Treatments for children",
            "fr": "Traitements pour enfants",
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
            "names": {"es": "Primera Visita", "en": "First Visit", "fr": "Première visite"},
            "descriptions": {
                "es": "Consulta inicial con exploración y diagnóstico",
                "en": "Initial consultation with examination and diagnosis",
                "fr": "Consultation initiale avec examen et diagnostique",
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
            "names": {"es": "Revisión", "en": "Follow-up", "fr": "Contrôle"},
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
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("60.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "DX-2ND-OPINION",
            "names": {"es": "Segunda opinión", "en": "Second opinion", "fr": "Deuxième avis"},
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
            "names": {"es": "Limpieza dental", "en": "Dental Cleaning", "fr": "Détartrage"},
            "descriptions": {
                "es": "Tartrectomía y pulido",
                "en": "Scaling and polishing",
                "fr": "Détartrage et polissage",
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("60.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PREV-FLUOR",
            "names": {"es": "Fluorización", "en": "Fluoride Application", "fr": "Fluoration"},
            "treatment_scope": "global_mouth",
            "default_price": Decimal("25.00"),
            "default_duration_minutes": 15,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PREV-CHECKUP",
            "names": {"es": "Revisión", "en": "Checkup", "fr": "Contrôle"},
            "descriptions": {
                "es": "Revisión general",
                "en": "General checkup",
                "fr": "Contrôle général",
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
            "names": {"es": "Inlay composite", "en": "Composite inlay", "fr": "Inlay composite"},
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
            "names": {"es": "Inlay cerámico", "en": "Ceramic inlay", "fr": "Inlay céramique"},
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
            "names": {"es": "Overlay cerámico", "en": "Ceramic overlay", "fr": "Overlay céramique"},
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
            "names": {"es": "Carilla zirconio", "en": "Zirconia veneer", "fr": "Facette zircone"},
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
                    },
                    "default_price": Decimal("150.00"),
                },
                {
                    "labels": {"es": "Colocación", "en": "Placement", "fr": "Pose"},
                    "default_price": Decimal("250.00"),
                },
            ],
        },
        {
            "internal_code": "REST-CROWN-ZIR",
            "names": {"es": "Corona zirconio", "en": "Zirconia crown", "fr": "Couronne zircone"},
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
                    },
                    "default_price": Decimal("200.00"),
                },
                {
                    "labels": {"es": "Colocación", "en": "Placement", "fr": "Pose"},
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
                    },
                    "default_price": Decimal("250.00"),
                },
                {
                    "labels": {"es": "Colocación", "en": "Placement", "fr": "Pose"},
                    "default_price": Decimal("400.00"),
                },
            ],
        },
        {
            "internal_code": "REST-CROWN-METAL",
            "names": {"es": "Corona metal", "en": "Metal crown", "fr": "Couronne métallique"},
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
                    },
                    "default_price": Decimal("200.00"),
                },
                {
                    "labels": {"es": "Colocación", "en": "Placement", "fr": "Pose"},
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
                    },
                    "default_price": Decimal("250.00"),
                },
                {
                    "labels": {"es": "Colocación", "en": "Placement", "fr": "Pose"},
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
            "names": {"es": "Puente zirconio", "en": "Zirconia bridge", "fr": "Pont zircone"},
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
            "names": {"es": "Puente Maryland", "en": "Maryland bridge", "fr": "Pont du Maryland"},
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
                    },
                    "default_price": Decimal("130.00"),
                },
                {
                    "labels": {
                        "es": "Limpieza y conformación",
                        "en": "Cleaning and shaping",
                        "fr": "Nettoyage et mise en forme",
                    },
                    "default_price": Decimal("130.00"),
                },
                {
                    "labels": {"es": "Obturación", "en": "Obturation", "fr": "Obturation"},
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
            "names": {"es": "Perno de fibra", "en": "Fiber post", "fr": "Pivot en fibre"},
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
            "names": {"es": "Perno colado", "en": "Cast post", "fr": "Pivot coulé"},
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
            "names": {"es": "Apicoformación", "en": "Apexification", "fr": "Apexification"},
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
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("450.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "PERIO-GRAFT",
            "names": {"es": "Injerto gingival", "en": "Gingival graft", "fr": "Greffe gingivale"},
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
            "names": {"es": "Gingivectomía", "en": "Gingivectomy", "fr": "Gingivectomie"},
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
                    },
                    "default_price": Decimal("700.00"),
                },
                {
                    "labels": {
                        "es": "Pilar de cicatrización",
                        "en": "Healing abutment",
                        "fr": "Pilier de cicatrisation",
                    },
                    "default_price": Decimal("150.00"),
                },
                {
                    "labels": {
                        "es": "Colocación de corona",
                        "en": "Crown placement",
                        "fr": "Pose de couronne",
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
            "names": {"es": "Elevación de seno", "en": "Sinus lift", "fr": "Élévation sinusienne"},
            "treatment_scope": "tooth",
            "default_price": Decimal("800.00"),
            "default_duration_minutes": 90,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-BONE-GRAFT",
            "names": {"es": "Injerto óseo", "en": "Bone graft", "fr": "Greffe osseuse"},
            "treatment_scope": "tooth",
            "default_price": Decimal("450.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-APEC",
            "names": {"es": "Apicectomía", "en": "Apicoectomy", "fr": "Apicectomie"},
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
            "names": {"es": "Frenectomía", "en": "Frenectomy", "fr": "Frénectomie"},
            "treatment_scope": "tooth",
            "default_price": Decimal("180.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-BIOPSY",
            "names": {"es": "Biopsia", "en": "Biopsy", "fr": "Biopsie"},
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
            },
            "treatment_scope": "tooth",
            "default_price": Decimal("380.00"),
            "default_duration_minutes": 75,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "SURG-CYST",
            "names": {"es": "Exéresis de quiste", "en": "Cyst removal", "fr": "Exérèse de kyste"},
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
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("3500.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-LINGUAL",
            "names": {"es": "Ortodoncia lingual", "en": "Lingual braces", "fr": "Bagues linguales"},
            "treatment_scope": "global_mouth",
            "default_price": Decimal("5500.00"),
            "default_duration_minutes": 60,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-INV-LITE",
            "names": {"es": "Invisalign Lite", "en": "Invisalign Lite", "fr": "Invisalign Lite"},
            "treatment_scope": "global_mouth",
            "default_price": Decimal("2900.00"),
            "default_duration_minutes": 45,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-INV-FULL",
            "names": {"es": "Invisalign Full", "en": "Invisalign Full", "fr": "Invisalign Full"},
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
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("40.00"),
            "default_duration_minutes": 30,
            "vat_type": "exempt",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "ORTO-RET-FIX",
            "names": {"es": "Retenedor fijo", "en": "Fixed retainer", "fr": "Contention fixe"},
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
            },
            "treatment_scope": "global_mouth",
            "default_price": Decimal("550.00"),
            "default_duration_minutes": 120,
            "vat_type": "standard",
            "pricing_strategy": "flat",
        },
        {
            "internal_code": "EST-MICROAB",
            "names": {"es": "Microabrasión", "en": "Microabrasion", "fr": "Microabrasion"},
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
            "names": {"es": "Pulpotomía", "en": "Pulpotomy", "fr": "Pulpotomie"},
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
