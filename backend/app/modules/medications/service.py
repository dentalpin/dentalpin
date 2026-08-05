"""MedicationService — business logic for the medication catalog.

Static methods, thin routers (per patients/service.py). db.flush()
only — the get_db dependency commits on successful request exit, so
services must NOT call db.commit()/db.refresh() themselves.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Medication, MedicationForm


class MedicationService:
    @staticmethod
    async def list_medications(
        db: AsyncSession,
        clinic_id: UUID,
        *,
        name: str | None = None,
        form: MedicationForm | None = None,
        is_prescribed: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Medication], int]:
        page_size = min(max(page_size, 1), 100)
        page = max(page, 1)
        offset = (page - 1) * page_size

        conditions = [Medication.clinic_id == clinic_id]
        if name:
            conditions.append(Medication.name.ilike(f"%{name}%"))
        if form is not None:
            conditions.append(Medication.form == form)
        if is_prescribed is not None:
            conditions.append(Medication.is_prescribed.is_(is_prescribed))

        total = (
            await db.execute(select(func.count(Medication.id)).where(*conditions))
        ).scalar() or 0

        result = await db.execute(
            select(Medication)
            .where(*conditions)
            .order_by(Medication.name)
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def get_medication(
        db: AsyncSession, clinic_id: UUID, medication_id: UUID
    ) -> Medication | None:
        result = await db.execute(
            select(Medication).where(
                Medication.id == medication_id,
                Medication.clinic_id == clinic_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_medication(db: AsyncSession, clinic_id: UUID, data: dict) -> Medication:
        medication = Medication(clinic_id=clinic_id, **data)
        db.add(medication)
        await db.flush()
        return medication

    @staticmethod
    async def update_medication(db: AsyncSession, medication: Medication, data: dict) -> Medication:
        """``data`` should come from model_dump(exclude_unset=True)."""
        for key, value in data.items():
            setattr(medication, key, value)
        await db.flush()
        return medication

    @staticmethod
    async def delete_medication(db: AsyncSession, medication: Medication) -> None:
        await db.delete(medication)
        await db.flush()
