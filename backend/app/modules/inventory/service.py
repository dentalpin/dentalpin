"""Inventory module service layer.

Business logic for categories and items.  Every query filters by
``clinic_id`` (multi-tenancy — mandatory).

Atomic stock adjustment (issue #153): concurrent quantity changes use
an atomic ``UPDATE … SET quantity = quantity + :delta
WHERE quantity + :delta >= 0`` so the race condition is guarded at the
DB level, not in application code.  The caller gets ``None`` (rejected)
when the adjustment would go negative.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import InventoryCategory, InventoryItem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class ItemFilters:
    status: str | None = None
    category_id: UUID | None = None
    low_stock: bool = False
    search: str | None = None


# ---------------------------------------------------------------------------
# InventoryCategoryService
# ---------------------------------------------------------------------------


class InventoryCategoryService:
    """CRUD for ``inventory_categories``."""

    @staticmethod
    async def list(
        db: AsyncSession,
        clinic_id: UUID,
        *,
        include_inactive: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[InventoryCategory], int]:
        conditions = [InventoryCategory.clinic_id == clinic_id]
        if not include_inactive:
            conditions.append(InventoryCategory.is_active.is_(True))

        count_stmt = (
            select(func.count(InventoryCategory.id))
            .select_from(InventoryCategory)
            .where(*conditions)
        )
        total = int((await db.execute(count_stmt)).scalar_one() or 0)

        stmt = (
            select(InventoryCategory)
            .where(*conditions)
            .order_by(InventoryCategory.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def get(db: AsyncSession, clinic_id: UUID, category_id: UUID) -> InventoryCategory | None:
        stmt = select(InventoryCategory).where(
            InventoryCategory.id == category_id,
            InventoryCategory.clinic_id == clinic_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, clinic_id: UUID, data: dict[str, Any]) -> InventoryCategory:
        category = InventoryCategory(clinic_id=clinic_id, **data)
        db.add(category)
        await db.flush()
        return category

    @staticmethod
    async def update(
        db: AsyncSession, clinic_id: UUID, category_id: UUID, data: dict[str, Any]
    ) -> InventoryCategory | None:
        category = await InventoryCategoryService.get(db, clinic_id, category_id)
        if not category:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(category, key, value)
        await db.flush()
        return category


# ---------------------------------------------------------------------------
# InventoryItemService
# ---------------------------------------------------------------------------


class InventoryItemService:
    """CRUD + low-stock queries for ``inventory_items``."""

    @staticmethod
    async def list(
        db: AsyncSession,
        clinic_id: UUID,
        filters: ItemFilters | None = None,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[InventoryItem], int]:
        filters = filters or ItemFilters()
        conditions = [InventoryItem.clinic_id == clinic_id]

        if filters.status:
            conditions.append(InventoryItem.status == filters.status)
        else:
            # Default: exclude soft-deleted
            conditions.append(InventoryItem.status != "deleted")

        if filters.category_id:
            conditions.append(InventoryItem.category_id == filters.category_id)

        if filters.low_stock:
            conditions.append(
                and_(
                    InventoryItem.min_quantity > 0,
                    InventoryItem.quantity <= InventoryItem.min_quantity,
                    InventoryItem.status == "active",
                )
            )

        if filters.search:
            pattern = f"%{filters.search}%"
            conditions.append(
                or_(
                    InventoryItem.code.ilike(pattern),
                    InventoryItem.name.ilike(pattern),
                    InventoryItem.supplier.ilike(pattern),
                )
            )

        count_stmt = (
            select(func.count(InventoryItem.id)).select_from(InventoryItem).where(*conditions)
        )
        total = int((await db.execute(count_stmt)).scalar_one() or 0)

        stmt = (
            select(InventoryItem)
            .where(*conditions)
            .order_by(InventoryItem.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    @staticmethod
    async def get(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> InventoryItem | None:
        stmt = select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.clinic_id == clinic_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db: AsyncSession, clinic_id: UUID, code: str) -> InventoryItem | None:
        stmt = select(InventoryItem).where(
            InventoryItem.clinic_id == clinic_id,
            InventoryItem.code == code,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, clinic_id: UUID, data: dict[str, Any]) -> InventoryItem:
        is_low = (
            data.get("quantity", 0) <= data.get("min_quantity", 0)
            and data.get("min_quantity", 0) > 0
        )
        item = InventoryItem(clinic_id=clinic_id, is_low_stock=is_low, **data)
        db.add(item)
        await db.flush()
        return item

    @staticmethod
    async def update(
        db: AsyncSession, clinic_id: UUID, item_id: UUID, data: dict[str, Any]
    ) -> InventoryItem | None:
        item = await InventoryItemService.get(db, clinic_id, item_id)
        if not item:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(item, key, value)
        # Recompute low-stock flag
        item.is_low_stock = item.min_quantity > 0 and item.quantity <= item.min_quantity
        await db.flush()
        return item

    @staticmethod
    async def delete(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> InventoryItem | None:
        """Soft-delete an item."""
        return await InventoryItemService.update(db, clinic_id, item_id, {"status": "deleted"})

    @staticmethod
    async def adjust_stock(
        db: AsyncSession,
        clinic_id: UUID,
        item_id: UUID,
        delta: int,
    ) -> InventoryItem | None:
        """Atomic stock adjustment — guards against negative quantities
        at the DB level (issue #153).

        Uses ``UPDATE … SET quantity = quantity + :delta
        WHERE quantity + :delta >= 0`` so concurrent requests serialize
        at the DB level, not in application code.

        Returns the updated item on success, ``None`` if the adjustment
        would go negative (no row updated).
        """
        if delta == 0:
            return await InventoryItemService.get(db, clinic_id, item_id)

        # Atomic UPDATE with check constraint — no race condition possible.
        stmt = text(
            "UPDATE inventory_items "
            "SET quantity = quantity + :delta, updated_at = now() "
            "WHERE id = :item_id AND clinic_id = :clinic_id "
            "AND quantity + :delta >= 0 "
            "RETURNING id"
        ).bindparams(delta=delta, item_id=item_id, clinic_id=clinic_id)
        result = await db.execute(stmt)
        row = result.first()
        if row is None:
            # Adjustment rejected (negative) or item not found.
            return None

        await db.flush()
        # Re-fetch to get updated is_low_stock and all columns.
        return await InventoryItemService.get(db, clinic_id, item_id)

    @staticmethod
    async def low_stock_items(
        db: AsyncSession, clinic_id: UUID, limit: int = 50
    ) -> list[InventoryItem]:
        """Return items where quantity <= min_quantity and min_quantity > 0."""
        stmt = (
            select(InventoryItem)
            .where(
                InventoryItem.clinic_id == clinic_id,
                InventoryItem.status == "active",
                InventoryItem.min_quantity > 0,
                InventoryItem.quantity <= InventoryItem.min_quantity,
            )
            .order_by(InventoryItem.quantity)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def stock_summary(db: AsyncSession, clinic_id: UUID) -> dict[str, Any]:
        """Aggregate stock stats for the clinic dashboard."""
        base = select(func.count(InventoryItem.id)).where(
            InventoryItem.clinic_id == clinic_id,
            InventoryItem.status == "active",
        )

        total_items = int((await db.execute(base)).scalar_one() or 0)

        low_stock_count_stmt = (
            select(func.count(InventoryItem.id))
            .select_from(InventoryItem)
            .where(
                InventoryItem.clinic_id == clinic_id,
                InventoryItem.status == "active",
                InventoryItem.min_quantity > 0,
                InventoryItem.quantity <= InventoryItem.min_quantity,
            )
        )
        low_stock_count = int((await db.execute(low_stock_count_stmt)).scalar_one() or 0)

        out_of_stock_stmt = (
            select(func.count(InventoryItem.id))
            .select_from(InventoryItem)
            .where(
                InventoryItem.clinic_id == clinic_id,
                InventoryItem.status == "active",
                InventoryItem.quantity == 0,
            )
        )
        out_of_stock_count = int((await db.execute(out_of_stock_stmt)).scalar_one() or 0)

        total_quantity_stmt = (
            select(func.coalesce(func.sum(InventoryItem.quantity), 0))
            .select_from(InventoryItem)
            .where(
                InventoryItem.clinic_id == clinic_id,
                InventoryItem.status == "active",
            )
        )
        total_quantity = int((await db.execute(total_quantity_stmt)).scalar_one() or 0)

        return {
            "total_items": total_items,
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
            "total_quantity": total_quantity,
        }
