"""Business logic for the gdpr module.

All queries are hard-filtered by ``clinic_id`` for multi-tenancy — a query
keyed only by id is a security bug. The GDPR events are published on the
bus for cross-module reactions (patient_timeline, notifications, etc.).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType, event_bus

from .models import DataBreach, ErasureAuditLog, GdprRequest, PatientConsent, RetentionPolicy
from .schemas import (
    ConsentCreate,
    DataBreachCreate,
    DataBreachUpdate,
    ErasureResult,
    GdprRequestCreate,
    GdprRequestUpdate,
    RetentionPolicyCreate,
    RetentionPolicyUpdate,
)


class SlaCalculator:
    """Art. 12(3) — answer within one month (30 days)."""

    @staticmethod
    def deadline_from(received_at: datetime) -> datetime:
        return received_at + timedelta(days=30)


class GdprService:
    @staticmethod
    async def create_request(
        db: AsyncSession, clinic_id: UUID, payload: GdprRequestCreate
    ) -> GdprRequest:
        received_at = datetime.now(UTC)
        row = GdprRequest(
            clinic_id=clinic_id,
            patient_id=payload.patient_id,
            requester_name=payload.requester_name,
            requester_email=payload.requester_email,
            request_type=payload.request_type,
            status="received",
            received_at=received_at,
            deadline_at=SlaCalculator.deadline_from(received_at),
            notes=payload.notes,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        await event_bus.publish(
            EventType.GDPR_REQUEST_CREATED,
            {
                "clinic_id": str(clinic_id),
                "request_id": str(row.id),
                "patient_id": str(payload.patient_id) if payload.patient_id else None,
                "request_type": payload.request_type,
            },
            db=db,
        )
        return row

    @staticmethod
    async def get_request(
        db: AsyncSession, clinic_id: UUID, request_id: UUID
    ) -> GdprRequest | None:
        return (
            await db.execute(
                select(GdprRequest).where(
                    GdprRequest.id == request_id, GdprRequest.clinic_id == clinic_id
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_requests(
        db: AsyncSession,
        clinic_id: UUID,
        status: str | None = None,
        request_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[GdprRequest], int]:
        stmt = select(GdprRequest).where(GdprRequest.clinic_id == clinic_id)
        if status:
            stmt = stmt.where(GdprRequest.status == status)
        if request_type:
            stmt = stmt.where(GdprRequest.request_type == request_type)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = (
            stmt.order_by(GdprRequest.received_at.desc())
            .offset((max(page, 1) - 1) * min(max(page_size, 1), 100))
            .limit(min(max(page_size, 1), 100))
        )
        return list((await db.execute(stmt)).scalars()), total

    @staticmethod
    async def update_request(
        db: AsyncSession,
        row: GdprRequest,
        payload: GdprRequestUpdate,
        resolved_by: UUID | None = None,
    ) -> GdprRequest:
        changes = payload.model_dump(exclude_unset=True)
        old_status = row.status
        for field, value in changes.items():
            setattr(row, field, value)
        if "status" in changes and changes["status"] in ("completed", "rejected"):
            row.resolved_at = datetime.now(UTC)
        elif "status" in changes and changes["status"] == "received":
            row.resolved_at = None
        await db.commit()
        await db.refresh(row)
        if "status" in changes and changes["status"] != old_status:
            await event_bus.publish(
                EventType.GDPR_REQUEST_STATUS_CHANGED,
                {
                    "clinic_id": str(row.clinic_id),
                    "request_id": str(row.id),
                    "patient_id": str(row.patient_id) if row.patient_id else None,
                    "from_status": old_status,
                    "to_status": row.status,
                    "changed_by": str(resolved_by) if resolved_by else None,
                },
                db=db,
            )
        return row


class ConsentService:
    @staticmethod
    async def grant_or_withdraw(
        db: AsyncSession, clinic_id: UUID, payload: ConsentCreate
    ) -> PatientConsent:
        """Record a consent grant/withdrawal (Art. 7-8) as an immutable event.

        Every call APPENDS a row — grant → withdraw → grant leaves three
        rows, so the withdrawal is never lost. The latest row per
        (patient, purpose) (``created_at`` desc) is the current state;
        ``list_consents`` already orders that way.
        """
        now = datetime.now(UTC)
        row = PatientConsent(
            clinic_id=clinic_id,
            patient_id=payload.patient_id,
            purpose=payload.purpose,
            granted=payload.granted,
            provided_text=payload.provided_text,
            granted_at=now if payload.granted else None,
            withdrawn_at=None if payload.granted else now,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        if payload.granted:
            await event_bus.publish(
                EventType.GDPR_CONSENT_GRANTED,
                {
                    "clinic_id": str(clinic_id),
                    "consent_id": str(row.id),
                    "patient_id": str(payload.patient_id),
                    "purpose": payload.purpose,
                },
                db=db,
            )
        else:
            await event_bus.publish(
                EventType.GDPR_CONSENT_WITHDRAWN,
                {
                    "clinic_id": str(clinic_id),
                    "consent_id": str(row.id),
                    "patient_id": str(payload.patient_id),
                    "purpose": payload.purpose,
                },
                db=db,
            )
        return row

    @staticmethod
    async def list_consents(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PatientConsent], int]:
        stmt = select(PatientConsent).where(PatientConsent.clinic_id == clinic_id)
        if patient_id:
            stmt = stmt.where(PatientConsent.patient_id == patient_id)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = (
            stmt.order_by(PatientConsent.created_at.desc())
            .offset((max(page, 1) - 1) * min(max(page_size, 1), 100))
            .limit(min(max(page_size, 1), 100))
        )
        return list((await db.execute(stmt)).scalars()), total


class RetentionService:
    @staticmethod
    async def list_active(db: AsyncSession, clinic_id: UUID) -> list[RetentionPolicy]:
        return list(
            (
                await db.execute(
                    select(RetentionPolicy).where(
                        RetentionPolicy.clinic_id == clinic_id, RetentionPolicy.is_active.is_(True)
                    )
                )
            ).scalars()
        )

    @staticmethod
    async def create(
        db: AsyncSession, clinic_id: UUID, payload: RetentionPolicyCreate
    ) -> RetentionPolicy:
        row = RetentionPolicy(
            clinic_id=clinic_id,
            data_category=payload.data_category,
            retention_years=payload.retention_years,
            legal_hold_until=payload.legal_hold_until,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def update(
        db: AsyncSession, row: RetentionPolicy, payload: RetentionPolicyUpdate
    ) -> RetentionPolicy:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def delete(db: AsyncSession, clinic_id: UUID, policy_id: UUID) -> bool:
        result = await db.execute(
            delete(RetentionPolicy).where(
                RetentionPolicy.id == policy_id, RetentionPolicy.clinic_id == clinic_id
            )
        )
        await db.commit()
        return (result.rowcount or 0) > 0

    @staticmethod
    async def get_active_by_id(
        db: AsyncSession, clinic_id: UUID, policy_id: UUID
    ) -> RetentionPolicy | None:
        return (
            await db.execute(
                select(RetentionPolicy).where(
                    RetentionPolicy.id == policy_id,
                    RetentionPolicy.clinic_id == clinic_id,
                    RetentionPolicy.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()


class ErasureService:
    """Partial erasure (Art. 17). Identity-critical fields are only blanked
    once every active retention policy for the data category no longer holds;
    the patient row itself is never hard-deleted (L7 governance)."""

    # Closed vocabulary (mirrors ``schemas.ErasureCategory``): the only data
    # categories that map onto patient PII fields. A category without a
    # mapping here can never be reported as erased.
    category_to_fields: dict[str, list[str]] = {
        "email": ["email", "billing_email"],
        "phone": ["phone"],
        "identity": ["national_id"],
    }

    @staticmethod
    async def erasure_eligible(
        db: AsyncSession,
        clinic_id: UUID,
        categories: list[str],
        anchor_date: date,
    ) -> tuple[list[str], list[str]]:
        """Return (erasable, retained) categories given active retention policies.

        A category is erasable only when it has an active policy whose
        legal hold has expired AND whose retention window has passed:
        ``retention_years == 0`` means no age hold, otherwise the window
        runs ``retention_years`` years from ``anchor_date`` (the patient's
        ``updated_at`` — the minimum-honest anchor until a last-visit
        provider exists). Categories with no policy, or with no field
        mapping in ``category_to_fields``, are retained.
        """
        today = datetime.now(UTC).date()
        policies = await RetentionService.list_active(db, clinic_id)
        by_category: dict[str, RetentionPolicy] = {p.data_category: p for p in policies}

        erasable: list[str] = []
        retained: list[str] = []
        for cat in categories:
            policy = by_category.get(cat)
            if policy is None or cat not in ErasureService.category_to_fields:
                # No policy configured, or nothing to blank → retain.
                retained.append(cat)
                continue
            legal_expired = policy.legal_hold_until is None or policy.legal_hold_until < today
            if (policy.retention_years or 0) == 0:
                age_expired = True
            else:
                age_expired = (today - anchor_date).days >= policy.retention_years * 365
            if legal_expired and age_expired:
                erasable.append(cat)
            else:
                retained.append(cat)
        return erasable, retained

    @staticmethod
    async def execute(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        categories: list[str],
        rationale: str | None,
        request_id: UUID | None = None,
        executed_by: UUID | None = None,
    ) -> ErasureResult | None:
        from app.modules.patients.models import Patient

        # Patient first: unknown or other-clinic ids are None upstream
        # (404 in the router, error in the tool). The audit table FKs
        # patient_id, so nothing is written before this check.
        patient = (
            await db.execute(
                select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()
        if patient is None:
            return None
        anchor = (patient.updated_at or datetime.now(UTC)).date()
        erasable, retained = await ErasureService.erasure_eligible(
            db, clinic_id, categories, anchor
        )
        # Blank only the selected patient's PII (still scoped by clinic).
        fields_blanked: dict[str, str] = {}
        if erasable:
            seen: set[str] = set()
            for cat in erasable:
                for field in ErasureService.category_to_fields.get(cat, []):
                    if field in seen:
                        continue
                    seen.add(field)
                    setattr(patient, field, None)
                    fields_blanked[field] = cat
            await db.flush()

        log = ErasureAuditLog(
            clinic_id=clinic_id,
            patient_id=patient_id,
            request_id=request_id,
            erased_categories=erasable,
            fields_blanked=fields_blanked or None,
            rationale=rationale,
            executed_by=executed_by,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

        await event_bus.publish(
            EventType.GDPR_ERASURE_EXECUTED,
            {
                "clinic_id": str(clinic_id),
                "patient_id": str(patient_id),
                "request_id": str(request_id) if request_id else None,
                "erased_categories": erasable,
                "retained_categories": retained,
            },
            db=db,
        )
        return ErasureResult(
            patient_id=patient_id,
            erased_categories=erasable,
            audit_log_id=log.id,
            retained_categories=retained,
        )

    @staticmethod
    async def list_audit(
        db: AsyncSession, clinic_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ErasureAuditLog], int]:
        stmt = select(ErasureAuditLog).where(ErasureAuditLog.clinic_id == clinic_id)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = (
            stmt.order_by(ErasureAuditLog.executed_at.desc())
            .offset((max(page, 1) - 1) * min(max(page_size, 1), 100))
            .limit(min(max(page_size, 1), 100))
        )
        return list((await db.execute(stmt)).scalars()), total


class DataBreachService:
    @staticmethod
    async def create(db: AsyncSession, clinic_id: UUID, payload: DataBreachCreate) -> DataBreach:
        row = DataBreach(
            clinic_id=clinic_id,
            occurred_at=payload.occurred_at or datetime.now(UTC),
            description=payload.description,
            data_involved=payload.data_involved,
            affected_people=payload.affected_people,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        await event_bus.publish(
            EventType.GDPR_BREACH_REPORTED,
            {
                "clinic_id": str(clinic_id),
                "breach_id": str(row.id),
                "affected_people": payload.affected_people,
            },
            db=db,
        )
        return row

    @staticmethod
    async def get(db: AsyncSession, clinic_id: UUID, breach_id: UUID) -> DataBreach | None:
        return (
            await db.execute(
                select(DataBreach).where(
                    DataBreach.id == breach_id, DataBreach.clinic_id == clinic_id
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list(
        db: AsyncSession,
        clinic_id: UUID,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DataBreach], int]:
        stmt = select(DataBreach).where(DataBreach.clinic_id == clinic_id)
        if status:
            stmt = stmt.where(DataBreach.status == status)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = (
            stmt.order_by(DataBreach.occurred_at.desc())
            .offset((max(page, 1) - 1) * min(max(page_size, 1), 100))
            .limit(min(max(page_size, 1), 100))
        )
        return list((await db.execute(stmt)).scalars()), total

    @staticmethod
    async def update(db: AsyncSession, row: DataBreach, payload: DataBreachUpdate) -> DataBreach:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        if payload.status == "reported" and not row.notified_authority_at:
            row.notified_authority_at = datetime.now(UTC)
        if row.status == "reported":
            row.reported = True
        await db.commit()
        await db.refresh(row)
        return row


class ExportService:
    """Portability (Art. 20) — returns the patient's personal data in a
    machine-readable snapshot. Identity values are returned as-is so the
    output is genuinely portable."""

    @staticmethod
    async def export(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> dict:
        from app.modules.patients.models import Patient

        patient = (
            await db.execute(
                select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()
        if not patient:
            return {}

        consents_stmt = select(PatientConsent).where(
            PatientConsent.clinic_id == clinic_id, PatientConsent.patient_id == patient_id
        )
        consents = list((await db.execute(consents_stmt)).scalars())
        requests_stmt = select(GdprRequest).where(
            GdprRequest.clinic_id == clinic_id, GdprRequest.patient_id == patient_id
        )
        requests = list((await db.execute(requests_stmt)).scalars())

        return {
            "identity": {
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "phone": patient.phone,
                "email": patient.email,
                "date_of_birth": patient.date_of_birth.isoformat()
                if patient.date_of_birth
                else None,
                "gender": patient.gender,
                "national_id": patient.national_id,
                "address": patient.address,
            },
            "consents": [
                {
                    "purpose": c.purpose,
                    "granted": c.granted,
                    "granted_at": c.granted_at.isoformat() if c.granted_at else None,
                    "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None,
                }
                for c in consents
            ],
            "requests": [
                {
                    "request_type": r.request_type,
                    "status": r.status,
                    "received_at": r.received_at.isoformat(),
                    "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                }
                for r in requests
            ],
        }
