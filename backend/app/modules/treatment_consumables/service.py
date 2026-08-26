"""TreatmentConsumablesService — validated links, clinic-scoped everywhere.

Reads ``catalog`` and ``inventory`` (ADR 0002 cross-module reads) to
validate links and resolve display names; writes only to its own table.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import TreatmentCatalogItem
from app.modules.inventory.models import InventoryItem
from app.modules.treatment_consumables.models import TreatmentConsumable


def treatment_display_name(treatment: TreatmentCatalogItem) -> str:
    """Catalog names are localized JSONB — prefer es > en > first,
    falling back to the internal code for a row with no names."""
    names = treatment.names or {}
    for key in ("es", "en"):
        if names.get(key):
            return str(names[key])
    for value in names.values():
        if value:
            return str(value)
    return treatment.internal_code or "—"


class TreatmentConsumablesService:
    @staticmethod
    async def list_links(
        db: AsyncSession,
        clinic_id: UUID,
        catalog_item_id: UUID | None = None,
        inventory_item_id: UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[TreatmentConsumable], int]:
        stmt = select(TreatmentConsumable).where(TreatmentConsumable.clinic_id == clinic_id)
        if catalog_item_id:
            stmt = stmt.where(TreatmentConsumable.catalog_item_id == catalog_item_id)
        if inventory_item_id:
            stmt = stmt.where(TreatmentConsumable.inventory_item_id == inventory_item_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(TreatmentConsumable.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_link(db: AsyncSession, clinic_id: UUID, link_id: UUID) -> TreatmentConsumable:
        stmt = select(TreatmentConsumable).where(
            TreatmentConsumable.id == link_id,
            TreatmentConsumable.clinic_id == clinic_id,
        )
        link = (await db.execute(stmt)).scalar_one_or_none()
        if link is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        return link

    @staticmethod
    async def _validated_pair(
        db: AsyncSession, clinic_id: UUID, catalog_item_id: UUID, inventory_item_id: UUID
    ) -> tuple[TreatmentCatalogItem, InventoryItem]:
        """Both endpoints must exist inside the same clinic — this module
        reads its dependencies but never writes them."""
        treatment = (
            await db.execute(
                select(TreatmentCatalogItem).where(
                    TreatmentCatalogItem.id == catalog_item_id,
                    TreatmentCatalogItem.clinic_id == clinic_id,
                )
            )
        ).scalar_one_or_none()
        if treatment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Catalog treatment not found",
            )

        item = (
            await db.execute(
                select(InventoryItem).where(
                    InventoryItem.id == inventory_item_id,
                    InventoryItem.clinic_id == clinic_id,
                )
            )
        ).scalar_one_or_none()
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )
        return treatment, item

    @staticmethod
    async def create_link(
        db: AsyncSession,
        clinic_id: UUID,
        catalog_item_id: UUID,
        inventory_item_id: UUID,
        quantity: Decimal,
        note: str | None = None,
    ) -> TreatmentConsumable:
        treatment, item = await TreatmentConsumablesService._validated_pair(
            db, clinic_id, catalog_item_id, inventory_item_id
        )
        link = TreatmentConsumable(
            clinic_id=clinic_id,
            catalog_item_id=treatment.id,
            inventory_item_id=item.id,
            quantity=quantity,
            note=note or None,
        )
        db.add(link)
        try:
            await db.commit()
        except IntegrityError as exc:
            # uq_treatment_consumables_link. Answered from the constraint
            # rather than a SELECT-then-INSERT pre-check so two concurrent
            # creates both get a 409 instead of one raising a raw 500.
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This treatment already consumes this inventory item",
            ) from exc
        await db.refresh(link)
        return link

    @staticmethod
    async def update_quantity(
        db: AsyncSession,
        clinic_id: UUID,
        link_id: UUID,
        quantity: Decimal,
        note: str | None = None,
    ) -> TreatmentConsumable:
        link = await TreatmentConsumablesService.get_link(db, clinic_id, link_id)
        link.quantity = quantity
        if note is not None:
            link.note = note or None
        await db.commit()
        await db.refresh(link)
        return link

    @staticmethod
    async def delete_link(db: AsyncSession, clinic_id: UUID, link_id: UUID) -> None:
        link = await TreatmentConsumablesService.get_link(db, clinic_id, link_id)
        await db.delete(link)
        await db.commit()

    @staticmethod
    async def detailed_links(
        db: AsyncSession, clinic_id: UUID, links: list[TreatmentConsumable]
    ) -> list[dict]:
        """Resolve display names for a page of links (two batched reads)."""
        treatment_ids = {lnk.catalog_item_id for lnk in links}
        item_ids = {lnk.inventory_item_id for lnk in links}
        treatments: dict[UUID, TreatmentCatalogItem] = {}
        items: dict[UUID, InventoryItem] = {}
        if treatment_ids:
            rows = (
                await db.execute(
                    select(TreatmentCatalogItem).where(
                        TreatmentCatalogItem.clinic_id == clinic_id,
                        TreatmentCatalogItem.id.in_(treatment_ids),
                    )
                )
            ).scalars()
            treatments = {t.id: t for t in rows}
        if item_ids:
            rows = (
                await db.execute(
                    select(InventoryItem).where(
                        InventoryItem.clinic_id == clinic_id,
                        InventoryItem.id.in_(item_ids),
                    )
                )
            ).scalars()
            items = {i.id: i for i in rows}

        detailed = []
        for lnk in links:
            t = treatments.get(lnk.catalog_item_id)
            i = items.get(lnk.inventory_item_id)
            detailed.append(
                {
                    "id": lnk.id,
                    "clinic_id": lnk.clinic_id,
                    "catalog_item_id": lnk.catalog_item_id,
                    "inventory_item_id": lnk.inventory_item_id,
                    "quantity": lnk.quantity,
                    "note": lnk.note,
                    "created_at": lnk.created_at,
                    "updated_at": lnk.updated_at,
                    "treatment_name": treatment_display_name(t) if t else "—",
                    "treatment_code": t.internal_code if t else None,
                    "item_name": i.name if i else "—",
                    "item_unit": i.unit if i else None,
                }
            )
        return detailed

    @staticmethod
    async def link_options(
        db: AsyncSession, clinic_id: UUID, q: str | None = None, limit: int = 20
    ) -> tuple[list[TreatmentCatalogItem], list[InventoryItem]]:
        """Search-based picker data from both dependency modules.

        Catalog names are JSONB-localized so the `q` match runs in Python
        over the clinic's own rows (bounded; avoids dialect-specific jsonb
        operators); inventory names are plain columns matched in SQL.
        """
        needle = (q or "").strip().lower()

        treatments = (
            (
                await db.execute(
                    select(TreatmentCatalogItem).where(TreatmentCatalogItem.clinic_id == clinic_id)
                )
            )
            .scalars()
            .all()
        )
        matched_treatments = [
            t
            for t in treatments
            if not needle
            or any(needle in str(v).lower() for v in (t.names or {}).values())
            or needle in (t.internal_code or "").lower()
        ][:limit]

        item_stmt = select(InventoryItem).where(InventoryItem.clinic_id == clinic_id)
        if needle:
            item_stmt = item_stmt.where(InventoryItem.name.ilike(f"%{needle}%"))
        matched_items = (await db.execute(item_stmt.limit(limit))).scalars().all()
        return list(matched_treatments), list(matched_items)
