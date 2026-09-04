"""Push subscription registry (WebPush channel, T6)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import PushSubscription


class PushSubscriptionService:
    """CRUD for patient browser subscriptions. All clinic-scoped."""

    @staticmethod
    async def subscribe(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        endpoint: str,
        keys: dict,
        user_agent: str | None = None,
    ) -> PushSubscription:
        """Upsert by (clinic, endpoint): re-subscribes refresh keys in place."""
        from app.modules.patients.models import Patient

        patient = (
            await db.execute(
                select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()
        if patient is None:
            raise LookupError("Patient not found")
        if not endpoint or not isinstance(keys, dict) or "p256dh" not in keys or "auth" not in keys:
            raise ValueError("subscription needs endpoint + keys.p256dh + keys.auth")
        existing = (
            await db.execute(
                select(PushSubscription).where(
                    PushSubscription.clinic_id == clinic_id,
                    PushSubscription.endpoint == endpoint,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.patient_id = patient_id
            existing.keys = keys
            existing.user_agent = user_agent
            await db.flush()
            return existing
        row = PushSubscription(
            clinic_id=clinic_id,
            patient_id=patient_id,
            endpoint=endpoint,
            keys=keys,
            user_agent=user_agent,
        )
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def list_for_patient(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> list[PushSubscription]:
        return list(
            (
                await db.execute(
                    select(PushSubscription)
                    .where(
                        PushSubscription.clinic_id == clinic_id,
                        PushSubscription.patient_id == patient_id,
                    )
                    .order_by(PushSubscription.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    async def unsubscribe(db: AsyncSession, clinic_id: UUID, subscription_id: UUID) -> bool:
        row = (
            await db.execute(
                select(PushSubscription).where(
                    PushSubscription.id == subscription_id,
                    PushSubscription.clinic_id == clinic_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        await db.delete(row)
        await db.flush()
        return True

    @staticmethod
    async def active_for_patient(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> list[PushSubscription]:
        """Subscriptions the adapter fans out to (existence = opted in;
        explicit opt-out lives on the preference row)."""
        return await PushSubscriptionService.list_for_patient(db, clinic_id, patient_id)
