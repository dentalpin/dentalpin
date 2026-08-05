"""InventoryService — business logic for stock item CRUD, movements, and cost tracking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType, event_bus

from .models import InventoryItem, InventoryMovement
from .schemas import (
    InventoryAdjust,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryMovementCreate,
)


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
            unit_cost=payload.unit_cost,
            average_cost=payload.unit_cost,
            reorder_max_quantity=payload.reorder_max_quantity,
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
    async def record_movement(
        db: AsyncSession,
        clinic_id: UUID,
        item_id: UUID,
        payload: InventoryMovementCreate,
        created_by: UUID | None,
    ) -> tuple[InventoryItem, InventoryMovement]:
        """Record a stock movement and apply it to the item's quantity (and,
        for purchases, its cost basis).

        This is the single write path for every quantity change —
        the legacy ``/adjust`` endpoint calls this with reason="adjustment".
        """
        item = await InventoryService.get_item(db, clinic_id, item_id)

        new_quantity = item.quantity_on_hand + payload.quantity_delta
        if new_quantity < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Movement would make quantity negative "
                    f"(current: {item.quantity_on_hand}, delta: {payload.quantity_delta})"
                ),
            )

        # Moving-average (AVCO) cost update — only purchases change the
        # cost basis; usage/loss/adjustment only change the quantity.
        if (
            payload.reason == "purchase"
            and payload.unit_cost is not None
            and payload.quantity_delta > 0
        ):
            prior_qty = Decimal(str(item.quantity_on_hand))
            prior_avg = Decimal(str(item.average_cost)) if item.average_cost is not None else Decimal("0")
            prior_value = prior_qty * prior_avg
            added_value = payload.quantity_delta * payload.unit_cost
            total_qty = prior_qty + payload.quantity_delta
            item.average_cost = (
                (prior_value + added_value) / total_qty if total_qty > 0 else payload.unit_cost
            )
            item.unit_cost = payload.unit_cost

        item.quantity_on_hand = new_quantity

        movement_kwargs = dict(
            clinic_id=clinic_id,
            item_id=item.id,
            reason=payload.reason,
            quantity_delta=payload.quantity_delta,
            quantity_after=new_quantity,
            unit_cost=payload.unit_cost,
            reference=payload.reference,
            notes=payload.notes,
            created_by=created_by,
        )
        if payload.movement_date is not None:
            movement_kwargs["movement_date"] = payload.movement_date
        movement = InventoryMovement(**movement_kwargs)

        db.add(movement)
        await db.commit()
        await db.refresh(item)
        await db.refresh(movement)

        await event_bus.publish(
            EventType.INVENTORY_MOVEMENT_RECORDED,
            {
                "clinic_id": str(clinic_id),
                "item_id": str(item.id),
                "item_name": item.name,
                "movement_id": str(movement.id),
                "reason": movement.reason,
                "quantity_delta": float(movement.quantity_delta),
                "quantity_after": float(movement.quantity_after),
                "unit_cost": float(movement.unit_cost) if movement.unit_cost is not None else None,
                "created_by": str(created_by) if created_by else None,
            },
        )

        return item, movement

    @staticmethod
    async def adjust_quantity(
        db: AsyncSession,
        clinic_id: UUID,
        item_id: UUID,
        payload: InventoryAdjust,
        created_by: UUID | None = None,
    ) -> InventoryItem:
        """Backward-compatible quick adjust — recorded as an 'adjustment' movement."""
        movement_payload = InventoryMovementCreate(
            reason="adjustment",
            quantity_delta=payload.delta,
            notes=payload.note,
        )
        item, _ = await InventoryService.record_movement(
            db, clinic_id, item_id, movement_payload, created_by
        )
        return item

    @staticmethod
    async def list_movements(
        db: AsyncSession,
        clinic_id: UUID,
        item_id: UUID,
        reason: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[InventoryMovement], int]:
        # Confirms the item exists and belongs to this clinic (404s otherwise).
        await InventoryService.get_item(db, clinic_id, item_id)

        stmt = select(InventoryMovement).where(
            InventoryMovement.clinic_id == clinic_id, InventoryMovement.item_id == item_id
        )
        if reason:
            stmt = stmt.where(InventoryMovement.reason == reason)
        if date_from:
            stmt = stmt.where(InventoryMovement.movement_date >= date_from)
        if date_to:
            stmt = stmt.where(InventoryMovement.movement_date <= date_to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(InventoryMovement.movement_date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total

    @staticmethod
    async def export_movements(
        db: AsyncSession,
        clinic_id: UUID,
        item_id: UUID,
        reason: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        max_rows: int = 5000,
    ) -> list[InventoryMovement]:
        """Unpaginated fetch for CSV export, capped at max_rows."""
        await InventoryService.get_item(db, clinic_id, item_id)

        stmt = select(InventoryMovement).where(
            InventoryMovement.clinic_id == clinic_id, InventoryMovement.item_id == item_id
        )
        if reason:
            stmt = stmt.where(InventoryMovement.reason == reason)
        if date_from:
            stmt = stmt.where(InventoryMovement.movement_date >= date_from)
        if date_to:
            stmt = stmt.where(InventoryMovement.movement_date <= date_to)

        stmt = stmt.order_by(InventoryMovement.movement_date.desc()).limit(max_rows)
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)

    @staticmethod
    async def usage_summary(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> dict:
        await InventoryService.get_item(db, clinic_id, item_id)

        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)

        async def sum_used(since: datetime | None) -> Decimal:
            stmt = select(func.coalesce(func.sum(-InventoryMovement.quantity_delta), 0)).where(
                InventoryMovement.clinic_id == clinic_id,
                InventoryMovement.item_id == item_id,
                InventoryMovement.reason == "used",
                InventoryMovement.quantity_delta < 0,
            )
            if since is not None:
                stmt = stmt.where(InventoryMovement.movement_date >= since)
            return (await db.execute(stmt)).scalar_one()

        return {
            "item_id": item_id,
            "used_this_week": await sum_used(week_start),
            "used_this_month": await sum_used(month_start),
            "total_used": await sum_used(None),
        }

    @staticmethod
    async def delete_item(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> None:
        item = await InventoryService.get_item(db, clinic_id, item_id)
        await db.delete(item)
        await db.commit()
