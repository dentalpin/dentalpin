"""PatientRelationshipsService — patient relationships CRUD.

Cross-module read of ``patients`` is allowed: this module lists ``patients``
in ``manifest.depends`` (ADR 0002).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.patients.models import Patient

from .models import PatientRelationship
from .schemas import INVERSE_RELATIONSHIP_TYPE


class PatientRelationshipsService:
    # --- Relationships ------------------------------------------------------

    @staticmethod
    async def _assert_patient_in_clinic(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> None:
        stmt = select(Patient.id).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
        found = (await db.execute(stmt)).scalar_one_or_none()
        if found is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="related_patient_id does not match a patient in this clinic",
            )

    @staticmethod
    async def create_relationship(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, data: dict
    ) -> PatientRelationship:
        related_patient_id = data["related_patient_id"]
        # relationship_type validity is enforced by the schema's Literal
        # (422 on bad input), matching how the rest of the repo validates.
        relationship_type = data["relationship_type"]

        if related_patient_id == patient_id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="A patient cannot be related to themselves",
            )
        await PatientRelationshipsService._assert_patient_in_clinic(
            db, clinic_id, related_patient_id
        )

        # A pair can only be linked once, in either direction. The unique key
        # covers one direction only, so serialise on the two patient rows
        # (in id order, so A→B and B→A can't deadlock) before the check.
        await db.execute(
            select(Patient.id)
            .where(
                Patient.clinic_id == clinic_id,
                Patient.id.in_([patient_id, related_patient_id]),
            )
            .order_by(Patient.id)
            .with_for_update()
        )
        existing_stmt = select(PatientRelationship.id).where(
            PatientRelationship.clinic_id == clinic_id,
            or_(
                (PatientRelationship.patient_id == patient_id)
                & (PatientRelationship.related_patient_id == related_patient_id),
                (PatientRelationship.patient_id == related_patient_id)
                & (PatientRelationship.related_patient_id == patient_id),
            ),
        )
        if (await db.execute(existing_stmt)).scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="These two patients are already linked",
            )

        row = PatientRelationship(
            clinic_id=clinic_id,
            patient_id=patient_id,
            related_patient_id=related_patient_id,
            relationship_type=relationship_type,
            notes=data.get("notes"),
        )
        db.add(row)
        return row

    @staticmethod
    async def get_relationship(
        db: AsyncSession, clinic_id: UUID, relationship_id: UUID
    ) -> PatientRelationship | None:
        stmt = select(PatientRelationship).where(
            PatientRelationship.id == relationship_id, PatientRelationship.clinic_id == clinic_id
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def update_relationship(
        db: AsyncSession, row: PatientRelationship, data: dict
    ) -> PatientRelationship:
        # data is already model_dump(exclude_unset=True) from the router,
        # so every key here was explicitly sent by the client -- including
        # an explicit `null`, which is how a client clears an optional
        # field like `notes`. Don't re-filter on `is not None` here: that
        # would silently turn "clear this field" into a no-op.
        for key, value in data.items():
            setattr(row, key, value)
        return row

    @staticmethod
    async def delete_relationship(db: AsyncSession, row: PatientRelationship) -> None:
        await db.delete(row)

    @staticmethod
    async def list_relationships_for_patient(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> list[dict]:
        """Both directions: rows where patient is the subject, and rows
        where patient is the *related* party (flipped to the inverse
        label so the list always reads "this person is my ___")."""
        stmt = select(PatientRelationship).where(
            PatientRelationship.clinic_id == clinic_id,
            or_(
                PatientRelationship.patient_id == patient_id,
                PatientRelationship.related_patient_id == patient_id,
            ),
        )
        rows = (await db.execute(stmt)).scalars().all()
        if not rows:
            return []

        other_ids = {
            (r.related_patient_id if r.patient_id == patient_id else r.patient_id) for r in rows
        }
        others = (
            (
                await db.execute(
                    select(Patient).where(Patient.id.in_(other_ids), Patient.clinic_id == clinic_id)
                )
            )
            .scalars()
            .all()
        )
        names = {p.id: p.full_name for p in others}

        results = []
        for r in rows:
            if r.patient_id == patient_id:
                other_id = r.related_patient_id
                label = r.relationship_type
            else:
                other_id = r.patient_id
                label = INVERSE_RELATIONSHIP_TYPE.get(r.relationship_type, r.relationship_type)
            results.append(
                {
                    "id": r.id,
                    "patient_id": patient_id,
                    "related_patient_id": other_id,
                    "related_patient_name": names.get(other_id, "—"),
                    "relationship_type": label,
                    "notes": r.notes,
                    "created_at": r.created_at,
                }
            )
        return results
