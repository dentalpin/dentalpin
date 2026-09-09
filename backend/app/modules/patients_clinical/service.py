"""Service layer for patients_clinical.

Wraps CRUD for the seven tables plus two derived helpers:
* :meth:`PatientsClinicalService.build_medical_history` — aggregates
  medical_context + allergies + meds + diseases + surgeries into the
  legacy JSONB-shaped response for the form.
* :meth:`PatientsClinicalService.compute_alerts` — the former
  ``Patient.active_alerts`` property, moved here because alerts are
  now derived from normalized rows instead of a blob.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Allergy,
    EmergencyContact,
    LegalGuardian,
    MedicalContext,
    Medication,
    SurgicalHistory,
    SystemicDisease,
)


class PatientsClinicalService:
    """Static service: all methods take ``db`` + ``clinic_id`` explicitly."""

    # --- Medical context (1:1) -----------------------------------------

    @staticmethod
    async def get_medical_context(db: AsyncSession, patient_id: UUID) -> MedicalContext | None:
        result = await db.execute(
            select(MedicalContext).where(MedicalContext.patient_id == patient_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_medical_context(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        data: dict[str, Any],
        user_id: UUID | None,
    ) -> MedicalContext:
        existing = await PatientsClinicalService.get_medical_context(db, patient_id)
        now = datetime.now(UTC)

        if existing is None:
            existing = MedicalContext(
                patient_id=patient_id,
                clinic_id=clinic_id,
                **data,
                last_updated_at=now,
                last_updated_by=user_id,
            )
            db.add(existing)
        else:
            for key, value in data.items():
                setattr(existing, key, value)
            existing.last_updated_at = now
            existing.last_updated_by = user_id

        await db.flush()
        return existing

    # --- Allergy -------------------------------------------------------

    @staticmethod
    async def list_allergies(db: AsyncSession, patient_id: UUID) -> list[Allergy]:
        result = await db.execute(
            select(Allergy)
            .where(Allergy.patient_id == patient_id, Allergy.status == "active")
            .order_by(Allergy.created_at)
        )
        return list(result.scalars())

    @staticmethod
    async def create_allergy(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, data: dict
    ) -> Allergy:
        allergy = Allergy(clinic_id=clinic_id, patient_id=patient_id, **data)
        db.add(allergy)
        await db.flush()
        return allergy

    @staticmethod
    async def get_allergy(db: AsyncSession, allergy_id: UUID) -> Allergy | None:
        result = await db.execute(select(Allergy).where(Allergy.id == allergy_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_allergy(db: AsyncSession, allergy: Allergy, data: dict) -> Allergy:
        for k, v in data.items():
            setattr(allergy, k, v)
        await db.flush()
        return allergy

    @staticmethod
    async def delete_allergy(db: AsyncSession, allergy: Allergy) -> None:
        # Soft-delete: the row stays for history; lists exclude it.
        allergy.status = "archived"
        await db.flush()

    # --- Medication ----------------------------------------------------

    @staticmethod
    async def list_medications(db: AsyncSession, patient_id: UUID) -> list[Medication]:
        result = await db.execute(
            select(Medication)
            .where(Medication.patient_id == patient_id, Medication.status == "active")
            .order_by(Medication.created_at)
        )
        return list(result.scalars())

    @staticmethod
    async def create_medication(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, data: dict
    ) -> Medication:
        med = Medication(clinic_id=clinic_id, patient_id=patient_id, **data)
        db.add(med)
        await db.flush()
        return med

    @staticmethod
    async def get_medication(db: AsyncSession, medication_id: UUID) -> Medication | None:
        result = await db.execute(select(Medication).where(Medication.id == medication_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_medication(db: AsyncSession, med: Medication, data: dict) -> Medication:
        for k, v in data.items():
            setattr(med, k, v)
        await db.flush()
        return med

    @staticmethod
    async def delete_medication(db: AsyncSession, med: Medication) -> None:
        # Soft-delete: the row stays for history; lists exclude it.
        med.status = "archived"
        await db.flush()

    # --- Systemic disease ----------------------------------------------

    @staticmethod
    async def list_systemic_diseases(db: AsyncSession, patient_id: UUID) -> list[SystemicDisease]:
        result = await db.execute(
            select(SystemicDisease)
            .where(SystemicDisease.patient_id == patient_id, SystemicDisease.status == "active")
            .order_by(SystemicDisease.created_at)
        )
        return list(result.scalars())

    @staticmethod
    async def create_systemic_disease(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, data: dict
    ) -> SystemicDisease:
        disease = SystemicDisease(clinic_id=clinic_id, patient_id=patient_id, **data)
        db.add(disease)
        await db.flush()
        return disease

    @staticmethod
    async def get_systemic_disease(db: AsyncSession, disease_id: UUID) -> SystemicDisease | None:
        result = await db.execute(select(SystemicDisease).where(SystemicDisease.id == disease_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_systemic_disease(
        db: AsyncSession, disease: SystemicDisease, data: dict
    ) -> SystemicDisease:
        for k, v in data.items():
            setattr(disease, k, v)
        await db.flush()
        return disease

    @staticmethod
    async def delete_systemic_disease(db: AsyncSession, disease: SystemicDisease) -> None:
        # Soft-delete: the row stays for history; lists exclude it.
        disease.status = "archived"
        await db.flush()

    # --- Surgical history ----------------------------------------------

    @staticmethod
    async def list_surgical_history(db: AsyncSession, patient_id: UUID) -> list[SurgicalHistory]:
        result = await db.execute(
            select(SurgicalHistory)
            .where(SurgicalHistory.patient_id == patient_id, SurgicalHistory.status == "active")
            .order_by(SurgicalHistory.created_at)
        )
        return list(result.scalars())

    @staticmethod
    async def create_surgical_history(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, data: dict
    ) -> SurgicalHistory:
        surgery = SurgicalHistory(clinic_id=clinic_id, patient_id=patient_id, **data)
        db.add(surgery)
        await db.flush()
        return surgery

    @staticmethod
    async def get_surgical_history(db: AsyncSession, surgery_id: UUID) -> SurgicalHistory | None:
        result = await db.execute(select(SurgicalHistory).where(SurgicalHistory.id == surgery_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_surgical_history(
        db: AsyncSession, surgery: SurgicalHistory, data: dict
    ) -> SurgicalHistory:
        for k, v in data.items():
            setattr(surgery, k, v)
        await db.flush()
        return surgery

    @staticmethod
    async def delete_surgical_history(db: AsyncSession, surgery: SurgicalHistory) -> None:
        # Soft-delete: the row stays for history; lists exclude it.
        surgery.status = "archived"
        await db.flush()

    # --- Emergency contact (1:1) ---------------------------------------

    @staticmethod
    async def get_emergency_contact(db: AsyncSession, patient_id: UUID) -> EmergencyContact | None:
        result = await db.execute(
            select(EmergencyContact).where(EmergencyContact.patient_id == patient_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_emergency_contact(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, data: dict
    ) -> EmergencyContact:
        existing = await PatientsClinicalService.get_emergency_contact(db, patient_id)
        if existing is None:
            existing = EmergencyContact(patient_id=patient_id, clinic_id=clinic_id, **data)
            db.add(existing)
        else:
            for k, v in data.items():
                setattr(existing, k, v)
            # Revive: the PK is patient_id, so an archived row is reused.
            existing.status = "active"
        await db.flush()
        return existing

    @staticmethod
    async def delete_emergency_contact(db: AsyncSession, contact: EmergencyContact) -> None:
        # Soft-delete: the row stays for history; upserts revive it.
        contact.status = "archived"
        await db.flush()

    # --- Legal guardian (1:1) ------------------------------------------

    @staticmethod
    async def get_legal_guardian(db: AsyncSession, patient_id: UUID) -> LegalGuardian | None:
        result = await db.execute(
            select(LegalGuardian).where(LegalGuardian.patient_id == patient_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_legal_guardian(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, data: dict
    ) -> LegalGuardian:
        existing = await PatientsClinicalService.get_legal_guardian(db, patient_id)
        if existing is None:
            existing = LegalGuardian(patient_id=patient_id, clinic_id=clinic_id, **data)
            db.add(existing)
        else:
            for k, v in data.items():
                setattr(existing, k, v)
            # Revive: the PK is patient_id, so an archived row is reused.
            existing.status = "active"
        await db.flush()
        return existing

    @staticmethod
    async def delete_legal_guardian(db: AsyncSession, guardian: LegalGuardian) -> None:
        # Soft-delete: the row stays for history; upserts revive it.
        guardian.status = "archived"
        await db.flush()

    # --- Aggregated views ----------------------------------------------

    @staticmethod
    async def build_medical_history(db: AsyncSession, patient_id: UUID) -> dict:
        """Return the legacy JSONB-shaped medical history payload."""
        context = await PatientsClinicalService.get_medical_context(db, patient_id)
        allergies = await PatientsClinicalService.list_allergies(db, patient_id)
        medications = await PatientsClinicalService.list_medications(db, patient_id)
        diseases = await PatientsClinicalService.list_systemic_diseases(db, patient_id)
        surgeries = await PatientsClinicalService.list_surgical_history(db, patient_id)

        ctx: dict[str, Any] = {}
        if context is not None:
            ctx = {
                "is_pregnant": context.is_pregnant,
                "pregnancy_week": context.pregnancy_week,
                "is_lactating": context.is_lactating,
                "is_on_anticoagulants": context.is_on_anticoagulants,
                "anticoagulant_medication": context.anticoagulant_medication,
                "inr_value": context.inr_value,
                "last_inr_date": context.last_inr_date,
                "is_smoker": context.is_smoker,
                "smoking_frequency": context.smoking_frequency,
                "alcohol_consumption": context.alcohol_consumption,
                "bruxism": context.bruxism,
                "adverse_reactions_to_anesthesia": context.adverse_reactions_to_anesthesia,
                "anesthesia_reaction_details": context.anesthesia_reaction_details,
                "last_updated_at": context.last_updated_at,
                "last_updated_by": context.last_updated_by,
            }
        return {
            "allergies": allergies,
            "medications": medications,
            "systemic_diseases": diseases,
            "surgical_history": surgeries,
            **ctx,
        }

    @staticmethod
    async def compute_alerts(db: AsyncSession, patient_id: UUID) -> list[dict]:
        """Compute active alerts from normalized clinical rows."""
        context = await PatientsClinicalService.get_medical_context(db, patient_id)
        allergies = await PatientsClinicalService.list_allergies(db, patient_id)
        diseases = await PatientsClinicalService.list_systemic_diseases(db, patient_id)

        alerts: list[dict] = []

        for allergy in allergies:
            if allergy.severity in ("high", "critical"):
                alerts.append(
                    {
                        "type": "allergy",
                        "severity": allergy.severity,
                        "title": f"Alergia: {allergy.name}",
                        "details": allergy.reaction,
                    }
                )

        if context is None:
            return alerts

        if context.is_pregnant:
            week = context.pregnancy_week
            alerts.append(
                {
                    "type": "pregnancy",
                    "severity": "high",
                    "title": f"Embarazada{f' ({week} semanas)' if week else ''}",
                    "details": None,
                }
            )

        if context.is_lactating:
            alerts.append(
                {
                    "type": "lactating",
                    "severity": "medium",
                    "title": "En período de lactancia",
                    "details": None,
                }
            )

        if context.is_on_anticoagulants:
            med = context.anticoagulant_medication
            inr = context.inr_value
            alerts.append(
                {
                    "type": "anticoagulant",
                    "severity": "critical",
                    "title": f"Anticoagulantes{f': {med}' if med else ''}",
                    "details": f"INR: {inr}" if inr else None,
                }
            )

        if context.adverse_reactions_to_anesthesia:
            alerts.append(
                {
                    "type": "anesthesia_reaction",
                    "severity": "critical",
                    "title": "Reacción adversa a anestesia",
                    "details": context.anesthesia_reaction_details,
                }
            )

        for disease in diseases:
            if disease.is_critical:
                alerts.append(
                    {
                        "type": "systemic_disease",
                        "severity": "high",
                        "title": disease.name,
                        "details": disease.notes,
                    }
                )

        return alerts

    # --- Bulk medical-history upsert -----------------------------------

    @staticmethod
    async def replace_medical_history(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        payload: dict,
        user_id: UUID | None,
    ) -> None:
        """Replace allergies/medications/diseases/surgeries and context atomically.

        The frontend form submits the whole block, mirroring the old
        JSONB shape. Superseded rows are archived (never hard-deleted, so
        the clinical history survives every save) and the submitted set is
        inserted fresh, so the result stays deterministic.
        """
        for table_cls, key in (
            (Allergy, "allergies"),
            (Medication, "medications"),
            (SystemicDisease, "systemic_diseases"),
            (SurgicalHistory, "surgical_history"),
        ):
            existing = await db.execute(select(table_cls).where(table_cls.patient_id == patient_id))
            for row in existing.scalars():
                row.status = "archived"

        for row in payload.get("allergies", []):
            db.add(Allergy(clinic_id=clinic_id, patient_id=patient_id, **row))
        for row in payload.get("medications", []):
            db.add(Medication(clinic_id=clinic_id, patient_id=patient_id, **row))
        for row in payload.get("systemic_diseases", []):
            db.add(SystemicDisease(clinic_id=clinic_id, patient_id=patient_id, **row))
        for row in payload.get("surgical_history", []):
            db.add(SurgicalHistory(clinic_id=clinic_id, patient_id=patient_id, **row))

        context_fields = {
            k: payload[k]
            for k in (
                "is_pregnant",
                "pregnancy_week",
                "is_lactating",
                "is_on_anticoagulants",
                "anticoagulant_medication",
                "inr_value",
                "last_inr_date",
                "is_smoker",
                "smoking_frequency",
                "alcohol_consumption",
                "bruxism",
                "adverse_reactions_to_anesthesia",
                "anesthesia_reaction_details",
            )
            if k in payload
        }
        await PatientsClinicalService.upsert_medical_context(
            db, clinic_id, patient_id, context_fields, user_id
        )
        await db.flush()
