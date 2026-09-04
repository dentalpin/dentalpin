"""Business logic for the supplier_items module."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contacts.models import Contact
from app.modules.inventory.models import InventoryItem
from app.modules.suppliers.models import Supplier

from .models import SupplierItem
from .schemas import SupplierItemCreate, SupplierItemUpdate


class SupplierItemService:
    @staticmethod
    async def create_link(
        db: AsyncSession, clinic_id: UUID, payload: SupplierItemCreate
    ) -> tuple[SupplierItem, str, str]:
        """Create a supplier<->item link, validating both ends in-clinic.

        Returns (link, supplier_name, item_name) so routers/tools can build
        the denormalized response without extra queries.
        """
        # Validate against the suppliers row (the FK target), not just the
        # Contact: a Contact(type='supplier') without its 1:1 extension would
        # pass a Contact-only check and then fail the FK as a misleading 409.
        supplier_row = (
            await db.execute(
                select(Supplier, Contact.name)
                .join(Contact, Contact.id == Supplier.id)
                .where(Supplier.id == payload.supplier_id, Supplier.clinic_id == clinic_id)
            )
        ).first()
        if not supplier_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
        supplier_name: str = supplier_row[1]

        item = (
            await db.execute(
                select(InventoryItem).where(
                    InventoryItem.id == payload.inventory_item_id,
                    InventoryItem.clinic_id == clinic_id,
                )
            )
        ).scalar_one_or_none()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
            )

        # A soft-deleted link for the same pair is revived with the new
        # SKU/price instead of tripping the UNIQUE constraint — otherwise a
        # deactivated pair could never be linked again.
        link = (
            await db.execute(
                select(SupplierItem).where(
                    SupplierItem.clinic_id == clinic_id,
                    SupplierItem.supplier_id == payload.supplier_id,
                    SupplierItem.inventory_item_id == payload.inventory_item_id,
                    SupplierItem.is_active.is_(False),
                )
            )
        ).scalar_one_or_none()
        if link:
            link.is_active = True
            link.supplier_sku = payload.supplier_sku
            link.price = payload.price
        else:
            link = SupplierItem(
                clinic_id=clinic_id,
                supplier_id=payload.supplier_id,
                inventory_item_id=payload.inventory_item_id,
                supplier_sku=payload.supplier_sku,
                price=payload.price,
            )
            db.add(link)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This supplier already prices this inventory item",
            )
        await db.refresh(link)

        return link, supplier_name, item.name

    @staticmethod
    async def get_link(
        db: AsyncSession, clinic_id: UUID, link_id: UUID
    ) -> tuple[SupplierItem, str, str] | None:
        """Fetch one active link scoped by clinic, plus denormalized names."""
        row = (
            await db.execute(
                select(SupplierItem, Contact, InventoryItem)
                .join(Contact, Contact.id == SupplierItem.supplier_id)
                .join(InventoryItem, InventoryItem.id == SupplierItem.inventory_item_id)
                .where(
                    SupplierItem.id == link_id,
                    SupplierItem.clinic_id == clinic_id,
                    SupplierItem.is_active.is_(True),
                )
            )
        ).first()
        if not row:
            return None
        link, supplier, item = row
        return link, supplier.name, item.name

    @staticmethod
    async def list_links(
        db: AsyncSession,
        clinic_id: UUID,
        supplier_id: UUID | None = None,
        inventory_item_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[tuple[SupplierItem, str, str]], int]:
        """List active links with multi-tenancy, optional filters and pagination."""
        stmt = (
            select(SupplierItem, Contact, InventoryItem)
            .join(Contact, Contact.id == SupplierItem.supplier_id)
            .join(InventoryItem, InventoryItem.id == SupplierItem.inventory_item_id)
            .where(SupplierItem.clinic_id == clinic_id)
            .where(SupplierItem.is_active.is_(True))
        )

        if supplier_id is not None:
            stmt = stmt.where(SupplierItem.supplier_id == supplier_id)
        if inventory_item_id is not None:
            stmt = stmt.where(SupplierItem.inventory_item_id == inventory_item_id)

        stmt = stmt.order_by(Contact.name.asc(), InventoryItem.name.asc())

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(total_stmt)).scalar_one()

        page_size = min(max(page_size, 1), 100)
        offset = (max(page, 1) - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await db.execute(stmt)
        return list(result.all()), total

    @staticmethod
    async def update_link(
        db: AsyncSession,
        link: SupplierItem,
        payload: SupplierItemUpdate,
    ) -> SupplierItem:
        """Update SKU/price on an existing link. Only forwards supplied fields
        (``exclude_unset``) so an omitted price/SKU is not silently wiped (M4)."""
        payload_dict = payload.model_dump(exclude_unset=True)
        for field, value in payload_dict.items():
            setattr(link, field, value)
        await db.commit()
        await db.refresh(link)
        return link

    @staticmethod
    async def deactivate_link(db: AsyncSession, link: SupplierItem) -> None:
        """Soft-delete the link (L7): flip ``is_active`` so the row is kept
        for historical purchase-order references. No hard DELETE."""
        link.is_active = False
        await db.commit()
        await db.refresh(link)
