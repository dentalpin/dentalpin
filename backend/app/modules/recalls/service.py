"""Recalls module service layer.

Static-method classes — routers stay thin, business logic lives here.
Multi-tenancy is mandatory: every query filters by ``clinic_id``.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.core.events.types import EventType
from app.core.utils.dates import clinic_today_for, clinic_zone_for
from app.modules.patients.models import Patient

from .models import (
    DEFAULT_CATEGORY_TO_REASON,
    DEFAULT_REASON_INTERVALS,
    Recall,
    RecallContactAttempt,
    RecallSettings,
)

logger = logging.getLogger(__name__)


# Status sets used in multiple queries.
ACTIVE_STATUSES = ("pending", "contacted_no_answer", "contacted_scheduled")
OPEN_STATUSES = ACTIVE_STATUSES + ("needs_review",)
TERMINAL_STATUSES = ("done", "cancelled")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_due_month(d: date) -> date:
    """Always day-1 of the month — keeps the index selective."""
    return date(d.year, d.month, 1)


def _add_months(d: date, months: int) -> date:
    """Add N calendar months to a day-1 date, returning a day-1 date."""
    base = _normalize_due_month(d)
    total = base.year * 12 + (base.month - 1) + months
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


def _build_event_payload(recall: Recall) -> dict[str, Any]:
    return {
        "recall_id": str(recall.id),
        "clinic_id": str(recall.clinic_id),
        "patient_id": str(recall.patient_id),
        "reason": recall.reason,
        "due_month": recall.due_month.isoformat(),
        "priority": recall.priority,
        "status": recall.status,
    }


@dataclass
class RecallFilters:
    month: date | None = None  # any day in target month, normalised internally
    reason: str | None = None
    professional_id: UUID | None = None
    status: str | None = None
    priority: str | None = None
    overdue: bool = False  # status active + due_month < current month
    patient_id: UUID | None = None
    include_archived_patients: bool = False  # surfaces needs_review bucket
    include_do_not_contact: bool = False


# ---------------------------------------------------------------------------
# RecallService
# ---------------------------------------------------------------------------


class RecallService:
    """Business logic for ``recalls`` and ``recall_contact_attempts``."""

    # --- Read ----------------------------------------------------------------

    @staticmethod
    async def list(
        db: AsyncSession,
        clinic_id: UUID,
        filters: RecallFilters,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Recall], int]:
        # Both predicates matter: Recall.clinic_id scopes the rows, and
        # Patient.clinic_id keeps the join from ever surfacing a foreign
        # patient's name/phone if a stray cross-clinic recall exists
        # (defense in depth behind create()'s patient-clinic guard).
        conditions = [
            Recall.clinic_id == clinic_id,
            Patient.clinic_id == clinic_id,
        ]

        if not filters.include_archived_patients:
            conditions.append(Patient.status != "archived")
        if not filters.include_do_not_contact:
            conditions.append(Patient.do_not_contact.is_(False))

        if filters.month:
            month = _normalize_due_month(filters.month)
            conditions.append(Recall.due_month == month)

        if filters.reason:
            conditions.append(Recall.reason == filters.reason)
        if filters.priority:
            conditions.append(Recall.priority == filters.priority)
        if filters.professional_id:
            conditions.append(Recall.assigned_professional_id == filters.professional_id)
        if filters.patient_id:
            conditions.append(Recall.patient_id == filters.patient_id)
        if filters.status:
            conditions.append(Recall.status == filters.status)
        if filters.overdue:
            current_month = _normalize_due_month(await clinic_today_for(db, clinic_id))
            conditions.append(
                and_(
                    Recall.due_month < current_month,
                    Recall.status.in_(ACTIVE_STATUSES),
                )
            )

        count_stmt = (
            select(func.count(Recall.id))
            .select_from(Recall)
            .join(Patient, Patient.id == Recall.patient_id)
            .where(*conditions)
        )
        total = int((await db.execute(count_stmt)).scalar_one() or 0)

        stmt = (
            select(Recall, Patient)
            .join(Patient, Patient.id == Recall.patient_id)
            .where(*conditions)
        )

        priority_order = case(
            (Recall.priority == "high", 0),
            (Recall.priority == "normal", 1),
            (Recall.priority == "low", 2),
            else_=3,
        )
        stmt = (
            stmt.order_by(priority_order, Recall.due_month, Recall.created_at, Recall.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        rows = result.all()
        items: list[Recall] = []
        for recall, patient in rows:
            # Attach patient brief without a relationship — the API layer
            # serialises ``patient`` from the column we set here.
            recall.patient = patient  # type: ignore[attr-defined]
            items.append(recall)
        return items, total

    @staticmethod
    async def get(db: AsyncSession, clinic_id: UUID, recall_id: UUID) -> Recall | None:
        stmt = select(Recall).where(Recall.id == recall_id, Recall.clinic_id == clinic_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_with_attempts(
        db: AsyncSession, clinic_id: UUID, recall_id: UUID
    ) -> tuple[Recall | None, list[RecallContactAttempt]]:
        recall = await RecallService.get(db, clinic_id, recall_id)
        if not recall:
            return None, []
        result = await db.execute(
            select(RecallContactAttempt)
            .where(RecallContactAttempt.recall_id == recall.id)
            .order_by(RecallContactAttempt.attempted_at.desc())
        )
        return recall, list(result.scalars().all())

    @staticmethod
    async def list_attempts(
        db: AsyncSession, clinic_id: UUID, recall_id: UUID
    ) -> list[RecallContactAttempt]:
        result = await db.execute(
            select(RecallContactAttempt)
            .where(
                RecallContactAttempt.clinic_id == clinic_id,
                RecallContactAttempt.recall_id == recall_id,
            )
            .order_by(RecallContactAttempt.attempted_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_for_patient(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, limit: int = 50
    ) -> list[Recall]:
        result = await db.execute(
            select(Recall)
            .where(Recall.clinic_id == clinic_id, Recall.patient_id == patient_id)
            .order_by(Recall.due_month.desc(), Recall.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # --- Duplicate guard helper ---------------------------------------------

    @staticmethod
    async def find_pending_for(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, reason: str
    ) -> Recall | None:
        result = await db.execute(
            select(Recall).where(
                Recall.clinic_id == clinic_id,
                Recall.patient_id == patient_id,
                Recall.reason == reason,
                Recall.status.in_(ACTIVE_STATUSES),
            )
        )
        return result.scalars().first()

    # --- Write ---------------------------------------------------------------

    @staticmethod
    async def create(
        db: AsyncSession,
        clinic_id: UUID,
        data: dict[str, Any],
        recommended_by: UUID | None,
    ) -> tuple[Recall, bool]:
        """Create or update-the-existing-pending row for the patient.

        Returns ``(recall, created)`` — ``created`` is False when the
        duplicate guard updated an existing row instead of inserting.
        Publishes ``recall.created`` only when ``created`` is True.

        Raises ``ValueError`` if ``patient_id`` does not belong to
        ``clinic_id`` — otherwise a caller (HTTP or copilot tool) could
        create a recall pointing at another clinic's patient and read
        that patient's name/phone back through the list/export (audit
        multi-tenancy #1).
        """
        patient_in_clinic = await db.execute(
            select(Patient.id).where(
                Patient.id == data["patient_id"],
                Patient.clinic_id == clinic_id,
            )
        )
        if patient_in_clinic.scalar_one_or_none() is None:
            raise ValueError("Patient not found in this clinic")

        existing = await RecallService.find_pending_for(
            db, clinic_id, data["patient_id"], data["reason"]
        )
        normalised_due_month = _normalize_due_month(data["due_month"])

        if existing:
            existing.due_month = normalised_due_month
            existing.due_date = data.get("due_date")
            existing.priority = data.get("priority", existing.priority)
            existing.reason_note = data.get("reason_note")
            existing.assigned_professional_id = data.get("assigned_professional_id")
            existing.linked_treatment_id = data.get("linked_treatment_id")
            existing.linked_treatment_category_key = data.get("linked_treatment_category_key")
            await db.flush()
            return existing, False

        recall = Recall(
            clinic_id=clinic_id,
            patient_id=data["patient_id"],
            due_month=normalised_due_month,
            due_date=data.get("due_date"),
            reason=data["reason"],
            reason_note=data.get("reason_note"),
            priority=data.get("priority", "normal"),
            status="pending",
            recommended_by=recommended_by,
            assigned_professional_id=data.get("assigned_professional_id"),
            contact_attempt_count=0,
            linked_treatment_id=data.get("linked_treatment_id"),
            linked_treatment_category_key=data.get("linked_treatment_category_key"),
        )
        db.add(recall)
        await db.flush()
        await event_bus.publish(EventType.RECALL_CREATED, _build_event_payload(recall), db=db)
        return recall, True

    @staticmethod
    async def update(
        db: AsyncSession,
        clinic_id: UUID,
        recall_id: UUID,
        data: dict[str, Any],
    ) -> Recall | None:
        recall = await RecallService.get(db, clinic_id, recall_id)
        if not recall:
            return None
        if "due_month" in data and data["due_month"]:
            recall.due_month = _normalize_due_month(data["due_month"])
        if "due_date" in data:
            recall.due_date = data["due_date"]
        if "reason" in data and data["reason"]:
            recall.reason = data["reason"]
        if "reason_note" in data:
            recall.reason_note = data["reason_note"]
        if "priority" in data and data["priority"]:
            recall.priority = data["priority"]
        if "assigned_professional_id" in data:
            recall.assigned_professional_id = data["assigned_professional_id"]
        await db.flush()
        return recall

    @staticmethod
    async def snooze(
        db: AsyncSession,
        clinic_id: UUID,
        recall_id: UUID,
        months: int,
        reason_note: str | None,
        by_user: UUID | None,
    ) -> Recall | None:
        recall = await RecallService.get(db, clinic_id, recall_id)
        if not recall:
            return None
        recall.due_month = _add_months(recall.due_month, months)
        if reason_note:
            stamp = (
                datetime.now(UTC).strftime("%Y-%m-%d")
                + " ("
                + (str(by_user) if by_user else "system")
                + "): "
            )
            recall.reason_note = (
                (recall.reason_note + "\n" if recall.reason_note else "")
                + stamp
                + f"snoozed +{months}mo · {reason_note}"
            )
        if recall.status not in ("done", "cancelled"):
            recall.status = "pending"
        await db.flush()
        payload = _build_event_payload(recall)
        payload["snoozed_months"] = months
        await event_bus.publish(EventType.RECALL_SNOOZED, payload)
        return recall

    @staticmethod
    async def cancel(
        db: AsyncSession,
        clinic_id: UUID,
        recall_id: UUID,
        note: str | None,
        by_user: UUID | None,
    ) -> Recall | None:
        recall = await RecallService.get(db, clinic_id, recall_id)
        if not recall:
            return None
        recall.status = "cancelled"
        if note:
            recall.reason_note = (
                recall.reason_note + "\n" if recall.reason_note else ""
            ) + f"cancelled: {note}"
        await db.flush()
        await event_bus.publish(EventType.RECALL_CANCELLED, _build_event_payload(recall))
        return recall

    @staticmethod
    async def mark_done(
        db: AsyncSession,
        clinic_id: UUID,
        recall_id: UUID,
        by_user: UUID | None,
        commit: bool = True,
    ) -> Recall | None:
        recall = await RecallService.get(db, clinic_id, recall_id)
        if not recall:
            return None
        recall.status = "done"
        recall.completed_at = datetime.now(UTC)
        await db.flush()
        await event_bus.publish(EventType.RECALL_COMPLETED, _build_event_payload(recall))
        return recall

    @staticmethod
    async def log_attempt(
        db: AsyncSession,
        clinic_id: UUID,
        recall_id: UUID,
        attempt_data: dict[str, Any],
        by_user: UUID,
    ) -> tuple[Recall, RecallContactAttempt] | None:
        recall = await RecallService.get(db, clinic_id, recall_id)
        if not recall:
            return None
        attempt = RecallContactAttempt(
            recall_id=recall.id,
            clinic_id=clinic_id,
            attempted_by=by_user,
            channel=attempt_data["channel"],
            outcome=attempt_data["outcome"],
            note=attempt_data.get("note"),
        )
        db.add(attempt)
        recall.contact_attempt_count = (recall.contact_attempt_count or 0) + 1
        recall.last_contact_attempt_at = datetime.now(UTC)

        outcome = attempt_data["outcome"]
        linked = attempt_data.get("linked_appointment_id")
        if outcome == "scheduled":
            recall.status = "contacted_scheduled"
            if linked:
                recall.linked_appointment_id = linked
        elif outcome == "declined":
            recall.status = "contacted_declined"
        elif outcome in ("no_answer", "voicemail", "wrong_number"):
            if recall.status == "pending":
                recall.status = "contacted_no_answer"

        await db.flush()
        return recall, attempt

    @staticmethod
    async def link_appointment(
        db: AsyncSession,
        clinic_id: UUID,
        recall_id: UUID,
        appointment_id: UUID,
    ) -> Recall | None:
        recall = await RecallService.get(db, clinic_id, recall_id)
        if not recall:
            return None
        recall.linked_appointment_id = appointment_id
        if recall.status in ("pending", "contacted_no_answer"):
            recall.status = "contacted_scheduled"
        await db.flush()
        return recall

    @staticmethod
    async def auto_link_for_appointment(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        appointment_id: UUID,
        appointment_date: date,
    ) -> Recall | None:
        """Called from ``on_appointment_scheduled``.

        Conservative auto-link policy: link the appointment only when
        the patient has *exactly one* active recall whose ``due_month``
        is at or before the appointment month. Bails out when there are
        zero or two-plus candidates so the system never silently
        attaches the appointment to the wrong recall — reception keeps
        the explicit "Agendar cita" path from a recall row when the
        patient has more than one active recall.
        """
        appointment_month = _normalize_due_month(appointment_date)
        result = await db.execute(
            select(Recall)
            .where(
                Recall.clinic_id == clinic_id,
                Recall.patient_id == patient_id,
                Recall.status.in_(("pending", "contacted_no_answer")),
                Recall.due_month <= appointment_month,
                Recall.linked_appointment_id.is_(None),
            )
            # Two is enough to know we have to bail; no need to fetch more.
            .limit(2)
        )
        candidates = list(result.scalars().all())
        if len(candidates) != 1:
            # Zero candidates: nothing to do.
            # Two-plus: ambiguous — let reception link manually.
            return None
        recall = candidates[0]
        recall.linked_appointment_id = appointment_id
        recall.status = "contacted_scheduled"
        await db.flush()
        return recall

    # --- Suggestion ----------------------------------------------------------

    @staticmethod
    async def suggest_next_for_treatment(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        treatment_category_key: str | None,
        treatment_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        """Compute a non-binding next-recall suggestion.

        Returns ``None`` when the patient is excluded
        (archived / do_not_contact) or no mapping exists for the
        given category. Caller decides whether to materialise the
        suggestion as a recall (via POST /recalls).
        """
        patient = (
            await db.execute(
                select(Patient).where(
                    Patient.id == patient_id,
                    Patient.clinic_id == clinic_id,
                )
            )
        ).scalar_one_or_none()
        if not patient:
            return None
        if patient.status == "archived" or patient.do_not_contact:
            return None

        settings = await RecallSettingsService.get_or_create(db, clinic_id)
        reason = (
            settings.category_to_reason.get(treatment_category_key)
            if treatment_category_key
            else None
        )
        if not reason:
            return None
        interval = settings.reason_intervals.get(reason)
        if not interval:
            return None
        due_month = _add_months(await clinic_today_for(db, clinic_id), int(interval))
        return {
            "patient_id": patient_id,
            "reason": reason,
            "due_month": due_month,
            "interval_months": int(interval),
            "treatment_category_key": treatment_category_key,
            "treatment_id": treatment_id,
            "matched_setting": True,
        }

    # --- Stats / export ------------------------------------------------------

    @staticmethod
    async def dashboard_stats(
        db: AsyncSession, clinic_id: UUID, today: date | None = None
    ) -> dict[str, int | float]:
        tz = await clinic_zone_for(db, clinic_id)
        today = today or datetime.now(tz).date()
        month_start = _normalize_due_month(today)
        month_end = _add_months(month_start, 1)
        week_end = today + timedelta(days=7)
        # "This month" is the clinic's month. A naive bound would be read in
        # the app process's zone, so the KPI moved with the container's TZ.
        month_start_at = datetime.combine(month_start, datetime.min.time(), tzinfo=tz)
        month_end_at = datetime.combine(month_end, datetime.min.time(), tzinfo=tz)

        async def count_where(*conditions: Any) -> int:
            stmt = (
                select(func.count())
                .select_from(Recall)
                .join(Patient, Patient.id == Recall.patient_id)
                .where(
                    Recall.clinic_id == clinic_id,
                    Patient.status != "archived",
                    Patient.do_not_contact.is_(False),
                    *conditions,
                )
            )
            return int((await db.execute(stmt)).scalar_one() or 0)

        due_this_week = await count_where(
            Recall.status.in_(ACTIVE_STATUSES),
            Recall.due_month <= week_end,
            Recall.due_month >= month_start,
        )
        due_this_month = await count_where(
            Recall.status.in_(ACTIVE_STATUSES),
            Recall.due_month == month_start,
        )
        overdue = await count_where(
            Recall.status.in_(ACTIVE_STATUSES),
            Recall.due_month < month_start,
        )
        scheduled_this_month = await count_where(
            Recall.status == "contacted_scheduled",
            Recall.due_month >= month_start,
            Recall.due_month < month_end,
        )
        completed_this_month_count = await count_where(
            Recall.status == "done",
            Recall.completed_at >= month_start_at,
            Recall.completed_at < month_end_at,
        )
        # Conversion = completed this month / (completed + cancelled this month)
        cancelled_this_month_count = await count_where(
            Recall.status == "cancelled",
            Recall.updated_at >= month_start_at,
            Recall.updated_at < month_end_at,
        )
        denominator = completed_this_month_count + cancelled_this_month_count
        conversion_rate = float(completed_this_month_count) / denominator if denominator else 0.0
        return {
            "due_this_week": due_this_week,
            "due_this_month": due_this_month,
            "overdue": overdue,
            "scheduled_this_month": scheduled_this_month,
            "completed_this_month": completed_this_month_count,
            "conversion_rate": round(conversion_rate, 4),
        }

    @staticmethod
    async def export_rows(
        db: AsyncSession,
        clinic_id: UUID,
        filters: RecallFilters,
    ) -> Sequence[tuple[Recall, Patient]]:
        """Stream rows for CSV export. Same filter rules as ``list``."""
        items, _ = await RecallService.list(db, clinic_id, filters, page=1, page_size=10_000)
        # Patient was attached as ``recall.patient`` in ``list``.
        return [(r, r.patient) for r in items]  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# RecallSettingsService
# ---------------------------------------------------------------------------


class RecallSettingsService:
    @staticmethod
    async def get_or_create(db: AsyncSession, clinic_id: UUID) -> RecallSettings:
        result = await db.execute(
            select(RecallSettings).where(RecallSettings.clinic_id == clinic_id)
        )
        settings = result.scalar_one_or_none()
        if settings:
            return settings
        settings = RecallSettings(
            clinic_id=clinic_id,
            reason_intervals=dict(DEFAULT_REASON_INTERVALS),
            category_to_reason=dict(DEFAULT_CATEGORY_TO_REASON),
            auto_suggest_on_treatment_completed=True,
            auto_link_on_appointment_scheduled=True,
        )
        db.add(settings)
        await db.flush()
        return settings

    @staticmethod
    async def update(
        db: AsyncSession,
        clinic_id: UUID,
        data: dict[str, Any],
    ) -> RecallSettings:
        settings = await RecallSettingsService.get_or_create(db, clinic_id)
        if "reason_intervals" in data and data["reason_intervals"] is not None:
            settings.reason_intervals = data["reason_intervals"]
        if "category_to_reason" in data and data["category_to_reason"] is not None:
            settings.category_to_reason = data["category_to_reason"]
        if (
            "auto_suggest_on_treatment_completed" in data
            and data["auto_suggest_on_treatment_completed"] is not None
        ):
            settings.auto_suggest_on_treatment_completed = data[
                "auto_suggest_on_treatment_completed"
            ]
        if (
            "auto_link_on_appointment_scheduled" in data
            and data["auto_link_on_appointment_scheduled"] is not None
        ):
            settings.auto_link_on_appointment_scheduled = data["auto_link_on_appointment_scheduled"]
        settings.updated_at = datetime.now(UTC)
        await db.flush()
        return settings


# ---------------------------------------------------------------------------
# Re-export for convenience.
# ---------------------------------------------------------------------------

__all__ = [
    "ACTIVE_STATUSES",
    "OPEN_STATUSES",
    "TERMINAL_STATUSES",
    "RecallFilters",
    "RecallService",
    "RecallSettingsService",
    "_add_months",
    "_normalize_due_month",
]
