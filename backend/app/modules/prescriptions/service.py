"""PrescriptionService — drafts, issue/cancel lifecycle, templates, warnings.

Issued rows freeze: corrections are cancel + reissue. The prescriber
snapshot (name/license/signature) is taken at issue time so later
profile edits never rewrite a legal artifact.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType, event_bus
from app.modules.patients.models import Patient
from app.modules.patients.service import PatientService

from .hooks import resolve_hook_for_clinic
from .models import (
    PrescriberProfile,
    Prescription,
    PrescriptionItem,
    PrescriptionTemplate,
)

TERMINAL = ("issued", "cancelled")


class PrescriptionService:
    @staticmethod
    async def _ensure_patient(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> Patient:
        patient = await PatientService.get_patient(db, clinic_id, patient_id)
        if patient is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Patient not found")
        return patient

    @staticmethod
    async def _get(db: AsyncSession, clinic_id: UUID, prescription_id: UUID):
        stmt = select(Prescription).where(
            Prescription.id == prescription_id, Prescription.clinic_id == clinic_id
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Prescription not found")
        return row

    @staticmethod
    async def _items(db: AsyncSession, clinic_id: UUID, prescription_id: UUID):
        stmt = (
            select(PrescriptionItem)
            .where(
                PrescriptionItem.prescription_id == prescription_id,
                PrescriptionItem.clinic_id == clinic_id,
            )
            .order_by(PrescriptionItem.sort_order, PrescriptionItem.created_at)
        )
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def _require_draft(row: Prescription) -> None:
        if row.status != "draft":
            raise HTTPException(
                http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Only draft prescriptions can be changed (status is {row.status})",
            )

    # --- Drafts ---------------------------------------------------------

    @staticmethod
    async def list_for_patient(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> list[Prescription]:
        await PrescriptionService._ensure_patient(db, clinic_id, patient_id)
        stmt = (
            select(Prescription)
            .where(
                Prescription.clinic_id == clinic_id,
                Prescription.patient_id == patient_id,
            )
            .order_by(Prescription.created_at.desc())
        )
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def create_draft(
        db: AsyncSession,
        clinic_id: UUID,
        prescriber_id: UUID,
        patient_id: UUID,
        notes: str | None,
        locale: str,
        items: list[dict],
    ) -> Prescription:
        await PrescriptionService._ensure_patient(db, clinic_id, patient_id)
        row = Prescription(
            clinic_id=clinic_id,
            patient_id=patient_id,
            prescriber_id=prescriber_id,
            notes=notes,
            locale=locale or "es",
        )
        db.add(row)
        await db.flush()
        for position, item in enumerate(items):
            db.add(
                PrescriptionItem(
                    clinic_id=clinic_id,
                    prescription_id=row.id,
                    sort_order=item.pop("sort_order", position),
                    **item,
                )
            )
        await db.flush()
        return row

    @staticmethod
    async def update_draft(
        db: AsyncSession, clinic_id: UUID, prescription_id: UUID, data: dict
    ) -> Prescription:
        row = await PrescriptionService._get(db, clinic_id, prescription_id)
        await PrescriptionService._require_draft(row)
        if "notes" in data:
            row.notes = data["notes"]
        if "locale" in data and data["locale"] is not None:
            row.locale = data["locale"]
        if "items" in data and data["items"] is not None:
            await db.execute(
                delete(PrescriptionItem).where(
                    PrescriptionItem.prescription_id == row.id,
                    PrescriptionItem.clinic_id == clinic_id,
                )
            )
            for position, item in enumerate(data["items"]):
                db.add(
                    PrescriptionItem(
                        clinic_id=clinic_id,
                        prescription_id=row.id,
                        sort_order=item.pop("sort_order", position),
                        **item,
                    )
                )
        await db.flush()
        return row

    # --- Issue / cancel ---------------------------------------------------

    @staticmethod
    async def issue(
        db: AsyncSession, clinic_id: UUID, prescription_id: UUID, prescriber_id: UUID
    ) -> Prescription:
        from app.core.auth.models import User

        row = await PrescriptionService._get(db, clinic_id, prescription_id)
        await PrescriptionService._require_draft(row)
        items = await PrescriptionService._items(db, clinic_id, row.id)
        if not items:
            raise HTTPException(
                http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Cannot issue an empty prescription",
            )
        hook = await resolve_hook_for_clinic(db, clinic_id)
        prescriber = await db.get(User, prescriber_id)
        profile = (
            await db.execute(
                select(PrescriberProfile).where(
                    PrescriberProfile.clinic_id == clinic_id,
                    PrescriberProfile.user_id == prescriber_id,
                )
            )
        ).scalar_one_or_none()
        if hook is not None:
            ok, error = await hook.validate_before_issue(row, db)
            if not ok:
                raise HTTPException(
                    http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=error or "Country compliance check failed",
                )
            missing = [
                field for field in hook.get_required_fields() if not getattr(profile, field, None)
            ]
            if missing:
                raise HTTPException(
                    http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Missing prescriber fields: {', '.join(missing)}",
                )
        row.prescriber_id = prescriber_id
        row.prescriber_name = (
            f"{prescriber.first_name} {prescriber.last_name}" if prescriber else None
        )
        row.license_number = profile.license_number if profile else None
        row.signature_document_id = profile.signature_document_id if profile else None
        row.status = "issued"
        row.issued_at = datetime.now(UTC)
        if hook is not None:
            row.compliance_data = {
                **row.compliance_data,
                hook.country_code: await hook.on_prescription_issued(row, db),
            }
        await db.flush()
        await event_bus.publish(
            EventType.PRESCRIPTION_ISSUED,
            {
                "prescription_id": str(row.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(row.patient_id),
            },
            db=db,
        )
        return row

    @staticmethod
    async def cancel(db: AsyncSession, clinic_id: UUID, prescription_id: UUID) -> Prescription:
        row = await PrescriptionService._get(db, clinic_id, prescription_id)
        if row.status == "cancelled":
            raise HTTPException(http_status.HTTP_409_CONFLICT, "Prescription is already cancelled")
        row.status = "cancelled"
        await db.flush()
        await event_bus.publish(
            EventType.PRESCRIPTION_CANCELLED,
            {
                "prescription_id": str(row.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(row.patient_id),
            },
            db=db,
        )
        return row

    # --- Templates --------------------------------------------------------

    @staticmethod
    async def list_templates(db: AsyncSession, clinic_id: UUID):
        stmt = (
            select(PrescriptionTemplate)
            .where(PrescriptionTemplate.clinic_id == clinic_id)
            .order_by(PrescriptionTemplate.name)
        )
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def create_template(
        db: AsyncSession, clinic_id: UUID, name: str, items: list[dict]
    ) -> PrescriptionTemplate:
        row = PrescriptionTemplate(clinic_id=clinic_id, name=name, items=items)
        db.add(row)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="A template with this name already exists",
            ) from exc
        return row

    @staticmethod
    async def update_template(
        db: AsyncSession, clinic_id: UUID, template_id: UUID, data: dict
    ) -> PrescriptionTemplate:
        stmt = select(PrescriptionTemplate).where(
            PrescriptionTemplate.id == template_id,
            PrescriptionTemplate.clinic_id == clinic_id,
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Template not found")
        for key, value in data.items():
            setattr(row, key, value)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="A template with this name already exists",
            ) from exc
        return row

    @staticmethod
    async def delete_template(db: AsyncSession, clinic_id: UUID, template_id: UUID) -> None:
        stmt = select(PrescriptionTemplate).where(
            PrescriptionTemplate.id == template_id,
            PrescriptionTemplate.clinic_id == clinic_id,
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Template not found")
        await db.delete(row)
        await db.flush()

    # --- Prescriber profile -----------------------------------------------

    @staticmethod
    async def get_prescriber_profile(
        db: AsyncSession, clinic_id: UUID, user_id: UUID
    ) -> PrescriberProfile | None:
        stmt = select(PrescriberProfile).where(
            PrescriberProfile.clinic_id == clinic_id,
            PrescriberProfile.user_id == user_id,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def upsert_prescriber_profile(
        db: AsyncSession, clinic_id: UUID, user_id: UUID, data: dict
    ) -> PrescriberProfile:
        row = await PrescriptionService.get_prescriber_profile(db, clinic_id, user_id)
        if row is None:
            row = PrescriberProfile(clinic_id=clinic_id, user_id=user_id, **data)
            db.add(row)
        else:
            for key, value in data.items():
                setattr(row, key, value)
        await db.flush()
        return row

    # --- Safety warnings (soft integrations, no depends) --------------------

    @staticmethod
    async def prescribe_warnings(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> dict[str, list[str]]:
        """Allergy + interaction flags for the create-form banner. Never
        blocks issuing; every source is optional (module may be absent)."""
        await PrescriptionService._ensure_patient(db, clinic_id, patient_id)
        allergies: list[str] = []
        try:
            from app.modules.patients_clinical.models import Allergy

            rows = (
                (
                    await db.execute(
                        select(Allergy.name).where(
                            Allergy.patient_id == patient_id,
                            Allergy.clinic_id == clinic_id,
                            Allergy.status == "active",
                        )
                    )
                )
                .scalars()
                .all()
            )
            allergies = sorted({name for name in rows if name})
        except ImportError:
            pass
        flags: list[str] = []
        try:
            from app.core.plugins.registry import module_registry

            if module_registry.is_active("medical_reference"):
                from app.modules.medical_reference.service import (
                    MedicalReferenceService,
                )

                service_flags = await MedicalReferenceService.get_patient_flags(
                    db, clinic_id, patient_id
                )
                flags = [PrescriptionService._format_flag(f) for f in (service_flags or [])]
        except (ImportError, AttributeError):
            pass
        return {"allergies": allergies, "interaction_flags": flags}

    @staticmethod
    def _format_flag(flag) -> str:
        """Interaction flags read as text, never as a Pydantic repr."""
        return f"{' + '.join(flag.involved)}: {flag.risk_note}"
