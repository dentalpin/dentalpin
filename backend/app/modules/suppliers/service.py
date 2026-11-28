"""Business logic for the suppliers module."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contacts.models import Contact

from .models import Supplier
from .schemas import SupplierCreate, SupplierUpdate


class SupplierService:
    @staticmethod
    async def create_supplier(
        db: AsyncSession, clinic_id: UUID, payload: SupplierCreate
    ) -> tuple[Contact, Supplier]:
        """Atomically create a Contact(type='supplier') and its 1:1 Supplier row."""

        # 1. Create the base contact
        contact = Contact(
            clinic_id=clinic_id,
            name=payload.name,
            contact_type="supplier",
            phone=payload.phone,
            email=payload.email,
            address=payload.address,
            notes=payload.notes,
        )
        db.add(contact)
        await db.flush()  # To generate contact.id

        # 2. Create the supplier extension
        supplier = Supplier(
            id=contact.id,
            clinic_id=clinic_id,
            website=payload.website,
            payment_terms=payload.payment_terms,
            lead_time_days=payload.lead_time_days,
            is_preferred=payload.is_preferred,
        )
        db.add(supplier)

        await db.commit()
        await db.refresh(contact)
        await db.refresh(supplier)

        return contact, supplier

    @staticmethod
    async def get_supplier(
        db: AsyncSession, clinic_id: UUID, supplier_id: UUID
    ) -> tuple[Contact, Supplier] | None:
        """Fetch the composite Supplier and Contact securely scoped by clinic."""
        contact = (
            await db.execute(
                select(Contact).where(
                    Contact.id == supplier_id,
                    Contact.clinic_id == clinic_id,
                    Contact.contact_type == "supplier",
                )
            )
        ).scalar_one_or_none()

        if not contact:
            return None

        supplier = (
            await db.execute(
                select(Supplier).where(Supplier.id == supplier_id, Supplier.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()

        if not supplier:
            return None

        return contact, supplier

    @staticmethod
    async def list_suppliers(
        db: AsyncSession,
        clinic_id: UUID,
        search: str | None = None,
        is_preferred: bool | None = None,
        include_inactive: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[tuple[Contact, Supplier]], int]:
        """List suppliers with multi-tenancy and pagination."""
        stmt = (
            select(Contact, Supplier)
            .join(Supplier, Supplier.id == Contact.id)
            .where(
                Contact.clinic_id == clinic_id,
                Supplier.clinic_id == clinic_id,
                Contact.contact_type == "supplier",
            )
        )

        if not include_inactive:
            stmt = stmt.where(Contact.is_active.is_(True))

        if is_preferred is not None:
            stmt = stmt.where(Supplier.is_preferred.is_(is_preferred))

        if search:
            stmt = stmt.where(
                Contact.name.icontains(search, autoescape=True)
                | Contact.phone.icontains(search, autoescape=True)
                | Contact.email.icontains(search, autoescape=True)
            )

        stmt = stmt.order_by(Contact.name.asc(), Contact.id)

        # Total count
        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(total_stmt)).scalar_one()

        # Pagination
        page_size = min(max(page_size, 1), 100)
        offset = (max(page, 1) - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await db.execute(stmt)
        # Returns rows of tuple(Contact, Supplier)
        items = list(result.all())

        return items, total

    @staticmethod
    async def update_supplier(
        db: AsyncSession, contact: Contact, supplier: Supplier, payload: SupplierUpdate
    ) -> tuple[Contact, Supplier]:
        """Atomically update Contact and Supplier rows."""
        payload_dict = payload.model_dump(exclude_unset=True)

        contact_fields = {"name", "phone", "email", "address", "notes", "is_active"}
        supplier_fields = {"website", "payment_terms", "lead_time_days", "is_preferred"}

        for field, value in payload_dict.items():
            if field in contact_fields:
                setattr(contact, field, value)
            elif field in supplier_fields:
                setattr(supplier, field, value)

        await db.commit()
        await db.refresh(contact)
        await db.refresh(supplier)

        return contact, supplier

    @staticmethod
    async def delete_supplier(db: AsyncSession, contact: Contact) -> None:
        """Soft-delete a supplier (updates the underlying Contact)."""
        contact.is_active = False
        await db.commit()
        await db.refresh(contact)
