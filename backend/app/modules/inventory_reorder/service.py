"""Reorder suggestion computation and draft PO generation.

Pure computation over the movement ledger, supplier sourcing and open
purchase orders — no tables of its own (see __init__.py). Every query is
clinic-scoped.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contacts.models import Contact
from app.modules.inventory.models import InventoryItem, StockMovement
from app.modules.purchase_orders.models import PurchaseOrder, PurchaseOrderLine
from app.modules.purchase_orders.schemas import PurchaseOrderCreate, PurchaseOrderLineCreate
from app.modules.purchase_orders.service import PurchaseOrderService
from app.modules.supplier_items.models import SupplierItem
from app.modules.suppliers.models import Supplier

LOOKBACK_DAYS = 90
OPEN_PO_STATUSES = ("draft", "sent", "confirmed")


class ReorderService:
    """Reorder policy layer. Static methods, no state."""

    @staticmethod
    async def _usage_90d(db: AsyncSession, clinic_id: UUID) -> dict[UUID, Decimal]:
        """Sum of negative deltas (consumption) in the last 90 days, per item."""
        cutoff = datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)
        rows = (
            await db.execute(
                select(
                    StockMovement.inventory_item_id,
                    func.sum(-StockMovement.delta),
                )
                .where(
                    StockMovement.clinic_id == clinic_id,
                    StockMovement.delta < 0,
                    StockMovement.created_at >= cutoff,
                )
                .group_by(StockMovement.inventory_item_id)
            )
        ).all()
        return {item_id: usage for item_id, usage in rows}

    @staticmethod
    async def _on_order(db: AsyncSession, clinic_id: UUID) -> dict[UUID, Decimal]:
        """Quantity still outstanding on open POs, per item."""
        rows = (
            await db.execute(
                select(
                    PurchaseOrderLine.inventory_item_id,
                    func.sum(
                        PurchaseOrderLine.quantity_ordered - PurchaseOrderLine.quantity_received
                    ),
                )
                .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
                .where(
                    PurchaseOrder.clinic_id == clinic_id,
                    PurchaseOrder.status.in_(OPEN_PO_STATUSES),
                )
                .group_by(PurchaseOrderLine.inventory_item_id)
            )
        ).all()
        return {item_id: qty for item_id, qty in rows}

    @staticmethod
    async def _sourcing(
        db: AsyncSession, clinic_id: UUID, item_ids: set[UUID]
    ) -> dict[UUID, tuple[SupplierItem, Supplier, Contact]]:
        """Chosen (link, supplier, contact) per item: preferred supplier first,
        else first link by supplier name. Items without a link are absent."""
        if not item_ids:
            return {}
        rows = (
            await db.execute(
                select(SupplierItem, Supplier, Contact)
                .join(Supplier, Supplier.id == SupplierItem.supplier_id)
                .join(Contact, Contact.id == Supplier.id)
                .where(
                    SupplierItem.clinic_id == clinic_id,
                    SupplierItem.is_active.is_(True),
                    Contact.is_active.is_(True),
                    SupplierItem.inventory_item_id.in_(item_ids),
                )
                .order_by(Supplier.is_preferred.desc(), Contact.name.asc())
            )
        ).all()
        chosen: dict[UUID, tuple[SupplierItem, Supplier, Contact]] = {}
        for link, supplier, contact in rows:
            chosen.setdefault(link.inventory_item_id, (link, supplier, contact))
        return chosen

    @staticmethod
    async def compute_suggestions(db: AsyncSession, clinic_id: UUID) -> list[dict]:
        """Return reorder suggestions for active items, sorted by item name.

        Only items with usage in the lookback window AND a sourcing link
        AND positive suggested quantity appear. Returns native values
        (UUID/Decimal) — jsonify at the registry coerces them.
        """
        items = (
            (
                await db.execute(
                    select(InventoryItem).where(
                        InventoryItem.clinic_id == clinic_id,
                        InventoryItem.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        item_ids = {item.id for item in items}
        usage = await ReorderService._usage_90d(db, clinic_id)
        on_order = await ReorderService._on_order(db, clinic_id)
        sourcing = await ReorderService._sourcing(db, clinic_id, item_ids)

        suggestions: list[dict] = []
        for item in items:
            usage_90d = usage.get(item.id, Decimal("0"))
            if usage_90d <= 0:
                continue
            source = sourcing.get(item.id)
            if source is None:
                continue
            link, supplier, contact = source
            lead_time = supplier.lead_time_days if supplier.lead_time_days is not None else 0
            daily_usage = (usage_90d / Decimal(LOOKBACK_DAYS)).quantize(Decimal("0.01"))
            reorder_point = (daily_usage * Decimal(lead_time)).quantize(
                Decimal("1"), rounding=ROUND_CEILING
            )
            outstanding = on_order.get(item.id, Decimal("0"))
            available = item.stock_quantity + outstanding
            suggested = (reorder_point - available).quantize(Decimal("1"), rounding=ROUND_CEILING)
            if suggested <= 0:
                continue
            suggestions.append(
                {
                    "inventory_item_id": item.id,
                    "item_name": item.name,
                    "category": item.category,
                    "unit": item.unit,
                    "usage_90d": usage_90d,
                    "daily_usage": daily_usage,
                    "supplier_id": supplier.id,
                    "supplier_name": contact.name,
                    "lead_time_days": supplier.lead_time_days,
                    "unit_price": link.price,
                    "stock_quantity": item.stock_quantity,
                    "on_order": outstanding,
                    "reorder_point": reorder_point,
                    "suggested_quantity": suggested,
                }
            )
        suggestions.sort(key=lambda s: s["item_name"].lower())
        return suggestions

    @staticmethod
    async def generate_orders(
        db: AsyncSession,
        clinic_id: UUID,
        item_ids: list[UUID],
        created_by: UUID | None,
    ) -> list[dict]:
        """Turn the requested suggestions into one draft PO per supplier."""
        suggestions = await ReorderService.compute_suggestions(db, clinic_id)
        by_item = {s["inventory_item_id"]: s for s in suggestions}
        missing = [str(i) for i in item_ids if i not in by_item]
        if missing:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"no reorder suggestion for item(s): {', '.join(missing)}",
            )

        by_supplier: dict[UUID, list[dict]] = {}
        for item_id in item_ids:
            suggestion = by_item[item_id]
            by_supplier.setdefault(suggestion["supplier_id"], []).append(suggestion)

        created: list[dict] = []
        for supplier_id, entries in by_supplier.items():
            payload = PurchaseOrderCreate(
                supplier_id=supplier_id,
                notes="Reorder suggestions",
                lines=[
                    PurchaseOrderLineCreate(
                        inventory_item_id=entry["inventory_item_id"],
                        quantity_ordered=entry["suggested_quantity"],
                        unit_price=entry["unit_price"],
                    )
                    for entry in entries
                ],
            )
            order = await PurchaseOrderService.create_order(
                db, clinic_id, payload, created_by=created_by
            )
            created.append(await PurchaseOrderService.get_order_response(db, clinic_id, order.id))
        return created
