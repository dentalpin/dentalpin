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

from app.modules.patients_clinical.models import Medication, SystemicDisease

from .models import (
    ReferenceAllergy,
    ReferenceContraindication,
    ReferenceDisease,
    ReferenceInteraction,
    ReferenceMedication,
)
from .schemas import PatientFlag

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

    # --- Interactions -------------------------------------------------------

    @staticmethod
    async def _assert_medication_exists(db: AsyncSession, clinic_id: UUID, med_id: UUID) -> None:
        stmt = select(ReferenceMedication.id).where(
            ReferenceMedication.id == med_id, ReferenceMedication.clinic_id == clinic_id
        )
        if (await db.execute(stmt)).scalar_one_or_none() is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="medication_id does not match a reference medication in this clinic",
            )

    @staticmethod
    async def create_interaction(
        db: AsyncSession, clinic_id: UUID, data: dict
    ) -> ReferenceInteraction:
        a, b = data["medication_a_id"], data["medication_b_id"]
        if a == b:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="A medication cannot interact with itself",
            )
        await MedicalReferenceService._assert_medication_exists(db, clinic_id, a)
        await MedicalReferenceService._assert_medication_exists(db, clinic_id, b)
        # Canonical order so (A,B) and (B,A) are always the same stored row.
        a, b = sorted([str(a), str(b)])

        existing_stmt = select(ReferenceInteraction.id).where(
            ReferenceInteraction.clinic_id == clinic_id,
            ReferenceInteraction.medication_a_id == a,
            ReferenceInteraction.medication_b_id == b,
        )
        if (await db.execute(existing_stmt)).scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="This medication pair is already recorded",
            )

        row = ReferenceInteraction(
            clinic_id=clinic_id,
            medication_a_id=a,
            medication_b_id=b,
            risk_note=data["risk_note"],
        )
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def list_interactions(
        db: AsyncSession, clinic_id: UUID, active_only: bool = True
    ) -> list[dict]:
        med_a = ReferenceMedication.__table__.alias("med_a")
        med_b = ReferenceMedication.__table__.alias("med_b")
        stmt = (
            select(
                ReferenceInteraction.id,
                ReferenceInteraction.medication_a_id,
                med_a.c.name.label("medication_a_name"),
                ReferenceInteraction.medication_b_id,
                med_b.c.name.label("medication_b_name"),
                ReferenceInteraction.risk_note,
                ReferenceInteraction.is_active,
            )
            .join(med_a, med_a.c.id == ReferenceInteraction.medication_a_id)
            .join(med_b, med_b.c.id == ReferenceInteraction.medication_b_id)
            .where(ReferenceInteraction.clinic_id == clinic_id)
        )
        if active_only:
            stmt = stmt.where(ReferenceInteraction.is_active.is_(True))
        stmt = stmt.order_by(med_a.c.name, med_b.c.name)
        return [dict(row._mapping) for row in (await db.execute(stmt)).all()]

    @staticmethod
    async def get_interaction(db: AsyncSession, item_id: UUID) -> ReferenceInteraction | None:
        stmt = select(ReferenceInteraction).where(ReferenceInteraction.id == item_id)
        return (await db.execute(stmt)).scalar_one_or_none()

    # --- Contraindications ----------------------------------------------------

    @staticmethod
    async def _assert_disease_exists(db: AsyncSession, clinic_id: UUID, disease_id: UUID) -> None:
        stmt = select(ReferenceDisease.id).where(
            ReferenceDisease.id == disease_id, ReferenceDisease.clinic_id == clinic_id
        )
        if (await db.execute(stmt)).scalar_one_or_none() is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="disease_id does not match a reference disease in this clinic",
            )

    @staticmethod
    async def create_contraindication(
        db: AsyncSession, clinic_id: UUID, data: dict
    ) -> ReferenceContraindication:
        await MedicalReferenceService._assert_disease_exists(db, clinic_id, data["disease_id"])
        await MedicalReferenceService._assert_medication_exists(db, clinic_id, data["medication_id"])

        existing_stmt = select(ReferenceContraindication.id).where(
            ReferenceContraindication.clinic_id == clinic_id,
            ReferenceContraindication.disease_id == data["disease_id"],
            ReferenceContraindication.medication_id == data["medication_id"],
        )
        if (await db.execute(existing_stmt)).scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="This disease/medication pair is already recorded",
            )

        row = ReferenceContraindication(
            clinic_id=clinic_id,
            disease_id=data["disease_id"],
            medication_id=data["medication_id"],
            risk_note=data["risk_note"],
        )
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def list_contraindications(
        db: AsyncSession, clinic_id: UUID, active_only: bool = True
    ) -> list[dict]:
        stmt = (
            select(
                ReferenceContraindication.id,
                ReferenceContraindication.disease_id,
                ReferenceDisease.name.label("disease_name"),
                ReferenceContraindication.medication_id,
                ReferenceMedication.name.label("medication_name"),
                ReferenceContraindication.risk_note,
                ReferenceContraindication.is_active,
            )
            .join(ReferenceDisease, ReferenceDisease.id == ReferenceContraindication.disease_id)
            .join(
                ReferenceMedication,
                ReferenceMedication.id == ReferenceContraindication.medication_id,
            )
            .where(ReferenceContraindication.clinic_id == clinic_id)
        )
        if active_only:
            stmt = stmt.where(ReferenceContraindication.is_active.is_(True))
        stmt = stmt.order_by(ReferenceDisease.name, ReferenceMedication.name)
        return [dict(row._mapping) for row in (await db.execute(stmt)).all()]

    @staticmethod
    async def get_contraindication(
        db: AsyncSession, item_id: UUID
    ) -> ReferenceContraindication | None:
        stmt = select(ReferenceContraindication).where(ReferenceContraindication.id == item_id)
        return (await db.execute(stmt)).scalar_one_or_none()

    # --- Active per-patient flags ---------------------------------------------

    @staticmethod
    async def get_patient_flags(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[PatientFlag]:
        """Cross-references a patient's *currently recorded* medications and
        diseases (only entries with a reference_id set — free-text-only
        legacy entries can't be reliably matched, so they're silently
        excluded rather than fuzzy-matched) against known interaction and
        contraindication pairs. Requires ``patients_clinical`` (declared in
        manifest.depends) — the one deliberate exception to this module
        otherwise never reading another module's data directly.
        """
        med_ids_stmt = select(Medication.reference_id).where(
            Medication.patient_id == patient_id, Medication.reference_id.is_not(None)
        )
        med_ids = {row[0] for row in (await db.execute(med_ids_stmt)).all()}

        disease_ids_stmt = select(SystemicDisease.reference_id).where(
            SystemicDisease.patient_id == patient_id, SystemicDisease.reference_id.is_not(None)
        )
        disease_ids = {row[0] for row in (await db.execute(disease_ids_stmt)).all()}

        flags: list[PatientFlag] = []

        if len(med_ids) >= 2:
            interactions = await MedicalReferenceService.list_interactions(db, clinic_id)
            for it in interactions:
                if it["medication_a_id"] in med_ids and it["medication_b_id"] in med_ids:
                    flags.append(
                        PatientFlag(
                            type="interaction",
                            risk_note=it["risk_note"],
                            involved=[it["medication_a_name"], it["medication_b_name"]],
                        )
                    )

        if med_ids and disease_ids:
            contraindications = await MedicalReferenceService.list_contraindications(db, clinic_id)
            for c in contraindications:
                if c["disease_id"] in disease_ids and c["medication_id"] in med_ids:
                    flags.append(
                        PatientFlag(
                            type="contraindication",
                            risk_note=c["risk_note"],
                            involved=[c["disease_name"], c["medication_name"]],
                        )
                    )

        return flags
