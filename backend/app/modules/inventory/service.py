"""InventoryService — stock CRUD, atomic adjustments and the movement ledger.

Every quantity change goes through :meth:`_apply_movement`: a
``SELECT … FOR UPDATE`` row lock (concurrent adjustments serialise at
the row level — the DB arbitrates, never app code) followed by a Python
arithmetic floor check and an append-only ``stock_movements`` row in the
same transaction.  That ledger is the audit trail (#226); the row lock
is the concurrency fix for PR #153's race (roadmap #220).
"""

from __future__ import annotations

import logging
from datetime import datetime as dt
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import User
from app.core.events import event_bus
from app.core.events.types import EventType

from .models import InventoryItem, StockMovement
from .schemas import InventoryItemCreate, InventoryItemUpdate

logger = logging.getLogger(__name__)


class InventoryService:
    @staticmethod
    async def create_item(
        db: AsyncSession,
        clinic_id: UUID,
        payload: InventoryItemCreate,
        created_by: UUID | None,
    ) -> InventoryItem:
        item = InventoryItem(
            clinic_id=clinic_id,
            name=payload.name,
            category=payload.category,
            unit=payload.unit,
            stock_quantity=payload.stock_quantity,
            min_quantity=payload.min_quantity,
            unit_cost=payload.unit_cost,
            notes=payload.notes,
            created_by=created_by,
        )
        db.add(item)
        await db.flush()
        # Opening stock is itself a ledger row — the trail starts at day one.
        if payload.stock_quantity > 0:
            db.add(
                StockMovement(
                    clinic_id=clinic_id,
                    inventory_item_id=item.id,
                    delta=payload.stock_quantity,
                    reason="initial",
                    created_by=created_by,
                )
            )
        # A brand-new item already at/below its threshold is a low-stock
        # alert on day one.
        await InventoryService._publish_low_if_crossed(db, item, was_low=False)
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def list_items(
        db: AsyncSession,
        clinic_id: UUID,
        category: str | None = None,
        low_stock_only: bool = False,
        include_inactive: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[InventoryItem], int]:
        stmt = select(InventoryItem).where(InventoryItem.clinic_id == clinic_id)
        if not include_inactive:
            stmt = stmt.where(InventoryItem.is_active)
        if category:
            stmt = stmt.where(InventoryItem.category == category)
        if low_stock_only:
            # SQL-level filter — stays correct under concurrency.
            stmt = stmt.where(InventoryItem.stock_quantity <= InventoryItem.min_quantity)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(InventoryItem.name.asc()).offset((page - 1) * page_size).limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_item(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> InventoryItem:
        stmt = select(InventoryItem).where(
            InventoryItem.id == item_id, InventoryItem.clinic_id == clinic_id
        )
        item = (await db.execute(stmt)).scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        return item

    @staticmethod
    async def update_item(
        db: AsyncSession,
        clinic_id: UUID,
        item_id: UUID,
        payload: InventoryItemUpdate,
        created_by: UUID | None = None,
    ) -> InventoryItem:
        """Update item fields, with ``FOR UPDATE`` row lock on stock changes.

        An absolute ``stock_quantity`` set through PATCH is a correction —
        it lands in the ledger too, so the trail has no gaps.  The row is
        locked with ``SELECT … FOR UPDATE`` so concurrent adjustments
        serialise correctly (#153).
        """
        stmt = (
            select(InventoryItem)
            .where(InventoryItem.id == item_id, InventoryItem.clinic_id == clinic_id)
            .with_for_update()
        )
        item = (await db.execute(stmt)).scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        was_low = item.is_low_stock
        data = payload.model_dump(exclude_unset=True)

        # An absolute stock_quantity set through PATCH is a correction —
        # it lands in the ledger too, so the trail has no gaps.
        new_qty = data.pop("stock_quantity", None)
        if new_qty is not None and new_qty != item.stock_quantity:
            db.add(
                StockMovement(
                    clinic_id=clinic_id,
                    inventory_item_id=item.id,
                    delta=new_qty - item.stock_quantity,
                    reason="correction",
                    created_by=created_by,
                )
            )
            item.stock_quantity = new_qty

        for field, value in data.items():
            setattr(item, field, value)
        await db.flush()
        if new_qty is not None:
            await InventoryService._publish_low_if_crossed(db, item, was_low=was_low)
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def delete_item(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> None:
        item = await InventoryService.get_item(db, clinic_id, item_id)
        has_history = (
            await db.execute(
                select(func.count())
                .select_from(StockMovement)
                .where(StockMovement.inventory_item_id == item.id)
            )
        ).scalar_one()
        if has_history:
            # The ledger IS the audit trail — items with history are
            # deactivated (PATCH is_active=false), never erased.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="item_has_history",
            )
        await db.delete(item)
        await db.commit()

    @staticmethod
    async def adjust_stock(
        db: AsyncSession,
        clinic_id: UUID,
        item_id: UUID,
        delta: Decimal,
        reason: str = "adjustment",
        note: str | None = None,
        created_by: UUID | None = None,
    ) -> InventoryItem:
        """Atomically apply a relative stock change (+/- ``delta``).

        The row is locked with ``SELECT … FOR UPDATE`` so concurrent
        adjustments serialise here instead of racing read-modify-write
        (#153).  Returns 409 when the guard rejects the delta.  The
        applied change lands in the movements ledger within the same
        transaction.
        """
        # get_item gives us the 404 plus the pre-adjust low state, so the
        # alert only fires on the not-low -> low crossing.
        pre = await InventoryService.get_item(db, clinic_id, item_id)
        was_low = pre.is_low_stock

        updated, _applied = await InventoryService._apply_movement(
            db,
            clinic_id=clinic_id,
            item_id=item_id,
            delta=delta,
            reason=reason,
            note=note,
            created_by=created_by,
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="adjustment would drive stock below zero",
            )

        # Low-stock crossing is evaluated on the freshly returned row.
        await InventoryService._publish_low_if_crossed(db, updated, was_low=was_low)
        await db.commit()
        await db.refresh(updated)
        return updated

    @staticmethod
    async def _apply_movement(
        db: AsyncSession,
        *,
        clinic_id: UUID,
        item_id: UUID,
        delta: Decimal,
        reason: str,
        note: str | None = None,
        created_by: UUID | None = None,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
        clamp_at_zero: bool = False,
    ) -> tuple[InventoryItem, Decimal] | tuple[None, None]:
        """Atomic ``SELECT … FOR UPDATE`` row lock + quantity change + ledger row.

        When ``clamp_at_zero`` is set (auto-deduction), an underflowing
        deduction floors at zero instead of being rejected — clinical care
        must not be blocked by bookkeeping — and the movement records the
        actually-applied delta.  Returns the updated row, or None when an
        unclamped guard rejected the delta (caller decides: 409 for manual
        adjustments).

        For ``reason='consumption'`` rows with a business reference
        (``reference_type`` + ``reference_id``), a partial unique index
        ensures idempotency: duplicate deductions for the same treatment
        are silently ignored (``ON CONFLICT DO NOTHING``).
        """
        # Row-level lock: concurrent adjustments serialise here instead of
        # racing read-modify-write (#153).  Released at commit/rollback.
        locked = (
            await db.execute(
                select(InventoryItem)
                .where(
                    InventoryItem.id == item_id,
                    InventoryItem.clinic_id == clinic_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if locked is None:
            return None, None

        new_quantity = locked.stock_quantity + delta
        if new_quantity < 0:
            if not clamp_at_zero:
                return None, None
            new_quantity = Decimal("0")

        applied = new_quantity - locked.stock_quantity
        locked.stock_quantity = new_quantity

        movement = StockMovement(
            clinic_id=clinic_id,
            inventory_item_id=item_id,
            delta=applied,
            reason=reason,
            note=note,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by=created_by,
        )
        db.add(movement)

        if reason == "consumption" and reference_type and reference_id:
            # Idempotency guard: the partial unique index catches
            # duplicate consumption movements for the same treatment.
            # A savepoint isolates the flush so a duplicate doesn't roll
            # back the caller's entire transaction (ADR 0019 — at-least-
            # once bus contract, same as payments).
            savepoint = await db.begin_nested()
            try:
                await db.flush()
                await savepoint.commit()
            except IntegrityError:
                await savepoint.rollback()
                # Remove the pending movement from the session so it
                # doesn't participate in the next flush.
                db.expunge(movement)
                return locked, Decimal("0")

        return locked, applied

    @staticmethod
    async def list_movements(
        db: AsyncSession,
        clinic_id: UUID,
        inventory_item_id: UUID | None = None,
        reason: str | None = None,
        date_from: dt | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """List stock movements with resolved actor names.

        Returns dicts (not ORM objects) so each row carries a
        ``created_by_name`` resolved from the ``users`` table.
        """
        stmt = (
            select(StockMovement, User.first_name, User.last_name)
            .outerjoin(User, StockMovement.created_by == User.id)
            .where(StockMovement.clinic_id == clinic_id)
        )
        if inventory_item_id:
            stmt = stmt.where(StockMovement.inventory_item_id == inventory_item_id)
        if reason:
            stmt = stmt.where(StockMovement.reason == reason)

        count_stmt = select(func.count()).select_from(
            select(StockMovement)
            .where(StockMovement.clinic_id == clinic_id)
            .correlate_except(StockMovement)
            .subquery()
        )
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).all()

        results = []
        for movement, first_name, last_name in rows:
            result = {
                "movement": movement,
                "created_by_name": (
                    f"{first_name} {last_name}" if first_name and last_name else None
                ),
            }
            results.append(result)

        return results, total

    @staticmethod
    async def stock_valuation(db: AsyncSession, clinic_id: UUID) -> dict:
        """Total on-hand value over items with a known unit cost."""
        rows = (
            await db.execute(
                select(
                    InventoryItem.unit_cost,
                    InventoryItem.stock_quantity,
                ).where(
                    InventoryItem.clinic_id == clinic_id,
                    InventoryItem.is_active,
                )
            )
        ).all()
        total = Decimal("0")
        valued = unvalued = 0
        for unit_cost, qty in rows:
            if unit_cost is None:
                unvalued += 1
                continue
            valued += 1
            total += Decimal(unit_cost) * Decimal(qty)
        return {
            "total_value": total,
            "valued_items": valued,
            "unvalued_items": unvalued,
        }

    @staticmethod
    async def apply_consumption(
        db: AsyncSession,
        *,
        clinic_id: UUID,
        links: list[tuple[UUID, Decimal]],
        treatment_reference_id: UUID | None,
        actor_id: UUID | None,
    ) -> list[dict]:
        """Deduct pre-resolved consumable links from stock (#226).

        Each entry in *links* is an ``(inventory_item_id, quantity)``
        pair resolved by the caller (``treatment_consumables`` owns the
        links table).  Each quantity is deducted via :meth:`_apply_movement`
        (``clamp_at_zero=True``): clinical care is never blocked by
        bookkeeping — an underflowing deduction floors at zero and the
        movement records what was actually applied.

        Duplicate deductions for the same treatment are silently ignored
        via the partial unique index on stock_movements (idempotency —
        at-least-once bus contract per ADR 0019).

        This is a clean public primitive with **no knowledge** of
        ``treatment_consumables`` — the caller reads its own table.
        """
        applied: list[dict] = []
        for item_id, quantity in links:
            updated, applied_delta = await InventoryService._apply_movement(
                db,
                clinic_id=clinic_id,
                item_id=item_id,
                delta=-quantity,
                reason="consumption",
                created_by=actor_id,
                reference_type="treatment_performance",
                reference_id=treatment_reference_id,
                clamp_at_zero=True,
            )
            if updated is not None and applied_delta is not None:
                # Low-stock crossing check for auto-deductions too.
                pre_low = (updated.stock_quantity - applied_delta) <= updated.min_quantity
                await InventoryService._publish_low_if_crossed(db, updated, was_low=pre_low)
                applied.append(
                    {
                        "inventory_item_id": str(updated.id),
                        "name": updated.name,
                        "requested": float(quantity),
                        "applied": float(applied_delta),
                    }
                )

        return applied

    @staticmethod
    async def _publish_low_if_crossed(
        db: AsyncSession, item: InventoryItem, *, was_low: bool
    ) -> None:
        """Fire ``inventory.low_stock`` once, on the not-low → low crossing."""
        if not was_low and item.is_low_stock:
            await event_bus.publish(
                EventType.INVENTORY_STOCK_LOW,
                {
                    "clinic_id": str(item.clinic_id),
                    "item_id": str(item.id),
                    "name": item.name,
                    "category": item.category,
                    "stock_quantity": float(item.stock_quantity),
                    "min_quantity": float(item.min_quantity),
                },
                db=db,
            )
