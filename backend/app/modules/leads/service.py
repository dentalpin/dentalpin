"""Service layer for the leads module.

Static-method classes; routers stay thin. Multi-tenancy is mandatory:
every query filters by clinic_id — including the settings row, the
intake-key lookups and the agent tools.

The one rule that must not drift: a lead row is inserted **only** by
LeadService.create_lead, and the only caller allowed to reach it is
LeadIntakeService.route. Both entry points (the public form and
POST /api/v1/leads/) go through route(), so a matched enquiry can never
produce the duplicate lead this module exists to prevent.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.list_query import parse_sort
from app.modules.patients.models import Patient
from app.modules.patients.service import PatientService

from .matching import find_matching_patients
from .models import LEAD_STATUSES, Lead, LeadIntakeKey, LeadSettings, canonical_days
from .recall_routing import route_matched_enquiry

logger = logging.getLogger(__name__)

_SORT_ALLOW = {
    "created_at": Lead.created_at,
    "full_name": Lead.full_name,
    "status": Lead.status,
}
_SORT_DEFAULT = "created_at:desc"

#: Prefix of every intake key; also the first characters of key_prefix.
KEY_PREFIX = "lk_"


def _parse_statuses(status: str | list[str] | None) -> list[str]:
    """Accept a comma-separated status list or a repeated param, and validate."""
    if not status:
        return []
    raw = status if isinstance(status, list) else status.split(",")
    values = [value.strip() for value in raw if value and value.strip()]
    invalid = [value for value in values if value not in LEAD_STATUSES]
    if invalid:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status {invalid}. Allowed: {list(LEAD_STATUSES)}",
        )
    return values


class LeadService:
    """CRUD for leads, plus conversion into a patient."""

    @staticmethod
    async def list_leads(
        db: AsyncSession,
        clinic_id: UUID,
        *,
        status: str | list[str] | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str | None = None,
    ) -> tuple[list[Lead], int]:
        """Paginated list. No status param means *all* statuses.

        discarded is deliberately not excluded by default: hidden rows with
        no visible filter is exactly the confusion a lead queue cannot
        afford.
        """
        conditions: list[Any] = [Lead.clinic_id == clinic_id]

        statuses = _parse_statuses(status)
        if statuses:
            conditions.append(Lead.status.in_(statuses))

        term = (search or "").strip()
        if term:
            pattern = f"%{term}%"
            conditions.append(
                or_(
                    Lead.full_name.ilike(pattern),
                    Lead.phone.ilike(pattern),
                    Lead.email.ilike(pattern),
                )
            )

        total = int(
            (await db.execute(select(func.count(Lead.id)).where(*conditions))).scalar_one() or 0
        )

        stmt = (
            select(Lead)
            .where(*conditions)
            .order_by(parse_sort(sort, _SORT_ALLOW, _SORT_DEFAULT))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list((await db.execute(stmt)).scalars().all())
        return items, total

    @staticmethod
    async def get_lead(db: AsyncSession, clinic_id: UUID, lead_id: UUID) -> Lead | None:
        """id **and** clinic_id in the same WHERE — never id-only."""
        stmt = select(Lead).where(Lead.id == lead_id, Lead.clinic_id == clinic_id)
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def create_lead(db: AsyncSession, clinic_id: UUID, data: dict) -> Lead:
        """The only place a lead row is inserted.

        Only LeadIntakeService.route may call this. website is an
        intake-only field — dropped here so the honeypot can never be
        persisted by a future caller.
        """
        payload = dict(data)
        payload.pop("website", None)
        # Canonical mon..sun order, no duplicates, whatever the caller sent.
        payload["availability_days"] = canonical_days(payload.get("availability_days"))
        row = Lead(
            clinic_id=clinic_id,
            status=payload.pop("status", None) or "new",
            **payload,
        )
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def update_lead(db: AsyncSession, lead: Lead, data: dict) -> Lead:
        """Callers pass model_dump(exclude_unset=True) — PATCH semantics."""
        if "availability_days" in data:
            data["availability_days"] = canonical_days(data["availability_days"])
        for key, value in data.items():
            setattr(lead, key, value)
        await db.flush()
        return lead

    @staticmethod
    async def convert(
        db: AsyncSession, clinic_id: UUID, lead: Lead, patient_data: dict
    ) -> tuple[Lead, Patient]:
        """Create the patient and link the lead, in one transaction.

        Patient creation goes through PatientService.create_patient — it
        flushes and publishes patient.created with db=db, so the timeline,
        notifications and integrations webhooks fire exactly as for a
        normal creation. Never re-implement it.
        """
        if lead.status == "converted":
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Lead is already converted",
            )

        patient = await PatientService.create_patient(db, clinic_id, patient_data)

        lead.patient_id = patient.id
        lead.status = "converted"
        lead.converted_at = datetime.now(UTC)
        await db.flush()
        return lead, patient


@dataclass
class IntakeOutcome:
    """What an enquiry turned into. The public route discards it (D12)."""

    outcome: Literal["lead_created", "recall_queued"]
    lead: Lead | None = None
    recalled_patients: list[Patient] = field(default_factory=list)


class LeadIntakeService:
    """The single routing entry point for an enquiry."""

    @staticmethod
    async def route(
        db: AsyncSession,
        clinic_id: UUID,
        data: dict,
        *,
        recommended_by: UUID | None,
    ) -> IntakeOutcome:
        """Route one enquiry: new person to a lead, known patient to a recall.

        Both the public handler and POST /api/v1/leads/ call this, so the
        rule cannot diverge between the form and the front desk.
        """
        matched = await find_matching_patients(db, clinic_id, data.get("phone"), data.get("email"))
        if not matched:
            lead = await LeadService.create_lead(db, clinic_id, data)
            logger.info("leads: lead created for clinic %s", clinic_id)
            return IntakeOutcome("lead_created", lead=lead)

        recalled = await route_matched_enquiry(db, clinic_id, matched, data, recommended_by)
        return IntakeOutcome("recall_queued", recalled_patients=recalled)


class LeadSettingsService:
    """Per-clinic intake configuration + the daily volume counter."""

    @staticmethod
    async def get_or_create(db: AsyncSession, clinic_id: UUID) -> LeadSettings:
        """Lazy row, race-safe: INSERT ... ON CONFLICT DO NOTHING, then read.

        Select-then-insert would let two concurrent first-ever intakes both
        try to insert and one 500 on the unique violation. Column server
        defaults supply daily_cap=200 and day_count=0.
        """
        await db.execute(
            pg_insert(LeadSettings)
            .values(clinic_id=clinic_id)
            .on_conflict_do_nothing(index_elements=["clinic_id"])
        )
        stmt = select(LeadSettings).where(LeadSettings.clinic_id == clinic_id)
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def update(db: AsyncSession, clinic_id: UUID, data: dict) -> LeadSettings:
        """Update daily_cap only.

        Never touches day_count / day_count_date: the gauge is a fact about
        today, not a property of the config.
        """
        settings = await LeadSettingsService.get_or_create(db, clinic_id)
        if "daily_cap" in data and data["daily_cap"] is not None:
            settings.daily_cap = int(data["daily_cap"])
        await db.flush()
        return settings

    @staticmethod
    async def consume_daily_quota(db: AsyncSession, clinic_id: UUID) -> tuple[int, int]:
        """Count this attempt and read the cap in one atomic statement.

        Returns (day_count, daily_cap). Counting *before* the write is
        deliberate: blocked attempts stay visible in day_count, so the
        clinic sees how big a flood is rather than only that intake
        stopped. One statement means no read-then-write race, and it
        survives multi-worker restarts (which the in-process rate limiter
        does not).
        """
        await LeadSettingsService.get_or_create(db, clinic_id)

        row = (
            await db.execute(
                update(LeadSettings)
                .where(LeadSettings.clinic_id == clinic_id)
                .values(
                    day_count=case(
                        (
                            LeadSettings.day_count_date == func.current_date(),
                            LeadSettings.day_count + 1,
                        ),
                        else_=1,
                    ),
                    day_count_date=func.current_date(),
                )
                .returning(LeadSettings.day_count, LeadSettings.daily_cap)
            )
        ).one()
        return int(row[0]), int(row[1])


class LeadIntakeKeyService:
    """The clinic's single intake key: mint, rotate, resolve, revoke."""

    @staticmethod
    def _hash(plaintext: str) -> str:
        """SHA-256 hex — same reasoning as integrations._hash_token.

        The key is high-entropy random, so a fast hash is the right tool; a
        leaked DB dump must not hand out working keys.
        """
        return hashlib.sha256(plaintext.encode()).hexdigest()

    @staticmethod
    async def get_key(db: AsyncSession, clinic_id: UUID) -> LeadIntakeKey | None:
        stmt = select(LeadIntakeKey).where(LeadIntakeKey.clinic_id == clinic_id)
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def rotate(db: AsyncSession, clinic_id: UUID) -> tuple[LeadIntakeKey, str]:
        """Mint or replace the clinic's key. Plaintext returned **once**.

        Rotating stops a leaked key immediately; it deliberately does not
        touch day_count — rotation stops a flood, it does not hand the
        attacker a fresh daily budget.
        """
        plaintext = KEY_PREFIX + secrets.token_urlsafe(32)
        key_hash = LeadIntakeKeyService._hash(plaintext)
        key_prefix = plaintext[:12]

        stmt = (
            pg_insert(LeadIntakeKey)
            .values(
                clinic_id=clinic_id,
                key_hash=key_hash,
                key_prefix=key_prefix,
                is_active=True,
            )
            .on_conflict_do_update(
                index_elements=["clinic_id"],
                set_={
                    "key_hash": key_hash,
                    "key_prefix": key_prefix,
                    "is_active": True,
                    "updated_at": func.now(),
                },
            )
        )
        await db.execute(stmt)
        await db.flush()

        key = await LeadIntakeKeyService.get_key(db, clinic_id)
        if key is None:  # pragma: no cover - the upsert just wrote it
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Intake key could not be stored",
            )
        return key, plaintext

    @staticmethod
    async def resolve_clinic_id(db: AsyncSession, plaintext: str | None) -> UUID | None:
        """Map a presented key to its clinic, touching last_used_at.

        Returns None for unknown *and* inactive keys, so the caller cannot
        leak which one it was.
        """
        if not plaintext:
            return None
        key_hash = LeadIntakeKeyService._hash(plaintext)
        stmt = select(LeadIntakeKey).where(
            LeadIntakeKey.key_hash == key_hash,
            LeadIntakeKey.is_active.is_(True),
        )
        key = (await db.execute(stmt)).scalar_one_or_none()
        if key is None:
            return None
        key.last_used_at = datetime.now(UTC)
        await db.flush()
        return key.clinic_id

    @staticmethod
    async def set_active(db: AsyncSession, clinic_id: UUID, is_active: bool) -> LeadIntakeKey:
        """The operator's kill switch — instant, no deploy."""
        key = await LeadIntakeKeyService.get_key(db, clinic_id)
        if key is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="No intake key configured for this clinic",
            )
        key.is_active = is_active
        await db.flush()
        return key


__all__ = [
    "KEY_PREFIX",
    "IntakeOutcome",
    "LeadIntakeKeyService",
    "LeadIntakeService",
    "LeadService",
    "LeadSettingsService",
]
