"""InventoryService — business logic for stock item CRUD and quantity adjustments."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import InventoryItem
from .schemas import InventoryAdjust, InventoryItemCreate, InventoryItemUpdate


class InventoryService:
    @staticmethod
    async def create_item(
        db: AsyncSession, clinic_id: UUID, payload: InventoryItemCreate, created_by: UUID | None
    ) -> InventoryItem:
        item = InventoryItem(
            clinic_id=clinic_id,
            name=payload.name,
            category=payload.category,
            unit=payload.unit,
            quantity_on_hand=payload.quantity_on_hand,
            low_stock_threshold=payload.low_stock_threshold,
            notes=payload.notes,
            created_by=created_by,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def list_items(
        db: AsyncSession,
        clinic_id: UUID,
        category: str | None = None,
        search: str | None = None,
        low_stock_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[InventoryItem], int]:
        stmt = select(InventoryItem).where(InventoryItem.clinic_id == clinic_id)
        if category:
            stmt = stmt.where(InventoryItem.category == category)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(InventoryItem.name.ilike(like), InventoryItem.notes.ilike(like)))
        if low_stock_only:
            stmt = stmt.where(InventoryItem.quantity_on_hand <= InventoryItem.low_stock_threshold)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(InventoryItem.name.asc()).offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_item(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> InventoryItem:
        stmt = select(InventoryItem).where(
            InventoryItem.id == item_id, InventoryItem.clinic_id == clinic_id
        )
        item = (await db.execute(stmt)).scalar_one_or_none()
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )
        return item

    @staticmethod
    async def update_item(
        db: AsyncSession, clinic_id: UUID, item_id: UUID, payload: InventoryItemUpdate
    ) -> InventoryItem:
        item = await InventoryService.get_item(db, clinic_id, item_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def adjust_quantity(
        db: AsyncSession, clinic_id: UUID, item_id: UUID, payload: InventoryAdjust
    ) -> InventoryItem:
        item = await InventoryService.get_item(db, clinic_id, item_id)
        new_quantity = item.quantity_on_hand + payload.delta
        if new_quantity < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Adjustment would make quantity negative "
                    f"(current: {item.quantity_on_hand}, delta: {payload.delta})"
                ),
            )
        item.quantity_on_hand = new_quantity
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def delete_item(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> None:
        item = await InventoryService.get_item(db, clinic_id, item_id)
        await db.delete(item)
        await db.commit()
