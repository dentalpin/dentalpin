"""Attachment owner resolvers for the orthodontics module (ADR 0007).

Registers ``ortho_case`` / ``ortho_control`` so clinical photos can be
attached to cases and controls through the generic media endpoints and
paired start-vs-current via the before/after pairing.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.media.attachment_registry import OwnerSpec, attachment_registry

from .models import OrthoCase, OrthoControl


async def _resolve_case(db: AsyncSession, clinic_id: UUID, owner_id: UUID) -> UUID | None:
    result = await db.execute(
        select(OrthoCase.patient_id).where(
            OrthoCase.id == owner_id, OrthoCase.clinic_id == clinic_id
        )
    )
    row = result.first()
    return row[0] if row else None


async def _resolve_control(db: AsyncSession, clinic_id: UUID, owner_id: UUID) -> UUID | None:
    result = await db.execute(
        select(OrthoCase.patient_id)
        .join(OrthoControl, OrthoControl.case_id == OrthoCase.id)
        .where(
            OrthoControl.id == owner_id,
            OrthoControl.clinic_id == clinic_id,
            OrthoCase.clinic_id == clinic_id,
        )
    )
    row = result.first()
    return row[0] if row else None


def register() -> None:
    attachment_registry.register(
        OwnerSpec(owner_type="ortho_case", resolver=_resolve_case, label="Caso de ortodoncia")
    )
    attachment_registry.register(
        OwnerSpec(
            owner_type="ortho_control", resolver=_resolve_control, label="Control de ortodoncia"
        )
    )
