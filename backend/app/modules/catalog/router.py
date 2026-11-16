"""Catalog module API router."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    CatalogItemBrief,
    CatalogItemCreate,
    CatalogItemResponse,
    CatalogItemUpdate,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    OdontogramTreatmentResponse,
    VatTypeCreate,
    VatTypeResponse,
    VatTypeUpdate,
)
from .seed import seed_clinic_defaults
from .service import (
    CatalogService,
    CategoryService,
    OdontogramCatalogService,
    SessionTemplateError,
    VatTypeService,
)

router = APIRouter()


# ============================================================================
# Category Endpoints
# ============================================================================


@router.get("/categories", response_model=ApiResponse[list[CategoryResponse]])
async def list_categories(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = Query(default=False),
) -> ApiResponse[list[CategoryResponse]]:
    """List all treatment categories."""
    categories = await CategoryService.list_categories(
        db, ctx.clinic_id, include_inactive=include_inactive
    )
    return ApiResponse(data=[CategoryResponse.model_validate(c) for c in categories])


@router.get("/categories/{category_id}", response_model=ApiResponse[CategoryResponse])
async def get_category(
    category_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CategoryResponse]:
    """Get a treatment category by ID."""
    category = await CategoryService.get_category(db, ctx.clinic_id, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return ApiResponse(data=CategoryResponse.model_validate(category))


@router.post(
    "/categories",
    response_model=ApiResponse[CategoryResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    data: CategoryCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CategoryResponse]:
    """Create a new treatment category."""
    # Check for duplicate key
    existing = await CategoryService.get_category_by_key(db, ctx.clinic_id, data.key)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with key '{data.key}' already exists",
        )

    if data.parent_id:
        await _check_parent(db, ctx.clinic_id, data.parent_id)

    category = await CategoryService.create_category(db, ctx.clinic_id, data.model_dump())
    return ApiResponse(data=CategoryResponse.model_validate(category))


async def _check_parent(
    db: AsyncSession, clinic_id: UUID, parent_id: UUID, moving: UUID | None = None
) -> None:
    """400 unless ``parent_id`` is this clinic's and isn't ``moving`` or below it."""
    seen: set[UUID] = set()
    current: UUID | None = parent_id
    while current is not None and current not in seen:
        if current == moving:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A category can't be its own parent or descendant",
            )
        seen.add(current)
        node = await CategoryService.get_category(db, clinic_id, current, include_inactive=True)
        if node is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Parent category not found"
            )
        current = node.parent_id


async def _check_vat_type(db: AsyncSession, clinic_id: UUID, vat_type_id: UUID) -> None:
    if not await VatTypeService.get_vat_type(db, clinic_id, vat_type_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="VAT type not found")


@router.put("/categories/{category_id}", response_model=ApiResponse[CategoryResponse])
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CategoryResponse]:
    """Update a treatment category (including reactivating an inactive one)."""
    category = await CategoryService.get_category(
        db, ctx.clinic_id, category_id, include_inactive=True
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify system category",
        )

    # Check key uniqueness if changing
    if data.key and data.key != category.key:
        existing = await CategoryService.get_category_by_key(db, ctx.clinic_id, data.key)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category with key '{data.key}' already exists",
            )

    if data.parent_id and data.parent_id != category.parent_id:
        await _check_parent(db, ctx.clinic_id, data.parent_id, moving=category.id)

    updated = await CategoryService.update_category(
        db, category, data.model_dump(exclude_unset=True)
    )
    return ApiResponse(data=CategoryResponse.model_validate(updated))


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete a treatment category."""
    category = await CategoryService.get_category(db, ctx.clinic_id, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system category",
        )

    await CategoryService.delete_category(db, category, soft=True)


# ============================================================================
# VAT Type Endpoints
# ============================================================================


@router.get("/vat-types", response_model=ApiResponse[list[VatTypeResponse]])
async def list_vat_types(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = Query(default=False),
) -> ApiResponse[list[VatTypeResponse]]:
    """List all VAT types for the clinic."""
    vat_types = await VatTypeService.list_vat_types(
        db, ctx.clinic_id, include_inactive=include_inactive
    )
    return ApiResponse(data=[VatTypeResponse.model_validate(v) for v in vat_types])


@router.get("/vat-types/default", response_model=ApiResponse[VatTypeResponse | None])
async def get_default_vat_type(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VatTypeResponse | None]:
    """Get the default VAT type for the clinic."""
    vat_type = await VatTypeService.get_default_vat_type(db, ctx.clinic_id)
    return ApiResponse(data=VatTypeResponse.model_validate(vat_type) if vat_type else None)


@router.get("/vat-types/{vat_type_id}", response_model=ApiResponse[VatTypeResponse])
async def get_vat_type(
    vat_type_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VatTypeResponse]:
    """Get a VAT type by ID."""
    vat_type = await VatTypeService.get_vat_type(db, ctx.clinic_id, vat_type_id)
    if not vat_type:
        raise HTTPException(status_code=404, detail="VAT type not found")
    return ApiResponse(data=VatTypeResponse.model_validate(vat_type))


@router.post(
    "/vat-types",
    response_model=ApiResponse[VatTypeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_vat_type(
    data: VatTypeCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VatTypeResponse]:
    """Create a new VAT type."""
    vat_type = await VatTypeService.create_vat_type(db, ctx.clinic_id, data.model_dump())
    return ApiResponse(data=VatTypeResponse.model_validate(vat_type))


@router.put("/vat-types/{vat_type_id}", response_model=ApiResponse[VatTypeResponse])
async def update_vat_type(
    vat_type_id: UUID,
    data: VatTypeUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[VatTypeResponse]:
    """Update a VAT type."""
    vat_type = await VatTypeService.get_vat_type(db, ctx.clinic_id, vat_type_id)
    if not vat_type:
        raise HTTPException(status_code=404, detail="VAT type not found")

    if vat_type.is_system:
        # System VAT types: rate/names stay locked, but the default flag
        # and the invoice legal note are clinic-owned (#237 precedent).
        allowed_updates = {"is_default", "legal_note"}
        update_data = {
            k: v for k, v in data.model_dump(exclude_unset=True).items() if k in allowed_updates
        }
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify system VAT type (only default status can be changed)",
            )
    else:
        update_data = data.model_dump(exclude_unset=True)

    updated = await VatTypeService.update_vat_type(db, ctx.clinic_id, vat_type, update_data)
    return ApiResponse(data=VatTypeResponse.model_validate(updated))


@router.delete("/vat-types/{vat_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vat_type(
    vat_type_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete a VAT type."""
    vat_type = await VatTypeService.get_vat_type(db, ctx.clinic_id, vat_type_id)
    if not vat_type:
        raise HTTPException(status_code=404, detail="VAT type not found")

    if vat_type.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system VAT type",
        )

    if vat_type.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default VAT type. Set another VAT type as default first.",
        )

    await VatTypeService.delete_vat_type(db, vat_type)


# ============================================================================
# Catalog Item Endpoints
# ============================================================================


@router.get("/items", response_model=PaginatedApiResponse[CatalogItemResponse])
async def list_items(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    category_id: UUID | None = Query(default=None),
    is_active: bool | None = Query(default=True),
    treatment_scope: str | None = Query(default=None),
    has_odontogram_mapping: bool | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
) -> PaginatedApiResponse[CatalogItemResponse]:
    """List catalog items with filtering and pagination."""
    items, total = await CatalogService.list_items(
        db,
        ctx.clinic_id,
        page=page,
        page_size=page_size,
        category_id=category_id,
        is_active=is_active,
        treatment_scope=treatment_scope,
        has_odontogram_mapping=has_odontogram_mapping,
        search_query=search,
    )
    return PaginatedApiResponse(
        data=[CatalogItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/items/popular", response_model=ApiResponse[list[CatalogItemBrief]])
async def get_popular_items(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=8, ge=1, le=20),
) -> ApiResponse[list[CatalogItemBrief]]:
    """Get popular catalog items by usage frequency."""
    items = await CatalogService.get_popular_items(db, ctx.clinic_id, limit)
    return ApiResponse(data=[CatalogItemBrief.model_validate(i) for i in items])


@router.get("/items/search", response_model=ApiResponse[list[CatalogItemBrief]])
async def search_items(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
) -> ApiResponse[list[CatalogItemBrief]]:
    """Search catalog items by name or code."""
    items = await CatalogService.search_items(db, ctx.clinic_id, q, limit)
    return ApiResponse(data=[CatalogItemBrief.model_validate(i) for i in items])


@router.get("/items/{item_id}", response_model=ApiResponse[CatalogItemResponse])
async def get_item(
    item_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CatalogItemResponse]:
    """Get a catalog item by ID."""
    item = await CatalogService.get_item(db, ctx.clinic_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    return ApiResponse(data=CatalogItemResponse.model_validate(item))


@router.post(
    "/items",
    response_model=ApiResponse[CatalogItemResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_item(
    data: CatalogItemCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CatalogItemResponse]:
    """Create a new catalog item."""
    # Verify category exists
    category = await CategoryService.get_category(db, ctx.clinic_id, data.category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category not found",
        )

    if data.vat_type_id:
        await _check_vat_type(db, ctx.clinic_id, data.vat_type_id)

    # Check for duplicate code
    existing = await CatalogService.get_item_by_code(db, ctx.clinic_id, data.internal_code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Item with code '{data.internal_code}' already exists",
        )

    try:
        item = await CatalogService.create_item(db, ctx.clinic_id, data.model_dump())
    except SessionTemplateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    # Reload to get relationships
    item = await CatalogService.get_item(db, ctx.clinic_id, item.id)
    return ApiResponse(data=CatalogItemResponse.model_validate(item))


# Structural fields owned by the seeder. Commercial/clinical values
# (price, cost, VAT, names, duration, sessions, is_active) stay editable (#237).
SYSTEM_ITEM_LOCKED_FIELDS = frozenset(
    {
        "internal_code",
        "category_id",
        "pricing_strategy",
        "treatment_scope",
        "is_diagnostic",
        "requires_surfaces",
    }
)


@router.put("/items/{item_id}", response_model=ApiResponse[CatalogItemResponse])
async def update_item(
    item_id: UUID,
    data: CatalogItemUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CatalogItemResponse]:
    """Update a catalog item."""
    item = await CatalogService.get_item(db, ctx.clinic_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    update_data = data.model_dump(exclude_unset=True)
    if item.is_system:
        # The modal resubmits the whole form, locked fields included with their
        # current value: only reject when a locked field actually changes.
        changed = {
            k
            for k in SYSTEM_ITEM_LOCKED_FIELDS & update_data.keys()
            if update_data[k] != getattr(item, k)
        }
        if changed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot modify system catalog item fields: {sorted(changed)}",
            )
        update_data.pop("odontogram_mapping", None)  # seeded mapping is preserved

    # Verify category if changing
    if data.category_id and data.category_id != item.category_id:
        category = await CategoryService.get_category(db, ctx.clinic_id, data.category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category not found",
            )

    if data.vat_type_id and data.vat_type_id != item.vat_type_id:
        await _check_vat_type(db, ctx.clinic_id, data.vat_type_id)

    # Check code uniqueness if changing
    if data.internal_code and data.internal_code != item.internal_code:
        existing = await CatalogService.get_item_by_code(db, ctx.clinic_id, data.internal_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Item with code '{data.internal_code}' already exists",
            )

    try:
        updated = await CatalogService.update_item(db, ctx.clinic_id, item, update_data)
    except SessionTemplateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    # Reload to get fresh relationships
    updated = await CatalogService.get_item(db, ctx.clinic_id, item_id)
    return ApiResponse(data=CatalogItemResponse.model_validate(updated))


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete a catalog item."""
    item = await CatalogService.get_item(db, ctx.clinic_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    if item.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system catalog item",
        )

    await CatalogService.delete_item(db, item, hard=False)


# ============================================================================
# Odontogram Integration Endpoints
# ============================================================================


@router.get("/odontogram-treatments", response_model=ApiResponse[list[OdontogramTreatmentResponse]])
async def get_odontogram_treatments(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[OdontogramTreatmentResponse]]:
    """Get catalog items with odontogram mappings.

    Used by the TreatmentBar component to display available treatments.
    """
    treatments = await OdontogramCatalogService.get_odontogram_treatments(db, ctx.clinic_id)
    return ApiResponse(data=[OdontogramTreatmentResponse.model_validate(t) for t in treatments])


@router.get("/odontogram-treatments/by-category")
async def get_odontogram_treatments_by_category(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict[str, list[dict]]]:
    """Get catalog items with odontogram mappings grouped by clinical category.

    Convenience endpoint for TreatmentBar to avoid client-side grouping.
    """
    grouped = await OdontogramCatalogService.get_treatments_by_category(db, ctx.clinic_id)
    return ApiResponse(data=grouped)


# ============================================================================
# Default catalog seed
# ============================================================================


@router.post("/seed", response_model=ApiResponse[dict[str, int]])
async def seed_default_catalog(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("catalog.admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict[str, int]]:
    """Load the stock VAT types, categories and treatments for this clinic.

    Idempotent — existing rows are kept, only missing ones are added. Repair
    path for installs created before ``clinic.created`` seeding existed, or
    where that seed failed. Returns how many rows were created.
    """
    summary = await seed_clinic_defaults(db, ctx.clinic_id)
    return ApiResponse(data=summary)
