"""ContactService — business logic for lab/supplier/provider contact CRUD."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Contact
from .schemas import ContactCreate, ContactUpdate


class ContactService:
    @staticmethod
    async def create_contact(
        db: AsyncSession, clinic_id: UUID, payload: ContactCreate
    ) -> Contact:
        contact = Contact(
            clinic_id=clinic_id,
            name=payload.name,
            contact_type=payload.contact_type,
            phone=payload.phone,
            email=payload.email,
            address=payload.address,
            notes=payload.notes,
        )
        db.add(contact)
        await db.commit()
        await db.refresh(contact)
        return contact

    @staticmethod
    async def list_contacts(
        db: AsyncSession,
        clinic_id: UUID,
        contact_type: str | None = None,
        search: str | None = None,
        include_inactive: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Contact], int]:
        stmt = select(Contact).where(Contact.clinic_id == clinic_id)
        if not include_inactive:
            stmt = stmt.where(Contact.is_active.is_(True))
        if contact_type:
            stmt = stmt.where(Contact.contact_type == contact_type)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(Contact.name.ilike(like), Contact.notes.ilike(like)))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Contact.name.asc()).offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_contact(db: AsyncSession, clinic_id: UUID, contact_id: UUID) -> Contact:
        stmt = select(Contact).where(Contact.id == contact_id, Contact.clinic_id == clinic_id)
        contact = (await db.execute(stmt)).scalar_one_or_none()
        if contact is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
        return contact

    @staticmethod
    async def update_contact(
        db: AsyncSession, clinic_id: UUID, contact_id: UUID, payload: ContactUpdate
    ) -> Contact:
        contact = await ContactService.get_contact(db, clinic_id, contact_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(contact, field, value)
        await db.commit()
        await db.refresh(contact)
        return contact

    @staticmethod
    async def delete_contact(db: AsyncSession, clinic_id: UUID, contact_id: UUID) -> None:
        # Soft delete: labs/suppliers may still be referenced by historical
        # records once the lab-order module (Phase 3) exists, so we never
        # hard-delete — same pattern as Patient.status.
        contact = await ContactService.get_contact(db, clinic_id, contact_id)
        contact.is_active = False
        await db.commit()
