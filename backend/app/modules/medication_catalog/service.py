"""MedicationCatalogService — clinic-scoped CRUD over the medication list.

Every query filters on ``clinic_id``. Duplicate names are rejected
case-insensitively with a 409 (create and rename), mirroring the
medical_reference behaviour; the DB-level unique constraint closes the
concurrent-create race.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import MedicationCatalogItem
from .schemas import MedicationCatalogCreate, MedicationCatalogUpdate


def _norm(name: str) -> str:
    """Must match the DB index key exactly (``lower(btrim(name))``).

    Collapsing inner whitespace here too would make the app check *looser*
    than the index: "Ibuprofen  400 mg" typed twice passes the 409 lookup
    and then trips the unique index as a raw 500.
    """
    return name.strip().lower()


class MedicationCatalogService:
    @staticmethod
    async def list_items(
        db: AsyncSession,
        clinic_id: UUID,
        q: str | None = None,
        form: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[MedicationCatalogItem], int]:
        stmt = select(MedicationCatalogItem).where(MedicationCatalogItem.clinic_id == clinic_id)
        if q:
            stmt = stmt.where(MedicationCatalogItem.name.ilike(f"%{q}%"))
        if form:
            stmt = stmt.where(MedicationCatalogItem.form == form)
        if is_active is not None:
            stmt = stmt.where(MedicationCatalogItem.is_active == is_active)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(MedicationCatalogItem.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_item(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> MedicationCatalogItem:
        stmt = select(MedicationCatalogItem).where(
            MedicationCatalogItem.id == item_id,
            MedicationCatalogItem.clinic_id == clinic_id,
        )
        item = (await db.execute(stmt)).scalar_one_or_none()
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found"
            )
        return item

    @staticmethod
    async def find_by_name(
        db: AsyncSession, clinic_id: UUID, name: str
    ) -> MedicationCatalogItem | None:
        """Case-insensitive lookup used by create/update and the seeder."""
        stmt = select(MedicationCatalogItem).where(
            MedicationCatalogItem.clinic_id == clinic_id,
            func.lower(func.btrim(MedicationCatalogItem.name)) == _norm(name),
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def create_item(
        db: AsyncSession, clinic_id: UUID, payload: MedicationCatalogCreate
    ) -> MedicationCatalogItem:
        existing = await MedicationCatalogService.find_by_name(db, clinic_id, payload.name)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A medication with this name already exists",
            )
        item = MedicationCatalogItem(clinic_id=clinic_id, **payload.model_dump())
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def update_item(
        db: AsyncSession, clinic_id: UUID, item_id: UUID, payload: MedicationCatalogUpdate
    ) -> MedicationCatalogItem:
        item = await MedicationCatalogService.get_item(db, clinic_id, item_id)
        data = payload.model_dump(exclude_unset=True)

        new_name = data.get("name")
        if new_name is not None and _norm(new_name) != _norm(item.name):
            other = await MedicationCatalogService.find_by_name(db, clinic_id, new_name)
            if other is not None and other.id != item.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A medication with this name already exists",
                )

        for field, value in data.items():
            setattr(item, field, value)
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def delete_item(db: AsyncSession, clinic_id: UUID, item_id: UUID) -> None:
        item = await MedicationCatalogService.get_item(db, clinic_id, item_id)
        await db.delete(item)
        await db.commit()
