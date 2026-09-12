"""Push subscription registry (WebPush channel, T6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import PushSubscribeToken, PushSubscription


def _require_https_endpoint(endpoint: str | None) -> None:
    # The worker POSTs wherever it is pointed — refuse non-HTTPS so a
    # staff typo (or worse) cannot turn the dispatcher into an
    # intranet HTTP client.
    if not endpoint or not endpoint.startswith("https://"):
        raise ValueError("subscription endpoint must be an https:// URL")


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
        _require_https_endpoint(endpoint)
        if not isinstance(keys, dict) or "p256dh" not in keys or "auth" not in keys:
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


class PushSubscribeTokenService:
    """Single-use patient subscribe tokens (T6 patient flow).

    Staff mints a token for a patient (``POST /push/subscribe-tokens``);
    the patient's browser redeems it with its subscription
    (``POST /push/patient-subscribe``). The token is the auth — random
    UUID, 24 h expiry, single use — same shape as budget public links.
    """

    TOKEN_TTL_HOURS = 24

    @staticmethod
    async def mint(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> PushSubscribeToken:
        from app.modules.patients.models import Patient

        patient = (
            await db.execute(
                select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()
        if patient is None:
            raise LookupError("Patient not found")
        row = PushSubscribeToken(
            clinic_id=clinic_id,
            patient_id=patient_id,
            token=uuid4(),
            expires_at=datetime.now(UTC)
            + timedelta(hours=PushSubscribeTokenService.TOKEN_TTL_HOURS),
        )
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def redeem(
        db: AsyncSession,
        token: UUID,
        endpoint: str,
        keys: dict,
        user_agent: str | None = None,
    ) -> PushSubscription:
        from sqlalchemy import update

        from app.modules.patients.models import Patient

        _require_https_endpoint(endpoint)
        if not isinstance(keys, dict) or "p256dh" not in keys or "auth" not in keys:
            raise ValueError("subscription needs keys.p256dh + keys.auth")
        # Resolve first (read-only): a malformed subscription must not
        # burn the single-use token.
        row = (
            await db.execute(select(PushSubscribeToken).where(PushSubscribeToken.token == token))
        ).scalar_one_or_none()
        if row is None or row.used_at is not None or row.expires_at < datetime.now(UTC):
            raise LookupError("Invalid or expired subscribe token")
        patient = (
            await db.execute(
                select(Patient).where(
                    Patient.id == row.patient_id, Patient.clinic_id == row.clinic_id
                )
            )
        ).scalar_one_or_none()
        if patient is None:
            raise LookupError("Invalid or expired subscribe token")
        # Atomic single-use: exactly one concurrent redeem wins.
        consumed = (
            await db.execute(
                update(PushSubscribeToken)
                .where(
                    PushSubscribeToken.id == row.id,
                    PushSubscribeToken.used_at.is_(None),
                )
                .values(used_at=datetime.now(UTC))
                .returning(PushSubscribeToken.id)
            )
        ).scalar_one_or_none()
        if consumed is None:
            raise LookupError("Invalid or expired subscribe token")
        subscription = await PushSubscriptionService.subscribe(
            db, row.clinic_id, row.patient_id, endpoint, keys, user_agent=user_agent
        )
        await db.flush()
        return subscription

    @staticmethod
    async def validate(db: AsyncSession, token: UUID) -> dict | None:
        """Token validity + consent-screen data, without consuming."""
        from app.core.auth.models import Clinic

        row = (
            await db.execute(select(PushSubscribeToken).where(PushSubscribeToken.token == token))
        ).scalar_one_or_none()
        if row is None or row.used_at is not None or row.expires_at < datetime.now(UTC):
            return None
        clinic = (
            await db.execute(select(Clinic.name).where(Clinic.id == row.clinic_id))
        ).scalar_one_or_none()
        return {
            "clinic_name": clinic or "",
            "expires_at": row.expires_at,
        }
