"""MedicalReferenceService — generic search/CRUD over the three lookup tables.

The three tables (allergy/medication/disease) are shaped identically apart
from ``ReferenceDisease.is_apci``, so CRUD is implemented once, generically,
against whichever model class is passed in — search/create/update/delete
methods are typed narrowly per-entity only where ``is_apci`` matters.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ReferenceAllergy, ReferenceDisease, ReferenceMedication

ReferenceModel = ReferenceAllergy | ReferenceMedication | ReferenceDisease


class MedicalReferenceService:
    @staticmethod
    async def search(
        db: AsyncSession,
        model,
        clinic_id: UUID,
        query: str | None,
        active_only: bool = True,
        limit: int = 25,
    ) -> list[ReferenceModel]:
        stmt = select(model).where(model.clinic_id == clinic_id)
        if active_only:
            stmt = stmt.where(model.is_active.is_(True))
        if query:
            stmt = stmt.where(func.lower(model.name).contains(query.lower()))
        stmt = stmt.order_by(model.name).limit(limit)
        return list((await db.execute(stmt)).scalars())

    @staticmethod
    async def create(db: AsyncSession, model, clinic_id: UUID, data: dict) -> ReferenceModel:
        existing_stmt = select(model).where(
            model.clinic_id == clinic_id, func.lower(model.name) == data["name"].lower()
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f'"{data["name"]}" already exists in this list',
            )
        row = model(clinic_id=clinic_id, **data)
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def get(db: AsyncSession, model, item_id: UUID) -> ReferenceModel | None:
        stmt = select(model).where(model.id == item_id)
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def update(db: AsyncSession, row: ReferenceModel, data: dict) -> ReferenceModel:
        for key, value in data.items():
            if value is not None:
                setattr(row, key, value)
        await db.flush()
        return row

    @staticmethod
    async def deactivate(db: AsyncSession, row: ReferenceModel) -> ReferenceModel:
        """Soft-delete — items already referenced by patient records must
        keep existing, just stop showing up in future searches."""
        row.is_active = False
        await db.flush()
        return row
