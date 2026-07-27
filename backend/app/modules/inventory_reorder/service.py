"""ReorderService — Phase 13e.

Computes reorder suggestions from existing data (no new "suggestion"
table — these are always derived fresh, never stored) and can turn a
chosen set of suggestions into draft POs, one per supplier.

Heuristic, not a precise forecast — documented plainly so nobody
mistakes it for more than it is:

    target_days_of_stock = (preferred supplier's lead_time_days, or a
                             7-day default if no supplier link exists)
                            + 14 (safety buffer)
    avg_daily_usage = sum of "used"-reason InventoryMovement quantity
                       over the last 90 days / 90
    suggested_quantity = max(0, avg_daily_usage * target_days_of_stock
                                  - quantity_on_hand)

If `reorder_max_quantity` is set on the item, the suggestion is capped
so `quantity_on_hand + suggested_quantity` never exceeds it. If there's
no usage history at all (new item, or never moved), the usage-based
calculation is 0 and the suggestion falls back to
`reorder_max_quantity - quantity_on_hand` if set, or is flagged as
`low_confidence` with a small default (enough to clear the low-stock
threshold) if neither usage history nor a max quantity exist.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.models import InventoryItem, InventoryMovement
from app.modules.purchase_orders.schemas import PurchaseOrderCreate, PurchaseOrderItemCreate
from app.modules.purchase_orders.service import PurchaseOrderService
from app.modules.suppliers.models import SupplierProfile
from app.modules.supplier_items.models import SupplierItem

_USAGE_WINDOW_DAYS = 90
_SAFETY_BUFFER_DAYS = 14
_DEFAULT_LEAD_TIME_DAYS = 7


class ReorderService:
    @staticmethod
    async def _avg_daily_usage(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> Decimal:
        since = datetime.now(UTC) - timedelta(days=_USAGE_WINDOW_DAYS)
        stmt = select(func.coalesce(func.sum(-InventoryMovement.quantity_delta), 0)).where(
            InventoryMovement.clinic_id == clinic_id,
            InventoryMovement.item_id == item_id,
            InventoryMovement.reason == "used",
            InventoryMovement.quantity_delta < 0,
            InventoryMovement.movement_date >= since,
        )
        total_used = (await db.execute(stmt)).scalar_one()
        return Decimal(str(total_used)) / Decimal(_USAGE_WINDOW_DAYS)

    @staticmethod
    async def _preferred_supplier(
        db: AsyncSession, clinic_id: UUID, item_id: UUID
    ) -> tuple[UUID | None, str | None, Decimal | None, int | None]:
        """Returns (supplier_contact_id, supplier_name, unit_price, lead_time_days)
        for this item's preferred supplier link, or the cheapest linked
        supplier if none is marked preferred, or all-None if unlinked."""
        stmt = (
            select(SupplierItem, SupplierProfile.lead_time_days)
            .outerjoin(SupplierProfile, SupplierProfile.contact_id == SupplierItem.supplier_contact_id)
            .where(SupplierItem.clinic_id == clinic_id, SupplierItem.inventory_item_id == item_id)
            .order_by(SupplierItem.is_preferred_supplier.desc(), SupplierItem.unit_price.asc())
        )
        row = (await db.execute(stmt)).first()
        if row is None:
            return None, None, None, None
        link, lead_time_days = row

        from app.modules.contacts.models import Contact

        supplier = await db.get(Contact, link.supplier_contact_id)
        return (
            link.supplier_contact_id,
            supplier.name if supplier else None,
            Decimal(str(link.unit_price)),
            lead_time_days,
        )

    @staticmethod
    async def get_suggestions(db: AsyncSession, clinic_id: UUID) -> list[dict]:
        stmt = select(InventoryItem).where(
            InventoryItem.clinic_id == clinic_id,
            InventoryItem.quantity_on_hand <= InventoryItem.low_stock_threshold,
        )
        low_stock_items = (await db.execute(stmt)).scalars().all()

        suggestions = []
        for item in low_stock_items:
            avg_daily = await ReorderService._avg_daily_usage(db, clinic_id, item.id)
            supplier_id, supplier_name, unit_price, lead_time_days = (
                await ReorderService._preferred_supplier(db, clinic_id, item.id)
            )

            effective_lead_time = lead_time_days if lead_time_days is not None else _DEFAULT_LEAD_TIME_DAYS
            target_days = effective_lead_time + _SAFETY_BUFFER_DAYS

            qty_on_hand = Decimal(str(item.quantity_on_hand))
            low_confidence = False

            if avg_daily > 0:
                suggested = max(Decimal("0"), avg_daily * target_days - qty_on_hand)
            elif item.reorder_max_quantity is not None:
                suggested = max(Decimal("0"), Decimal(str(item.reorder_max_quantity)) - qty_on_hand)
            else:
                # No usage history and no explicit target — crude
                # fallback, flagged so staff know to sanity-check it.
                suggested = max(Decimal("0"), Decimal(str(item.low_stock_threshold)) * 2 - qty_on_hand)
                low_confidence = True

            if item.reorder_max_quantity is not None:
                cap = Decimal(str(item.reorder_max_quantity)) - qty_on_hand
                suggested = min(suggested, max(Decimal("0"), cap))

            suggested = suggested.quantize(Decimal("1"))  # round to whole units
            if suggested <= 0:
                continue

            estimated_cost = None
            if unit_price is not None:
                estimated_cost = unit_price * suggested
            elif item.average_cost is not None:
                estimated_cost = Decimal(str(item.average_cost)) * suggested

            suggestions.append(
                {
                    "inventory_item_id": item.id,
                    "item_name": item.name,
                    "quantity_on_hand": qty_on_hand,
                    "low_stock_threshold": Decimal(str(item.low_stock_threshold)),
                    "reorder_max_quantity": (
                        Decimal(str(item.reorder_max_quantity))
                        if item.reorder_max_quantity is not None
                        else None
                    ),
                    "avg_daily_usage": avg_daily,
                    "lead_time_days": effective_lead_time,
                    "suggested_quantity": suggested,
                    "supplier_contact_id": supplier_id,
                    "supplier_name": supplier_name,
                    "unit_price": unit_price,
                    "estimated_cost": estimated_cost,
                    "low_confidence": low_confidence,
                }
            )

        return suggestions

    @staticmethod
    async def generate_purchase_orders(
        db: AsyncSession,
        clinic_id: UUID,
        selections: list[dict],  # [{inventory_item_id, supplier_contact_id, quantity, unit_price}]
        created_by: UUID | None,
    ) -> list[UUID]:
        """Groups selections by supplier (a PO can only have one) and
        creates one draft PO per supplier group."""
        by_supplier: dict[UUID, list[dict]] = {}
        for sel in selections:
            supplier_id = sel.get("supplier_contact_id")
            if not supplier_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No supplier specified for item {sel.get('inventory_item_id')} — link a supplier first (Phase 13b) or pick one manually.",
                )
            by_supplier.setdefault(UUID(str(supplier_id)), []).append(sel)

        created_ids: list[UUID] = []
        for supplier_id, items in by_supplier.items():
            payload = PurchaseOrderCreate(
                supplier_contact_id=supplier_id,
                items=[
                    PurchaseOrderItemCreate(
                        inventory_item_id=UUID(str(item["inventory_item_id"])),
                        unit_price=Decimal(str(item["unit_price"])),
                        quantity_ordered=Decimal(str(item["quantity"])),
                    )
                    for item in items
                ],
            )
            po = await PurchaseOrderService.create(db, clinic_id, payload, created_by)
            created_ids.append(po.id)

        return created_ids
