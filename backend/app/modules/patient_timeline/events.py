"""Event handlers for the patient_timeline module.

Every handler follows the same contract:

- Signature ``async def on_*(data: dict) -> None`` — matches the event bus
  calling convention (``handler(data)``).
- Opens its own DB session via :func:`async_session_maker`, commits on
  success and rolls back on failure — deliberately own-session (ADR 0019,
  audited in issue #183): the timeline is a log and must never be able to
  fail the event it is logging.
- Never imports models from other modules. Everything it needs must come in
  the ``data`` dict. Keeps the timeline module removable in isolation — the
  whole point of the patient_timeline split in Fase B.3.
- Skips events without a ``patient_id`` (administrative/clinic-scoped events
  have nowhere to land in the ficha del paciente).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.events import EventType
from app.database import async_session_maker

from .service import TimelineService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_dt(value: Any) -> datetime:
    """Parse an ISO timestamp; fall back to now if missing/invalid."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(UTC)


def _required_ids(data: dict, *keys: str) -> tuple[UUID, ...] | None:
    """Return tuple of UUIDs for the given keys, or None if any are missing/invalid."""
    try:
        return tuple(UUID(data[k]) for k in keys)
    except (KeyError, TypeError, ValueError):
        return None


async def _record(
    event_type: str,
    event_category: str,
    source_table: str,
    data: dict,
    *,
    source_id_key: str,
    title: str,
    description: str | None = None,
    event_data: dict | None = None,
    occurred_at_key: str = "occurred_at",
    created_by_key: str | None = None,
) -> None:
    """Generic helper: insert one timeline row and commit.

    Centralizes session management + error handling so each specific handler
    stays declarative.

    own-session (issue #183): every handler in this module is payload-only —
    the timeline records what the payload says happened and never re-reads
    the publisher's rows, and ``source_id`` is polymorphic with no FK. The
    timeline is a log: it must not be able to fail the thing it is logging.
    """
    ids = _required_ids(data, "clinic_id", "patient_id", source_id_key)
    if ids is None:
        # Not enough info to attach to a patient — silently skip. These events
        # are valid at the clinic level (e.g. admin emails without a patient)
        # and simply don't belong on any single ficha.
        return
    clinic_id, patient_id, source_id = ids

    created_by: UUID | None = None
    if created_by_key and data.get(created_by_key):
        try:
            created_by = UUID(data[created_by_key])
        except (TypeError, ValueError):
            created_by = None

    async with async_session_maker() as db:
        try:
            await TimelineService.add_entry(
                db=db,
                clinic_id=clinic_id,
                patient_id=patient_id,
                event_type=event_type,
                event_category=event_category,
                source_table=source_table,
                source_id=source_id,
                title=title,
                description=description,
                event_data=event_data,
                occurred_at=_parse_dt(data.get(occurred_at_key)),
                created_by=created_by,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("patient_timeline: failed to record %s", event_type)


# ---------------------------------------------------------------------------
# Visits
# ---------------------------------------------------------------------------


async def on_appointment_scheduled(data: dict) -> None:
    treatment = data.get("treatment_type") or "Consulta"
    await _record(
        event_type=EventType.APPOINTMENT_SCHEDULED,
        event_category="visit",
        source_table="appointments",
        data=data,
        source_id_key="appointment_id",
        title=f"Cita programada: {treatment}",
        event_data={
            "cabinet": data.get("cabinet"),
            "professional_id": data.get("professional_id"),
            "start_time": data.get("start_time"),
        },
        occurred_at_key="start_time",
    )


async def on_appointment_completed(data: dict) -> None:
    treatment = data.get("treatment_type") or "Consulta"
    await _record(
        event_type=EventType.APPOINTMENT_COMPLETED,
        event_category="visit",
        source_table="appointments",
        data=data,
        source_id_key="appointment_id",
        title=f"Cita completada: {treatment}",
        description=data.get("notes"),
        event_data={
            "cabinet": data.get("cabinet"),
            "professional_id": data.get("professional_id"),
        },
        occurred_at_key="end_time",
    )


async def on_appointment_cancelled(data: dict) -> None:
    treatment = data.get("treatment_type") or "Consulta"
    await _record(
        event_type=EventType.APPOINTMENT_CANCELLED,
        event_category="visit",
        source_table="appointments",
        data=data,
        source_id_key="appointment_id",
        title=f"Cita cancelada: {treatment}",
        event_data={"professional_id": data.get("professional_id")},
    )


async def on_appointment_no_show(data: dict) -> None:
    treatment = data.get("treatment_type") or "Consulta"
    await _record(
        event_type=EventType.APPOINTMENT_NO_SHOW,
        event_category="visit",
        source_table="appointments",
        data=data,
        source_id_key="appointment_id",
        title=f"Paciente no asistió: {treatment}",
        event_data={
            "cabinet": data.get("cabinet"),
            "professional_id": data.get("professional_id"),
        },
        occurred_at_key="start_time",
    )


async def on_appointment_confirmed(data: dict) -> None:
    treatment = data.get("treatment_type") or "Consulta"
    await _record(
        event_type=EventType.APPOINTMENT_CONFIRMED,
        event_category="visit",
        source_table="appointments",
        data=data,
        source_id_key="appointment_id",
        title=f"Cita confirmada: {treatment}",
        event_data={"professional_id": data.get("professional_id")},
        occurred_at_key="changed_at",
        created_by_key="changed_by",
    )


async def on_appointment_checked_in(data: dict) -> None:
    treatment = data.get("treatment_type") or "Consulta"
    await _record(
        event_type=EventType.APPOINTMENT_CHECKED_IN,
        event_category="visit",
        source_table="appointments",
        data=data,
        source_id_key="appointment_id",
        title=f"Paciente llegó a la clínica ({treatment})",
        event_data={
            "cabinet": data.get("cabinet"),
            "professional_id": data.get("professional_id"),
        },
        occurred_at_key="changed_at",
        created_by_key="changed_by",
    )


async def on_appointment_in_treatment(data: dict) -> None:
    treatment = data.get("treatment_type") or "Consulta"
    await _record(
        event_type=EventType.APPOINTMENT_IN_TREATMENT,
        event_category="visit",
        source_table="appointments",
        data=data,
        source_id_key="appointment_id",
        title=f"Paciente en gabinete ({treatment})",
        event_data={
            "cabinet": data.get("cabinet"),
            "professional_id": data.get("professional_id"),
        },
        occurred_at_key="changed_at",
        created_by_key="changed_by",
    )


# ---------------------------------------------------------------------------
# Treatments
# ---------------------------------------------------------------------------


async def on_tooth_treatment_performed(data: dict) -> None:
    name = data.get("treatment_name") or data.get("clinical_type") or "tratamiento"
    teeth = data.get("tooth_numbers") or []
    teeth_label = ", ".join(str(t) for t in teeth) if teeth else None
    await _record(
        event_type=EventType.ODONTOGRAM_TREATMENT_PERFORMED,
        event_category="treatment",
        source_table="treatments",
        data=data,
        source_id_key="treatment_id",
        title=f"Tratamiento realizado: {name}",
        description=f"Dientes: {teeth_label}" if teeth_label else None,
        event_data={
            "clinical_type": data.get("clinical_type"),
            "tooth_numbers": teeth,
        },
        occurred_at_key="performed_at",
        created_by_key="performed_by",
    )


async def on_plan_created(data: dict) -> None:
    plan_name = data.get("plan_name") or f"Plan {data.get('plan_number', '')}".strip()
    await _record(
        event_type=EventType.TREATMENT_PLAN_CREATED,
        event_category="treatment",
        source_table="treatment_plans",
        data=data,
        source_id_key="plan_id",
        title=f"Plan de tratamiento creado: {plan_name}"
        if plan_name
        else "Plan de tratamiento creado",
        event_data={"plan_number": data.get("plan_number")},
        created_by_key="created_by",
    )


async def on_plan_item_completed(data: dict) -> None:
    item_name = data.get("item_name")
    title = (
        f"Tratamiento del plan completado: {item_name}"
        if item_name
        else "Tratamiento del plan completado"
    )
    await _record(
        event_type=EventType.TREATMENT_PLAN_TREATMENT_COMPLETED,
        event_category="treatment",
        source_table="planned_treatment_items",
        data=data,
        source_id_key="item_id",
        title=title,
        event_data={"plan_id": data.get("plan_id")},
        created_by_key="completed_by",
    )


# ---------------------------------------------------------------------------
# Financial
# ---------------------------------------------------------------------------


async def on_budget_sent(data: dict) -> None:
    number = data.get("budget_number")
    await _record(
        event_type=EventType.BUDGET_SENT,
        event_category="financial",
        source_table="budgets",
        data=data,
        source_id_key="budget_id",
        title=f"Presupuesto enviado: {number}" if number else "Presupuesto enviado",
        event_data={
            "budget_number": number,
            "total": data.get("total"),
            "send_method": data.get("send_method"),
        },
    )


async def on_budget_accepted(data: dict) -> None:
    number = data.get("budget_number")
    await _record(
        event_type=EventType.BUDGET_ACCEPTED,
        event_category="financial",
        source_table="budgets",
        data=data,
        source_id_key="budget_id",
        title=f"Presupuesto aceptado: {number}" if number else "Presupuesto aceptado",
        event_data={
            "budget_number": number,
            "total": data.get("total"),
            "accepted_via": data.get("accepted_via"),
        },
    )


async def on_budget_rejected(data: dict) -> None:
    number = data.get("budget_number")
    await _record(
        event_type=EventType.BUDGET_REJECTED,
        event_category="financial",
        source_table="budgets",
        data=data,
        source_id_key="budget_id",
        title=f"Presupuesto rechazado: {number}" if number else "Presupuesto rechazado",
        event_data={
            "budget_number": number,
            "rejection_reason": data.get("rejection_reason"),
            "rejection_note": data.get("rejection_note"),
        },
    )


async def on_budget_expired(data: dict) -> None:
    number = data.get("budget_number")
    await _record(
        event_type=EventType.BUDGET_EXPIRED,
        event_category="financial",
        source_table="budgets",
        data=data,
        source_id_key="budget_id",
        title=f"Presupuesto caducado: {number}" if number else "Presupuesto caducado",
        event_data={
            "budget_number": number,
            "days_overdue": data.get("days_overdue"),
        },
    )


async def on_budget_renegotiated(data: dict) -> None:
    await _record(
        event_type=EventType.BUDGET_RENEGOTIATED,
        event_category="financial",
        source_table="budgets",
        data=data,
        source_id_key="budget_id",
        title="Presupuesto en renegociación",
        event_data={"plan_id": data.get("plan_id")},
    )


async def on_budget_viewed(data: dict) -> None:
    await _record(
        event_type=EventType.BUDGET_VIEWED,
        event_category="financial",
        source_table="budgets",
        data=data,
        source_id_key="budget_id",
        title="Presupuesto visto por el paciente",
        occurred_at_key="viewed_at",
    )


async def on_budget_reminder_sent(data: dict) -> None:
    milestone = data.get("milestone_days")
    await _record(
        event_type=EventType.BUDGET_REMINDER_SENT,
        event_category="financial",
        source_table="budgets",
        data=data,
        source_id_key="budget_id",
        title=(f"Recordatorio enviado ({milestone}d)" if milestone else "Recordatorio enviado"),
        occurred_at_key="sent_at",
        event_data={"milestone_days": milestone},
    )


async def on_treatment_plan_confirmed(data: dict) -> None:
    plan_number = data.get("plan_number")
    await _record(
        event_type=EventType.TREATMENT_PLAN_CONFIRMED,
        event_category="treatment",
        source_table="treatment_plans",
        data=data,
        source_id_key="plan_id",
        title=(f"Plan confirmado: {plan_number}" if plan_number else "Plan confirmado"),
        occurred_at_key="confirmed_at",
        created_by_key="confirmed_by_user_id",
        event_data={
            "plan_number": plan_number,
            "total_estimated": data.get("total_estimated"),
        },
    )


async def on_treatment_plan_closed(data: dict) -> None:
    reason = data.get("closure_reason") or "other"
    await _record(
        event_type=EventType.TREATMENT_PLAN_CLOSED,
        event_category="treatment",
        source_table="treatment_plans",
        data=data,
        source_id_key="plan_id",
        title=f"Plan cerrado ({reason})",
        occurred_at_key="closed_at",
        created_by_key="closed_by_user_id",
        event_data={
            "closure_reason": reason,
            "closure_note": data.get("closure_note"),
            "previous_status": data.get("previous_status"),
        },
    )


async def on_treatment_plan_reactivated(data: dict) -> None:
    await _record(
        event_type=EventType.TREATMENT_PLAN_REACTIVATED,
        event_category="treatment",
        source_table="treatment_plans",
        data=data,
        source_id_key="plan_id",
        title="Plan reactivado",
        occurred_at_key="reactivated_at",
        created_by_key="reactivated_by_user_id",
        event_data={
            "previous_closure_reason": data.get("previous_closure_reason"),
        },
    )


async def on_invoice_issued(data: dict) -> None:
    number = data.get("invoice_number")
    await _record(
        event_type=EventType.INVOICE_ISSUED,
        event_category="financial",
        source_table="invoices",
        data=data,
        source_id_key="invoice_id",
        title=f"Factura emitida: {number}" if number else "Factura emitida",
        event_data={"invoice_number": number, "total": data.get("total")},
    )


async def on_invoice_paid(data: dict) -> None:
    number = data.get("invoice_number")
    await _record(
        event_type=EventType.INVOICE_PAID,
        event_category="financial",
        source_table="invoices",
        data=data,
        source_id_key="invoice_id",
        title=f"Factura pagada: {number}" if number else "Factura pagada",
        event_data={"invoice_number": number, "total": data.get("total")},
    )


# ---------------------------------------------------------------------------
# Communications
# ---------------------------------------------------------------------------


# Human labels for the outbound channels the gateway publishes. Anything
# unknown falls back to a generic "Mensaje" so a future channel still lands
# on the timeline without a code change here.
_CHANNEL_LABELS = {"email": "Email", "whatsapp": "WhatsApp"}


def _channel_label(data: dict) -> str:
    channel = data.get("channel") or ""
    return _CHANNEL_LABELS.get(channel, "Mensaje")


async def on_notification_sent(data: dict) -> None:
    """Record any outbound send (every channel) from ``notification.sent``.

    Replaces the legacy ``email.sent`` subscription: the gateway publishes
    the generic event for email AND WhatsApp, so subscribing to both would
    double-record email sends (issue #287 bug 12).
    """
    subject = data.get("subject") or data.get("template_key") or "mensaje"
    await _record(
        event_type=EventType.NOTIFICATION_SENT,
        event_category="communication",
        source_table="communication_messages",
        data=data,
        source_id_key="message_id",
        title=f"{_channel_label(data)} enviado: {subject}",
        event_data={
            "channel": data.get("channel"),
            "template_key": data.get("template_key"),
        },
    )


async def on_notification_reply_received(data: dict) -> None:
    await _record(
        event_type=EventType.NOTIFICATION_REPLY_RECEIVED,
        event_category="communication",
        source_table="communication_messages",
        data=data,
        source_id_key="message_id",
        title="Respuesta recibida por WhatsApp",
        description=data.get("reply_text"),
        event_data={
            "channel": data.get("channel"),
            "from_address": data.get("from_address"),
        },
    )


async def on_notification_failed(data: dict) -> None:
    """Record a failed outbound send (every channel) from ``notification.failed``."""
    subject = data.get("subject") or data.get("template_key") or "mensaje"
    await _record(
        event_type=EventType.NOTIFICATION_FAILED,
        event_category="communication",
        source_table="communication_messages",
        data=data,
        source_id_key="message_id",
        title=f"{_channel_label(data)} fallido: {subject}",
        description=data.get("error_message"),
        event_data={
            "channel": data.get("channel"),
            "template_key": data.get("template_key"),
            "error_message": data.get("error_message"),
        },
    )


# ---------------------------------------------------------------------------
# Medical history
# ---------------------------------------------------------------------------


async def on_medical_updated(data: dict) -> None:
    # patient_timeline uses patient_id as the source_id for medical updates —
    # there is no per-update row to point to. Inject it so the generic helper
    # passes the required-ids check.
    data = {**data, "source_id": data.get("patient_id")}
    section = data.get("section")
    # The event_category badge already shows "Historial médico" and the
    # description carries the human summary — keep the title short and
    # avoid leaking internal section slugs like "history" / "context".
    title = data.get("summary") or "Historia clínica actualizada"
    await _record(
        event_type=EventType.PATIENT_MEDICAL_UPDATED,
        event_category="medical",
        source_table="patients",
        data=data,
        source_id_key="source_id",
        title=title,
        event_data={"section": section},
        created_by_key="user_id",
    )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


async def on_document_uploaded(data: dict) -> None:
    title = data.get("title") or "Documento"
    media_kind = data.get("media_kind") or "document"
    # Photos / X-rays get their own dedicated card via on_photo_uploaded.
    # Skip the generic document row to avoid duplicate timeline entries.
    if media_kind in ("photo", "xray"):
        return
    await _record(
        event_type=EventType.DOCUMENT_UPLOADED,
        event_category="document",
        source_table="documents",
        data=data,
        source_id_key="document_id",
        title=f"Documento: {title}",
        event_data={"document_type": data.get("document_type")},
    )


async def on_photo_uploaded(data: dict) -> None:
    """Photo / X-ray-aware variant — surfaces thumbnail-friendly metadata."""
    title = data.get("title") or "Foto"
    media_kind = data.get("media_kind") or "photo"
    category = data.get("media_category")
    subtype = data.get("media_subtype")
    label_kind = "Radiografía" if media_kind == "xray" else "Foto clínica"
    chip_parts = [label_kind]
    if subtype:
        chip_parts.append(subtype)
    elif category:
        chip_parts.append(category)
    await _record(
        event_type=EventType.PHOTO_UPLOADED,
        event_category="document",
        source_table="documents",
        data=data,
        source_id_key="document_id",
        title=f"{label_kind}: {title}",
        event_data={
            "media_kind": media_kind,
            "media_category": category,
            "media_subtype": subtype,
            "captured_at": data.get("captured_at"),
            "chip": " · ".join(chip_parts),
        },
        occurred_at_key="captured_at",
    )


async def on_pair_created(data: dict) -> None:
    await _record(
        event_type=EventType.PAIR_CREATED,
        event_category="document",
        source_table="documents",
        data=data,
        source_id_key="document_a_id",
        title="Comparativa antes/después creada",
        event_data={
            "document_a_id": data.get("document_a_id"),
            "document_b_id": data.get("document_b_id"),
        },
    )


# ---------------------------------------------------------------------------
# Clinical notes
# ---------------------------------------------------------------------------


_NOTE_TYPE_TITLES = {
    "administrative": "Nota administrativa",
    "diagnosis": "Nota de diagnóstico",
    "treatment": "Nota clínica en tratamiento",
    "treatment_plan": "Nota clínica en plan de tratamiento",
}


async def on_clinical_note_created(data: dict) -> None:
    """Record any clinical_notes-module note on the patient timeline.

    A single handler covers all four note_types (administrative, diagnosis,
    treatment, treatment_plan). The event_type field stays specific so the
    timeline UI can filter by note category.
    """
    event_type_str = f"clinical_notes.{data.get('note_type', 'note')}_created"
    note_type = data.get("note_type") or "note"
    title = _NOTE_TYPE_TITLES.get(note_type, "Nota clínica")
    tooth = data.get("tooth_number")
    if note_type == "diagnosis" and tooth:
        title = f"{title} (diente {tooth})"

    data = {**data, "source_id": data.get("note_id")}
    excerpt = data.get("body_excerpt") or ""
    await _record(
        event_type=event_type_str,
        event_category="note",
        source_table="clinical_notes",
        data=data,
        source_id_key="source_id",
        title=title,
        description=excerpt or None,
        event_data={
            "note_type": note_type,
            "owner_type": data.get("owner_type"),
            "owner_id": data.get("owner_id"),
            "tooth_number": tooth,
        },
        created_by_key="user_id",
    )


async def on_visit_note_updated(data: dict) -> None:
    """Record a visit-level clinical note (AppointmentTreatment.notes)."""
    data = {**data, "source_id": data.get("appointment_treatment_id")}
    excerpt = data.get("body_excerpt") or ""
    await _record(
        event_type=EventType.AGENDA_VISIT_NOTE_UPDATED,
        event_category="note",
        source_table="appointment_treatments",
        data=data,
        source_id_key="source_id",
        title="Nota clínica de visita",
        description=excerpt or None,
        event_data={
            "appointment_id": data.get("appointment_id"),
            "plan_item_id": data.get("plan_item_id"),
        },
        created_by_key="user_id",
    )


async def on_item_completed_without_note(data: dict) -> None:
    """Audit a plan-item completion where the clinician skipped the note."""
    data = {**data, "source_id": data.get("plan_item_id")}
    item_name = data.get("item_name") or "Tratamiento"
    await _record(
        event_type=EventType.TREATMENT_PLAN_ITEM_COMPLETED_WITHOUT_NOTE,
        event_category="treatment",
        source_table="planned_treatment_items",
        data=data,
        source_id_key="source_id",
        title=f"{item_name} completado sin nota",
        event_data={"plan_id": data.get("plan_id")},
        created_by_key="user_id",
    )
