"""SupplierItemService — supplier↔item pricing links.

Depends on `contacts`, `inventory`, and `suppliers` (declared in
`__init__.py`'s manifest) to validate both sides and join in display
fields (supplier name, item name, lead time) — never writes to any of
those three.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contacts.models import Contact
from app.modules.inventory.models import InventoryItem
from app.modules.suppliers.models import SupplierProfile

from .models import SupplierItem
from .schemas import SupplierItemCreate, SupplierItemUpdate


class SupplierItemService:
    @staticmethod
    async def _validate_supplier(db: AsyncSession, clinic_id: UUID, contact_id: UUID) -> Contact:
        contact = await db.get(Contact, contact_id)
        if contact is None or contact.clinic_id != clinic_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
        if contact.contact_type != "supplier":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Contact is not a supplier"
            )
        return contact

    @staticmethod
    async def _validate_item(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> InventoryItem:
        item = await db.get(InventoryItem, item_id)
        if item is None or item.clinic_id != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )
        return item

    @staticmethod
    async def create(
        db: AsyncSession, clinic_id: UUID, payload: SupplierItemCreate
    ) -> tuple[SupplierItem, str, str, int | None]:
        supplier = await SupplierItemService._validate_supplier(
            db, clinic_id, payload.supplier_contact_id
        )
        item = await SupplierItemService._validate_item(db, clinic_id, payload.inventory_item_id)

        link = SupplierItem(
            clinic_id=clinic_id,
            supplier_contact_id=payload.supplier_contact_id,
            inventory_item_id=payload.inventory_item_id,
            supplier_sku=payload.supplier_sku,
            unit_price=payload.unit_price,
            is_preferred_supplier=payload.is_preferred_supplier,
            notes=payload.notes,
        )
        db.add(link)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This supplier is already linked to this item — edit the existing link instead.",
            ) from None
        await db.refresh(link)

        profile = await db.get(SupplierProfile, payload.supplier_contact_id)
        return link, supplier.name, item.name, (profile.lead_time_days if profile else None)

    @staticmethod
    async def list_links(
        db: AsyncSession,
        clinic_id: UUID,
        supplier_contact_id: UUID | None = None,
        inventory_item_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[tuple[SupplierItem, str, str, int | None]], int]:
        stmt = (
            select(SupplierItem, Contact.name, InventoryItem.name, SupplierProfile.lead_time_days)
            .join(Contact, Contact.id == SupplierItem.supplier_contact_id)
            .join(InventoryItem, InventoryItem.id == SupplierItem.inventory_item_id)
            .outerjoin(SupplierProfile, SupplierProfile.contact_id == SupplierItem.supplier_contact_id)
            .where(SupplierItem.clinic_id == clinic_id)
        )
        if supplier_contact_id:
            stmt = stmt.where(SupplierItem.supplier_contact_id == supplier_contact_id)
        if inventory_item_id:
            stmt = stmt.where(SupplierItem.inventory_item_id == inventory_item_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(SupplierItem.unit_price.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).all()
        return [(row[0], row[1], row[2], row[3]) for row in rows], total

    @staticmethod
    async def _get_link(db: AsyncSession, clinic_id: UUID, link_id: UUID) -> SupplierItem:
        link = await db.get(SupplierItem, link_id)
        if link is None or link.clinic_id != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Supplier-item link not found"
            )
        return link

    @staticmethod
    async def update(
        db: AsyncSession, clinic_id: UUID, link_id: UUID, payload: SupplierItemUpdate
    ) -> tuple[SupplierItem, str, str, int | None]:
        link = await SupplierItemService._get_link(db, clinic_id, link_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(link, field, value)
        await db.commit()
        await db.refresh(link)

        supplier = await db.get(Contact, link.supplier_contact_id)
        item = await db.get(InventoryItem, link.inventory_item_id)
        profile = await db.get(SupplierProfile, link.supplier_contact_id)
        return (
            link,
            supplier.name if supplier else "",
            item.name if item else "",
            profile.lead_time_days if profile else None,
        )

    @staticmethod
    async def delete(db: AsyncSession, clinic_id: UUID, link_id: UUID) -> None:
        link = await SupplierItemService._get_link(db, clinic_id, link_id)
        await db.delete(link)
        await db.commit()
