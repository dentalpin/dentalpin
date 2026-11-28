"""Catalog module Pydantic schemas for API request/response."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator


def _blank_is_none(value: object) -> object:
    """A cleared input sends "" (Nuxt UI keeps "" even for ``type="number"``).

    For an optional price or duration that means "no value", not a malformed
    number -- without this, clearing the field and saving answers 422.
    """
    if isinstance(value, str) and not value.strip():
        return None
    return value


# Tier prices for ``pricing_strategy == "per_surface"``, keyed "1".."5". The
# column is plain JSONB, which ``json.dumps`` cannot fill with a Decimal, so
# ``model_dump()`` emits each price as a string -- the format the seeder
# stores and ``pricing._resolve_surface_tier_price`` reads (#1240).
# Prices fit the NUMERIC(10, 2) columns they end up in (price_snapshot).
SurfacePrice = Annotated[
    Decimal,
    Field(ge=0, max_digits=10, decimal_places=2),
    PlainSerializer(str, return_type=str),
]

SURFACE_TIERS = frozenset({"1", "2", "3", "4", "5"})


def _check_surface_tiers(value: dict | None) -> dict | None:
    """Keys must be exactly the tiers "1".."5" (what the modal and seeder send).

    ``pricing._resolve_surface_tier_price`` sorts ``int(k)`` and reads back
    ``surface_prices[str(tier)]``, so a key such as "02" was a KeyError (500)
    when a treatment was priced.
    """
    if value is not None:
        bad = sorted(k for k in value if k not in SURFACE_TIERS)
        if bad:
            raise ValueError(f"surface tiers must be '1'..'5', got {bad}")
    return value


# ============================================================================
# VAT Type Schemas
# ============================================================================


class VatTypeCreate(BaseModel):
    """Schema for creating a VAT type."""

    names: dict[str, str] = Field(default_factory=dict)  # {"es": "Nombre", "en": "Name"}
    rate: float = Field(default=0.0, ge=0, le=100)
    legal_note: str | None = Field(default=None, max_length=300)
    is_default: bool = False


class VatTypeUpdate(BaseModel):
    """Schema for updating a VAT type."""

    names: dict[str, str] | None = None
    rate: float | None = Field(default=None, ge=0, le=100)
    legal_note: str | None = Field(default=None, max_length=300)
    is_default: bool | None = None
    is_active: bool | None = None


class VatTypeResponse(BaseModel):
    """Schema for VAT type response."""

    id: UUID
    clinic_id: UUID
    names: dict[str, str]
    rate: float
    legal_note: str | None = None
    is_default: bool
    is_active: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VatTypeBrief(BaseModel):
    """Brief VAT type info for lists and selects."""

    id: UUID
    names: dict[str, str]
    rate: float
    is_default: bool
    is_active: bool
    is_system: bool

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Category Schemas
# ============================================================================


class CategoryCreate(BaseModel):
    """Schema for creating a treatment category."""

    key: str = Field(min_length=1, max_length=50)
    names: dict[str, str] = Field(default_factory=dict)  # {"es": "Nombre", "en": "Name"}
    descriptions: dict[str, str] | None = None
    parent_id: UUID | None = None
    display_order: int = 0
    icon: str | None = Field(default=None, max_length=50)


class CategoryUpdate(BaseModel):
    """Schema for updating a treatment category."""

    key: str | None = Field(default=None, min_length=1, max_length=50)
    names: dict[str, str] | None = None
    descriptions: dict[str, str] | None = None
    parent_id: UUID | None = None
    display_order: int | None = None
    icon: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    """Schema for treatment category response."""

    id: UUID
    clinic_id: UUID
    parent_id: UUID | None
    key: str
    names: dict[str, str]
    descriptions: dict[str, str] | None
    display_order: int
    icon: str | None
    is_active: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryTreeResponse(CategoryResponse):
    """Schema for category with nested children (tree structure)."""

    children: list["CategoryTreeResponse"] = []

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Odontogram Mapping Schemas
# ============================================================================


class OdontogramMappingCreate(BaseModel):
    """Schema for creating odontogram mapping (usually part of item creation)."""

    odontogram_treatment_type: str = Field(max_length=30)
    visualization_rules: list[dict] = Field(default_factory=list)
    visualization_config: dict = Field(default_factory=dict)
    clinical_category: str = Field(max_length=20)


class OdontogramMappingResponse(BaseModel):
    """Schema for odontogram mapping response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    odontogram_treatment_type: str
    visualization_rules: list[dict]
    visualization_config: dict
    clinical_category: str


# ============================================================================
# Session Template Schemas
# ============================================================================


class CatalogItemSessionInput(BaseModel):
    """Input shape for a session in the catalog template.

    Used inside CatalogItemCreate/Update.sessions[]. Sequence is assigned
    in array order at the server; client may omit or send a hint.
    """

    sequence: int | None = Field(default=None, ge=1)
    labels: dict[str, str] = Field(default_factory=dict)
    default_price: Decimal = Field(ge=0)


class CatalogItemSessionResponse(BaseModel):
    id: UUID
    sequence: int
    labels: dict[str, str]
    default_price: Decimal

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Catalog Item Schemas
# ============================================================================


class CatalogItemCreate(BaseModel):
    """Schema for creating a catalog item."""

    internal_code: str = Field(min_length=1, max_length=50)
    category_id: UUID
    names: dict[str, str] = Field(default_factory=dict)
    descriptions: dict[str, str] | None = None

    # Pricing
    default_price: Decimal | None = Field(default=None, ge=0)
    cost_price: Decimal | None = Field(default=None, ge=0)

    # Scheduling
    default_duration_minutes: int | None = Field(default=None, ge=0, le=480)  # Max 8 hours
    requires_appointment: bool = True

    # Tax - references VatType by ID (optional, uses clinic default if not provided)
    vat_type_id: UUID | None = None

    # Pricing strategy (how to compute Treatment.price_snapshot).
    pricing_strategy: Literal["flat", "per_tooth", "per_surface", "per_role"] = "flat"
    pricing_config: dict | None = None
    # Tiered prices by surface count. Keys "1".."5" map to prices. Used when
    # pricing_strategy == "per_surface". See pricing.py for tier resolution.
    surface_prices: dict[str, SurfacePrice] | None = None

    # Treatment characteristics (aligns with Treatment.scope).
    treatment_scope: Literal["tooth", "multi_tooth", "global_mouth", "global_arch"] = "tooth"
    is_diagnostic: bool = False
    requires_surfaces: bool = False

    # Material
    material_notes: str | None = None

    # Odontogram mapping (optional)
    odontogram_mapping: OdontogramMappingCreate | None = None

    # Session template (optional). Empty list and None both mean single-session.
    sessions: list[CatalogItemSessionInput] | None = None

    _clear_blank = field_validator(
        "default_price", "cost_price", "default_duration_minutes", mode="before"
    )(_blank_is_none)
    _surface_tiers = field_validator("surface_prices")(_check_surface_tiers)


class CatalogItemUpdate(BaseModel):
    """Schema for updating a catalog item."""

    internal_code: str | None = Field(default=None, min_length=1, max_length=50)
    category_id: UUID | None = None
    names: dict[str, str] | None = None
    descriptions: dict[str, str] | None = None

    # Pricing
    default_price: Decimal | None = Field(default=None, ge=0)
    cost_price: Decimal | None = Field(default=None, ge=0)

    # Scheduling
    default_duration_minutes: int | None = Field(default=None, ge=0, le=480)
    requires_appointment: bool | None = None

    # Tax - references VatType by ID
    vat_type_id: UUID | None = None

    # Pricing strategy
    pricing_strategy: Literal["flat", "per_tooth", "per_surface", "per_role"] | None = None
    pricing_config: dict | None = None
    surface_prices: dict[str, SurfacePrice] | None = None

    # Treatment characteristics
    treatment_scope: Literal["tooth", "multi_tooth", "global_mouth", "global_arch"] | None = None
    is_diagnostic: bool | None = None
    requires_surfaces: bool | None = None

    # Material
    material_notes: str | None = None

    # Status
    is_active: bool | None = None

    # Odontogram mapping
    odontogram_mapping: OdontogramMappingCreate | None = None

    # Session template. When provided (even as empty list) the server
    # atomically replaces the stored template.
    sessions: list[CatalogItemSessionInput] | None = None

    _clear_blank = field_validator(
        "default_price", "cost_price", "default_duration_minutes", mode="before"
    )(_blank_is_none)
    _surface_tiers = field_validator("surface_prices")(_check_surface_tiers)


class CatalogItemResponse(BaseModel):
    """Schema for catalog item response."""

    id: UUID
    clinic_id: UUID
    category_id: UUID
    internal_code: str
    names: dict[str, str]
    descriptions: dict[str, str] | None

    # Pricing
    default_price: Decimal | None
    cost_price: Decimal | None

    # Scheduling
    default_duration_minutes: int | None
    requires_appointment: bool

    # Tax - references VatType
    vat_type_id: UUID | None
    vat_type: VatTypeBrief | None = Field(
        default=None, validation_alias="vat_type_rel"
    )  # Eager loaded

    # Pricing strategy
    pricing_strategy: str
    pricing_config: dict | None
    surface_prices: dict[str, Decimal] | None = None

    # Treatment characteristics
    treatment_scope: str
    is_diagnostic: bool
    requires_surfaces: bool

    # Material
    material_notes: str | None

    # Status
    is_active: bool
    is_system: bool
    deleted_at: datetime | None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Related
    category: CategoryResponse | None = None
    odontogram_mapping: OdontogramMappingResponse | None = None
    sessions: list[CatalogItemSessionResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CatalogItemBrief(BaseModel):
    """Brief catalog item info for lists."""

    id: UUID
    internal_code: str
    names: dict[str, str]
    default_price: Decimal | None
    default_duration_minutes: int | None
    # The invoice line picker starts from the treatment's own VAT (#1028).
    vat_type_id: UUID | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Odontogram Integration Schemas
# ============================================================================


class OdontogramTreatmentResponse(BaseModel):
    """Schema for treatments with odontogram integration.

    Used by the odontogram component to display treatments with proper visualization
    plus pricing hints so the frontend can preview costs before confirming.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    internal_code: str
    names: dict[str, str]
    default_price: Decimal | None
    treatment_scope: str
    requires_surfaces: bool
    is_diagnostic: bool

    # Pricing strategy (for multi-tooth price preview).
    pricing_strategy: str
    pricing_config: dict | None = None
    surface_prices: dict[str, Decimal] | None = None

    # Odontogram specific. None/empty when the item has no odontogram mapping
    # (global-scope items are returned unmapped so the plan UI can offer them).
    odontogram_treatment_type: str | None = None
    visualization_rules: list[dict] = []
    visualization_config: dict = {}
    clinical_category: str | None = None

    # Category info
    category_key: str
    category_names: dict[str, str]


class OdontogramTreatmentsByCategory(BaseModel):
    """Grouped treatments for TreatmentBar display."""

    category_key: str
    category_names: dict[str, str]
    treatments: list[OdontogramTreatmentResponse]


# ============================================================================
# Search/Filter Schemas
# ============================================================================


class CatalogSearchParams(BaseModel):
    """Search parameters for catalog items."""

    query: str | None = None  # Search in names, codes
    category_id: UUID | None = None
    is_active: bool | None = True
    treatment_scope: Literal["tooth", "multi_tooth", "global_mouth", "global_arch"] | None = None
    has_odontogram_mapping: bool | None = None
