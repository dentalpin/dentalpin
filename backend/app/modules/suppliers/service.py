"""SupplierService — reads Contact (contact_type == "supplier"),
writes SupplierProfile.

Never mutates Contact. Contact creation/editing (name, phone, email,
address, notes, is_active) still goes through the existing
`/api/v1/contacts/*` endpoints — this module only owns the
procurement-specific extension table.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contacts.models import Contact

from .models import SupplierProfile
from .schemas import SupplierProfileUpsert


class SupplierService:
    @staticmethod
    async def _get_supplier_contact(db: AsyncSession, clinic_id: UUID, contact_id: UUID) -> Contact:
        contact = await db.get(Contact, contact_id)
        if contact is None or contact.clinic_id != clinic_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
        if contact.contact_type != "supplier":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact is not a supplier",
            )
        return contact

    @staticmethod
    async def get_supplier(
        db: AsyncSession, clinic_id: UUID, contact_id: UUID
    ) -> tuple[Contact, SupplierProfile | None]:
        contact = await SupplierService._get_supplier_contact(db, clinic_id, contact_id)
        profile = await db.get(SupplierProfile, contact_id)
        return contact, profile

    @staticmethod
    async def list_suppliers(
        db: AsyncSession,
        clinic_id: UUID,
        search: str | None = None,
        is_preferred: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[tuple[Contact, SupplierProfile | None]], int]:
        stmt = select(Contact).where(
            Contact.clinic_id == clinic_id, Contact.contact_type == "supplier"
        )
        if search:
            stmt = stmt.where(Contact.name.ilike(f"%{search}%"))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Contact.name.asc()).offset((page - 1) * page_size).limit(page_size)
        contacts = (await db.execute(stmt)).scalars().all()

        if not contacts:
            return [], total

        ids = [c.id for c in contacts]
        profiles = (
            (await db.execute(select(SupplierProfile).where(SupplierProfile.contact_id.in_(ids))))
            .scalars()
            .all()
        )
        profiles_by_id = {p.contact_id: p for p in profiles}
        pairs = [(c, profiles_by_id.get(c.id)) for c in contacts]

        if is_preferred is not None:
            pairs = [(c, p) for c, p in pairs if bool(p and p.is_preferred) == is_preferred]

        return pairs, total

    @staticmethod
    async def upsert_profile(
        db: AsyncSession, clinic_id: UUID, contact_id: UUID, payload: SupplierProfileUpsert
    ) -> SupplierProfile:
        await SupplierService._get_supplier_contact(db, clinic_id, contact_id)

        profile = await db.get(SupplierProfile, contact_id)
        if profile is None:
            profile = SupplierProfile(
                contact_id=contact_id, clinic_id=clinic_id, **payload.model_dump()
            )
            db.add(profile)
        else:
            for field, value in payload.model_dump().items():
                setattr(profile, field, value)

        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def delete_profile(db: AsyncSession, clinic_id: UUID, contact_id: UUID) -> None:
        profile = await db.get(SupplierProfile, contact_id)
        if profile is None or profile.clinic_id != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Supplier profile not found"
            )
        await db.delete(profile)
        await db.commit()
