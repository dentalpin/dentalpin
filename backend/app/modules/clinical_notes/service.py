"""Clinical notes service layer.

CRUD + queries for ``clinical_notes``. Owner existence is validated
up-front against the relevant module model (patients, odontogram,
treatment_plan) — the manifest declares those as ``depends`` so this is
a sanctioned cross-module read.

Document attachments are delegated to the ``media`` module (see issue
#55). When a note is created with ``attachment_document_ids`` we link
each document twice via ``media.AttachmentService``:

1. To the note's own owner (e.g. ``owner_type='plan'``) so the document
   surfaces in the plan's gallery.
2. To the note itself (``owner_type='clinical_note'``,
   ``owner_id=note.id``) so the note's renderer can list its
   attachments.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.events import event_bus
from app.core.events.types import EventType
from app.modules.agenda.models import Appointment
from app.modules.media.models import Document, MediaAttachment
from app.modules.media.service import AttachmentService
from app.modules.odontogram.models import Treatment
from app.modules.patients.models import Patient
from app.modules.treatment_plan.models import PlannedTreatmentItem, TreatmentPlan

from .models import (
    NOTE_OWNER_APPOINTMENT,
    NOTE_OWNER_PATIENT,
    NOTE_OWNER_PLAN,
    NOTE_OWNER_TREATMENT,
    NOTE_OWNER_TYPES,
    NOTE_TYPE_ADMINISTRATIVE,
    NOTE_TYPE_APPOINTMENT_ADMINISTRATIVE,
    NOTE_TYPE_APPOINTMENT_CLINICAL,
    NOTE_TYPE_DIAGNOSIS,
    NOTE_TYPE_TREATMENT,
    NOTE_TYPE_TREATMENT_PLAN,
    ClinicalNote,
)

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_EXCERPT_MAX = 200

# Owner types accepted by the read-only ``/attachments`` proxy endpoint.
_VALID_ATTACHMENT_OWNER_TYPES = (*NOTE_OWNER_TYPES, "clinical_note")


def body_excerpt(body: str) -> str:
    """Strip HTML + collapse whitespace for event payloads / timeline titles."""
    text = _HTML_TAG_RE.sub(" ", body or "")
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text[:_EXCERPT_MAX]


class NoteOwnerError(ValueError):
    """Owner does not exist in this clinic, or note_type/owner mismatch."""


class AttachmentPatientMismatchError(ValueError):
    """Document belongs to a different patient than the note owner."""


_NOTE_TYPE_TO_EVENT = {
    NOTE_TYPE_ADMINISTRATIVE: EventType.CLINICAL_NOTE_ADMINISTRATIVE_CREATED,
    NOTE_TYPE_DIAGNOSIS: EventType.CLINICAL_NOTE_DIAGNOSIS_CREATED,
    NOTE_TYPE_TREATMENT: EventType.CLINICAL_NOTE_TREATMENT_CREATED,
    NOTE_TYPE_TREATMENT_PLAN: EventType.CLINICAL_NOTE_PLAN_CREATED,
    NOTE_TYPE_APPOINTMENT_CLINICAL: EventType.CLINICAL_NOTE_APPOINTMENT_CLINICAL_CREATED,
    NOTE_TYPE_APPOINTMENT_ADMINISTRATIVE: (
        EventType.CLINICAL_NOTE_APPOINTMENT_ADMINISTRATIVE_CREATED
    ),
}


# ---------------------------------------------------------------------------
# Owner resolution (used by routes; the media registry has its own copies)
# ---------------------------------------------------------------------------


async def _resolve_patient_owner(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> UUID:
    result = await db.execute(
        select(Patient.id).where(
            Patient.id == patient_id,
            Patient.clinic_id == clinic_id,
        )
    )
    row = result.first()
    if row is None:
        raise NoteOwnerError(f"patient {patient_id} not found")
    return row[0]


async def _resolve_treatment_owner(
    db: AsyncSession, clinic_id: UUID, treatment_id: UUID
) -> tuple[UUID, UUID]:
    result = await db.execute(
        select(Treatment.id, Treatment.patient_id).where(
            Treatment.id == treatment_id,
            Treatment.clinic_id == clinic_id,
            Treatment.deleted_at.is_(None),
        )
    )
    row = result.first()
    if row is None:
        raise NoteOwnerError(f"treatment {treatment_id} not found")
    return row[0], row[1]


async def _resolve_plan_owner(
    db: AsyncSession, clinic_id: UUID, plan_id: UUID
) -> tuple[UUID, UUID]:
    result = await db.execute(
        select(TreatmentPlan.id, TreatmentPlan.patient_id).where(
            TreatmentPlan.id == plan_id,
            TreatmentPlan.clinic_id == clinic_id,
            TreatmentPlan.deleted_at.is_(None),
        )
    )
    row = result.first()
    if row is None:
        raise NoteOwnerError(f"treatment_plan {plan_id} not found")
    return row[0], row[1]


async def _resolve_appointment_owner(
    db: AsyncSession, clinic_id: UUID, appointment_id: UUID
) -> tuple[UUID, UUID]:
    result = await db.execute(
        select(Appointment.id, Appointment.patient_id).where(
            Appointment.id == appointment_id,
            Appointment.clinic_id == clinic_id,
        )
    )
    row = result.first()
    if row is None:
        raise NoteOwnerError(f"appointment {appointment_id} not found")
    if row[1] is None:
        raise NoteOwnerError(
            f"appointment {appointment_id} has no patient — notes require a patient binding"
        )
    return row[0], row[1]


async def resolve_owner_patient(
    db: AsyncSession,
    clinic_id: UUID,
    owner_type: str,
    owner_id: UUID,
) -> UUID:
    """Return the patient_id reachable from an owner reference, or raise."""
    if owner_type == NOTE_OWNER_PATIENT:
        return await _resolve_patient_owner(db, clinic_id, owner_id)
    if owner_type == NOTE_OWNER_TREATMENT:
        _, patient_id = await _resolve_treatment_owner(db, clinic_id, owner_id)
        return patient_id
    if owner_type == NOTE_OWNER_PLAN:
        _, patient_id = await _resolve_plan_owner(db, clinic_id, owner_id)
        return patient_id
    if owner_type == NOTE_OWNER_APPOINTMENT:
        _, patient_id = await _resolve_appointment_owner(db, clinic_id, owner_id)
        return patient_id
    raise NoteOwnerError(f"unsupported owner_type {owner_type!r}")


# ---------------------------------------------------------------------------
# Notes service
# ---------------------------------------------------------------------------


class NoteService:
    """CRUD for clinical notes."""

    @staticmethod
    async def list_for_owner(
        db: AsyncSession,
        clinic_id: UUID,
        owner_type: str,
        owner_id: UUID,
    ) -> list[ClinicalNote]:
        if owner_type not in NOTE_OWNER_TYPES:
            raise NoteOwnerError(f"unsupported note owner_type {owner_type!r}")
        result = await db.execute(
            select(ClinicalNote)
            .where(
                ClinicalNote.clinic_id == clinic_id,
                ClinicalNote.owner_type == owner_type,
                ClinicalNote.owner_id == owner_id,
                ClinicalNote.deleted_at.is_(None),
            )
            .options(selectinload(ClinicalNote.author))
            .order_by(ClinicalNote.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get(db: AsyncSession, clinic_id: UUID, note_id: UUID) -> ClinicalNote | None:
        result = await db.execute(
            select(ClinicalNote).where(
                ClinicalNote.id == note_id,
                ClinicalNote.clinic_id == clinic_id,
                ClinicalNote.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    async def create(
        cls,
        db: AsyncSession,
        *,
        clinic_id: UUID,
        user_id: UUID,
        note_type: str,
        owner_type: str,
        owner_id: UUID,
        body: str,
        tooth_number: int | None = None,
        attachment_document_ids: Iterable[UUID] | None = None,
    ) -> ClinicalNote:
        patient_id = await resolve_owner_patient(db, clinic_id, owner_type, owner_id)

        note = ClinicalNote(
            clinic_id=clinic_id,
            note_type=note_type,
            owner_type=owner_type,
            owner_id=owner_id,
            tooth_number=tooth_number if note_type == NOTE_TYPE_DIAGNOSIS else None,
            body=body,
            author_id=user_id,
        )
        db.add(note)
        await db.flush()

        if attachment_document_ids:
            doc_ids = list(attachment_document_ids)
            await _link_documents_to_note(
                db,
                clinic_id=clinic_id,
                document_ids=doc_ids,
                note=note,
                expected_patient_id=patient_id,
            )

        await db.flush()

        event_name = _NOTE_TYPE_TO_EVENT[note_type]
        await event_bus.publish(
            event_name,
            {
                "clinic_id": str(clinic_id),
                "patient_id": str(patient_id),
                "note_id": str(note.id),
                "note_type": note_type,
                "owner_type": owner_type,
                "owner_id": str(owner_id),
                "tooth_number": note.tooth_number,
                "user_id": str(user_id),
                "body_excerpt": body_excerpt(body),
                "occurred_at": note.created_at.isoformat() if note.created_at else None,
            },
        )
        return note

    @staticmethod
    async def update(
        db: AsyncSession,
        *,
        clinic_id: UUID,
        note_id: UUID,
        body: str,
        user_id: UUID,
        is_admin: bool,
    ) -> ClinicalNote | None:
        result = await db.execute(
            select(ClinicalNote).where(
                ClinicalNote.id == note_id,
                ClinicalNote.clinic_id == clinic_id,
                ClinicalNote.deleted_at.is_(None),
            )
        )
        note = result.scalar_one_or_none()
        if note is None:
            return None
        if note.author_id != user_id and not is_admin:
            raise PermissionError("Only the author or an admin can edit this note")
        note.body = body
        await db.flush()
        return note

    @staticmethod
    async def soft_delete(
        db: AsyncSession,
        *,
        clinic_id: UUID,
        note_id: UUID,
        user_id: UUID,
        is_admin: bool,
    ) -> bool:
        result = await db.execute(
            select(ClinicalNote).where(
                ClinicalNote.id == note_id,
                ClinicalNote.clinic_id == clinic_id,
                ClinicalNote.deleted_at.is_(None),
            )
        )
        note = result.scalar_one_or_none()
        if note is None:
            return False
        if note.author_id != user_id and not is_admin:
            raise PermissionError("Only the author or an admin can delete this note")
        note.deleted_at = datetime.now(UTC)
        await db.flush()
        return True


# ---------------------------------------------------------------------------
# Attachments — thin adapter layered on media.AttachmentService
# ---------------------------------------------------------------------------


async def _link_documents_to_note(
    db: AsyncSession,
    *,
    clinic_id: UUID,
    document_ids: list[UUID],
    note: ClinicalNote,
    expected_patient_id: UUID,
) -> None:
    """Link each document to (a) the note's own owner and (b) the note itself.

    Patient-mismatch is enforced by ``media.AttachmentService.link`` via
    the registry's owner resolvers, so we only validate here when the
    expected patient is known up-front (defensive — a wrong document_id
    would otherwise leak across patients).
    """
    docs = await _load_documents(db, clinic_id, document_ids)
    by_id = {d.id: d for d in docs}
    missing = [d for d in document_ids if d not in by_id]
    if missing:
        raise NoteOwnerError(f"documents not found: {missing}")
    for doc in docs:
        if doc.patient_id != expected_patient_id:
            raise AttachmentPatientMismatchError("Document does not belong to the owner's patient")

    for order, doc_id in enumerate(document_ids):
        # Link to the note's owner so the gallery for that owner sees it.
        await AttachmentService.link(
            db,
            clinic_id=clinic_id,
            document_id=doc_id,
            owner_type=note.owner_type,
            owner_id=note.owner_id,
            display_order=order,
        )
        # Link to the note itself so the note renderer can fetch by note_id.
        await AttachmentService.link(
            db,
            clinic_id=clinic_id,
            document_id=doc_id,
            owner_type="clinical_note",
            owner_id=note.id,
            display_order=order,
        )


async def _load_documents(
    db: AsyncSession, clinic_id: UUID, document_ids: list[UUID]
) -> list[Document]:
    if not document_ids:
        return []
    result = await db.execute(
        select(Document).where(
            Document.id.in_(document_ids),
            Document.clinic_id == clinic_id,
        )
    )
    return list(result.scalars().all())


async def count_notes_for_owners(
    db: AsyncSession,
    clinic_id: UUID,
    owner_type: str,
    owner_ids: list[UUID],
) -> dict[UUID, int]:
    """Bulk count of live notes per ``owner_id`` for a single ``owner_type``.

    Owners with zero notes are omitted from the result. Soft-deleted
    notes are excluded.
    """
    if owner_type not in NOTE_OWNER_TYPES:
        raise NoteOwnerError(f"unsupported note owner_type {owner_type!r}")
    if not owner_ids:
        return {}
    result = await db.execute(
        select(ClinicalNote.owner_id, func.count(ClinicalNote.id))
        .where(
            ClinicalNote.clinic_id == clinic_id,
            ClinicalNote.owner_type == owner_type,
            ClinicalNote.owner_id.in_(owner_ids),
            ClinicalNote.deleted_at.is_(None),
        )
        .group_by(ClinicalNote.owner_id)
    )
    return {row[0]: row[1] for row in result.all()}


async def list_attachments_for_note(
    db: AsyncSession, clinic_id: UUID, note_id: UUID
) -> list[MediaAttachment]:
    return await AttachmentService.list_by_owner(db, clinic_id, "clinical_note", note_id)


async def list_attachments_for_owner(
    db: AsyncSession, clinic_id: UUID, owner_type: str, owner_id: UUID
) -> list[MediaAttachment]:
    if owner_type not in _VALID_ATTACHMENT_OWNER_TYPES:
        raise NoteOwnerError(f"unsupported attachment owner_type {owner_type!r}")
    return await AttachmentService.list_by_owner(db, clinic_id, owner_type, owner_id)


# ---------------------------------------------------------------------------
# Aggregate feeds — Summary tab + plan-grouped patient view + plan merged
# ---------------------------------------------------------------------------


async def _resolve_treatments_for_patient(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID
) -> dict[UUID, Treatment]:
    """Return live Treatments for this patient indexed by id."""
    result = await db.execute(
        select(Treatment)
        .where(
            Treatment.clinic_id == clinic_id,
            Treatment.patient_id == patient_id,
            Treatment.deleted_at.is_(None),
        )
        .options(
            selectinload(Treatment.teeth),
            selectinload(Treatment.catalog_item),
        )
    )
    return {t.id: t for t in result.scalars().all()}


async def list_recent_for_patient(
    db: AsyncSession,
    *,
    clinic_id: UUID,
    patient_id: UUID,
    note_types: list[str] | None,
    limit: int,
    before: datetime | None,
) -> list[dict]:
    """Recent notes feed for a patient across every owner type."""
    await _resolve_patient_owner(db, clinic_id, patient_id)

    treatments_by_id = await _resolve_treatments_for_patient(db, clinic_id, patient_id)
    treatment_ids = list(treatments_by_id.keys())

    plans_result = await db.execute(
        select(TreatmentPlan).where(
            TreatmentPlan.clinic_id == clinic_id,
            TreatmentPlan.patient_id == patient_id,
            TreatmentPlan.deleted_at.is_(None),
        )
    )
    plans = list(plans_result.scalars().all())
    plan_ids = [p.id for p in plans]
    plan_by_id = {p.id: p for p in plans}

    appointments_result = await db.execute(
        select(Appointment.id).where(
            Appointment.clinic_id == clinic_id,
            Appointment.patient_id == patient_id,
        )
    )
    appointment_ids = [row[0] for row in appointments_result.all()]

    treatment_clause = and_(
        ClinicalNote.owner_type == NOTE_OWNER_TREATMENT,
        ClinicalNote.owner_id.in_(treatment_ids) if treatment_ids else false(),
    )
    plan_clause = and_(
        ClinicalNote.owner_type == NOTE_OWNER_PLAN,
        ClinicalNote.owner_id.in_(plan_ids) if plan_ids else false(),
    )
    patient_clause = and_(
        ClinicalNote.owner_type == NOTE_OWNER_PATIENT,
        ClinicalNote.owner_id == patient_id,
    )
    appointment_clause = and_(
        ClinicalNote.owner_type == NOTE_OWNER_APPOINTMENT,
        ClinicalNote.owner_id.in_(appointment_ids) if appointment_ids else false(),
    )
    owner_filter = or_(patient_clause, treatment_clause, plan_clause, appointment_clause)

    stmt = (
        select(ClinicalNote)
        .where(
            ClinicalNote.clinic_id == clinic_id,
            ClinicalNote.deleted_at.is_(None),
            owner_filter,
        )
        .options(selectinload(ClinicalNote.author))
        .order_by(ClinicalNote.created_at.desc())
        .limit(limit)
    )
    if note_types:
        stmt = stmt.where(ClinicalNote.note_type.in_(note_types))
    if before is not None:
        stmt = stmt.where(ClinicalNote.created_at < before)

    result = await db.execute(stmt)
    notes = list(result.scalars().all())

    entries: list[dict] = []
    for note in notes:
        attachments = await list_attachments_for_note(db, clinic_id, note.id)
        linked = _build_linked(note, plan_by_id, treatments_by_id, patient_id)
        entries.append(
            {
                "id": note.id,
                "note_type": note.note_type,
                "owner_type": note.owner_type,
                "owner_id": note.owner_id,
                "tooth_number": note.tooth_number,
                "body": note.body,
                "created_at": note.created_at,
                "updated_at": note.updated_at,
                "author": _author_brief(note.author) if note.author else {"id": note.author_id},
                "linked": linked,
                "attachments": attachments,
            }
        )
    return entries


def _author_brief(author) -> dict:
    full_name = (
        getattr(author, "full_name", None)
        or " ".join(
            filter(
                None,
                [getattr(author, "first_name", None), getattr(author, "last_name", None)],
            )
        ).strip()
        or None
    )
    return {
        "id": author.id,
        "full_name": full_name,
        "email": getattr(author, "email", None),
    }


def _resolve_label(
    names: dict[str, str] | None,
) -> str | None:
    """Resolve a display label from catalog names: es → en → fr."""
    names = names or {}
    return next((names[k] for k in ("es", "en", "fr") if names.get(k)), None)


def _build_linked(
    note: ClinicalNote,
    plan_by_id: dict[UUID, TreatmentPlan],
    treatments_by_id: dict[UUID, Treatment],
    patient_id: UUID,
) -> dict:
    if note.owner_type == NOTE_OWNER_PATIENT:
        return {
            "kind": "patient",
            "id": patient_id,
            "label": None,
            "tooth_number": note.tooth_number,
        }
    if note.owner_type == NOTE_OWNER_TREATMENT:
        treatment = treatments_by_id.get(note.owner_id)
        teeth = [t.tooth_number for t in (treatment.teeth or [])] if treatment else []
        catalog = treatment.catalog_item if treatment else None
        label = _resolve_label(catalog.names if catalog else None) or (
            treatment.clinical_type if treatment else None
        )
        return {
            "kind": "treatment",
            "id": note.owner_id,
            "label": label,
            "tooth_number": teeth[0] if teeth else None,
        }
    if note.owner_type == NOTE_OWNER_PLAN:
        plan = plan_by_id.get(note.owner_id)
        label = plan.title or plan.plan_number if plan else None
        return {
            "kind": "plan",
            "id": note.owner_id,
            "label": label,
            "tooth_number": None,
        }
    if note.owner_type == NOTE_OWNER_APPOINTMENT:
        return {
            "kind": "appointment",
            "id": note.owner_id,
            "label": None,
            "tooth_number": None,
        }
    return {"kind": note.owner_type, "id": note.owner_id, "label": None, "tooth_number": None}


# ---------------------------------------------------------------------------
# Plan-scoped feeds (replaces ``treatment_plan.notes_service`` aggregations)
# ---------------------------------------------------------------------------


async def list_merged_for_plan(db: AsyncSession, clinic_id: UUID, plan_id: UUID) -> list[dict]:
    """Plan + treatment + visit notes for a single plan, newest-first."""
    from app.modules.agenda.models import Appointment, AppointmentTreatment

    plan_result = await db.execute(
        select(TreatmentPlan).where(
            TreatmentPlan.id == plan_id,
            TreatmentPlan.clinic_id == clinic_id,
            TreatmentPlan.deleted_at.is_(None),
        )
    )
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        return []

    items_result = await db.execute(
        select(PlannedTreatmentItem.id, PlannedTreatmentItem.treatment_id).where(
            PlannedTreatmentItem.treatment_plan_id == plan_id,
            PlannedTreatmentItem.clinic_id == clinic_id,
        )
    )
    item_rows = items_result.all()
    treatment_ids = [row[1] for row in item_rows]
    plan_item_id_for_treatment = {row[1]: row[0] for row in item_rows}

    treatment_clause = (
        and_(
            ClinicalNote.owner_type == NOTE_OWNER_TREATMENT,
            ClinicalNote.owner_id.in_(treatment_ids),
        )
        if treatment_ids
        else false()
    )
    owner_filter = or_(
        and_(
            ClinicalNote.owner_type == NOTE_OWNER_PLAN,
            ClinicalNote.owner_id == plan_id,
        ),
        treatment_clause,
    )
    notes_result = await db.execute(
        select(ClinicalNote)
        .where(
            ClinicalNote.clinic_id == clinic_id,
            ClinicalNote.deleted_at.is_(None),
            owner_filter,
        )
        .options(selectinload(ClinicalNote.author))
        .order_by(ClinicalNote.created_at.desc())
    )
    notes = list(notes_result.scalars().all())

    entries: list[dict] = []
    for note in notes:
        is_treatment = note.owner_type == NOTE_OWNER_TREATMENT
        plan_item_id = plan_item_id_for_treatment.get(note.owner_id) if is_treatment else None
        attachments = await list_attachments_for_note(db, clinic_id, note.id)
        entries.append(
            {
                "source": "treatment" if is_treatment else "plan",
                "note_id": note.id,
                "owner_id": note.owner_id,
                "plan_item_id": plan_item_id,
                "body": note.body,
                "author_id": note.author_id,
                "author": _author_brief(note.author) if note.author else None,
                "created_at": note.created_at,
                "updated_at": note.updated_at,
                "attachments": attachments,
            }
        )

    if item_rows:
        item_ids = [row[0] for row in item_rows]
        visit_result = await db.execute(
            select(AppointmentTreatment, Appointment)
            .join(Appointment, AppointmentTreatment.appointment_id == Appointment.id)
            .options(selectinload(Appointment.professional))
            .where(
                AppointmentTreatment.planned_treatment_item_id.in_(item_ids),
                AppointmentTreatment.notes.is_not(None),
                AppointmentTreatment.notes != "",
                Appointment.clinic_id == clinic_id,
            )
        )
        for apt_tr, appointment in visit_result.all():
            professional = appointment.professional if appointment else None
            entries.append(
                {
                    "source": "visit",
                    "note_id": None,
                    "owner_id": apt_tr.id,
                    "plan_item_id": apt_tr.planned_treatment_item_id,
                    "body": apt_tr.notes or "",
                    "author_id": appointment.professional_id if appointment else None,
                    "author": _author_brief(professional) if professional else None,
                    "created_at": apt_tr.created_at or appointment.created_at,
                    "updated_at": None,
                    "attachments": [],
                }
            )

    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return entries


async def list_grouped_for_patient(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID,
) -> list[dict]:
    """Per-plan grouping with plan-level + per-treatment buckets, newest plan first."""
    plans_result = await db.execute(
        select(TreatmentPlan)
        .where(
            TreatmentPlan.patient_id == patient_id,
            TreatmentPlan.clinic_id == clinic_id,
            TreatmentPlan.deleted_at.is_(None),
        )
        .order_by(TreatmentPlan.created_at.desc())
    )
    plans = list(plans_result.scalars().all())
    if not plans:
        return []

    treatments_by_id = await _resolve_treatments_for_patient(db, clinic_id, patient_id)

    groups: list[dict] = []
    for plan in plans:
        items_result = await db.execute(
            select(PlannedTreatmentItem)
            .where(
                PlannedTreatmentItem.treatment_plan_id == plan.id,
                PlannedTreatmentItem.clinic_id == clinic_id,
            )
            .order_by(PlannedTreatmentItem.sequence_order)
        )
        items = list(items_result.scalars().all())

        entries = await list_merged_for_plan(db, clinic_id, plan.id)
        plan_notes = [e for e in entries if e["source"] == "plan"]
        by_item: dict[UUID, list[dict]] = {}
        for e in entries:
            if e["source"] == "plan":
                continue
            pid = e.get("plan_item_id")
            if pid is None:
                continue
            by_item.setdefault(pid, []).append(e)

        treatment_groups = []
        for item in items:
            treatment = treatments_by_id.get(item.treatment_id)
            label = None
            teeth: list[int] = []
            if treatment:
                label = (
                    _resolve_label(
                        treatment.catalog_item.names if treatment.catalog_item else None,
                    )
                    or treatment.clinical_type
                )
                teeth = [t.tooth_number for t in (treatment.teeth or [])]
            treatment_groups.append(
                {
                    "plan_item": {
                        "id": item.id,
                        "treatment_id": item.treatment_id,
                        "sequence_order": item.sequence_order,
                        "status": item.status,
                        "label": label,
                        "teeth": teeth,
                    },
                    "notes": by_item.get(item.id, []),
                }
            )

        groups.append(
            {
                "plan": {
                    "id": plan.id,
                    "plan_number": plan.plan_number,
                    "title": plan.title,
                    "status": plan.status,
                    "created_at": plan.created_at,
                },
                "plan_notes": plan_notes,
                "treatments": treatment_groups,
            }
        )
    return groups
