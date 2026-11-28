"""Map ``appointment`` → :class:`agenda.Appointment`.

Field mapping from `CanonicalAppointment` (DPMF v0.1):

| DPMF                | DentalPin                                |
|---------------------|------------------------------------------|
| patient_uuid        | patient_id (via resolver)                |
| professional_uuid   | professional_id (via resolver)           |
| scheduled_date+time | start_time (combined, UTC)               |
| duration_minutes    | end_time = start + duration              |
| coarse_status       | status (mapped to agenda enum)           |
| notes               | ClinicalNote(note_type='appointment_administrative', owner_type='appointment') |
| chair_uuid          | cabinet_id — resolved via CatalogItemMapper kind=chair |

Notes routing follows the pattern established by
:class:`AppliedTreatmentMapper` for non-clinical ``TtosMed`` rows
(commit ``191c884``): when ``payload.notes`` is non-empty the importer
creates a polymorphic :class:`ClinicalNote` row with
``owner_type='appointment'`` and ``note_type='appointment_administrative'``
(the safe default for legacy Gesdén notes, which usually carry
reception-level memos). Idempotency is tracked under the
``appointment_note`` entity_type so re-runs do not duplicate.

Skips with a warning when the source row is unusable: missing patient,
missing professional, or no schedule (date/time null). Re-running the
job is safe because the resolver lookup short-circuits.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.modules.agenda.service import AppointmentService
from app.modules.clinical_notes.models import ClinicalNote

from ..models import ImportWarning
from .base import MapperContext

logger = logging.getLogger(__name__)

_STATUS_MAP: dict[str, str] = {
    "scheduled": "scheduled",
    "confirmed": "confirmed",
    "attended": "completed",
    "no_show": "no_show",
    "cancelled": "cancelled",
    "unknown": "scheduled",
}

_DEFAULT_DURATION_MIN = 30


class AppointmentMapper:
    async def apply(
        self,
        ctx: MapperContext,
        *,
        entity_type: str,
        payload: dict[str, Any],
        raw: dict[str, Any],
        canonical_uuid: str,
        source_id: str,
        source_system: str,
    ) -> UUID | None:
        existing = await ctx.resolver.get("appointment", canonical_uuid)
        if existing is not None:
            return existing

        patient_uuid = payload.get("patient_uuid")
        professional_uuid = payload.get("professional_uuid")
        if not patient_uuid or not professional_uuid:
            await _warn(
                ctx,
                source_id,
                "appointment.missing_actor",
                "Cita omitida: paciente o profesional sin UUID en origen.",
            )
            return None

        patient_id = await ctx.resolver.get("patient", str(patient_uuid))
        professional_id = await ctx.resolver.get("professional", str(professional_uuid))
        if patient_id is None or professional_id is None:
            await _warn(
                ctx,
                source_id,
                "appointment.unmapped_actor",
                (
                    "Cita omitida: paciente o profesional no encontrado en mappings "
                    "previos (entidad fuera de scope o aún no importada)."
                ),
            )
            return None

        scheduled_date = payload.get("scheduled_date")
        scheduled_time = payload.get("scheduled_time")
        if not scheduled_date or not scheduled_time:
            await _warn(
                ctx,
                source_id,
                "appointment.no_schedule",
                "Cita omitida: sin fecha u hora programada en origen.",
            )
            return None

        try:
            start_dt = datetime.fromisoformat(f"{scheduled_date}T{scheduled_time}")
        except (TypeError, ValueError):
            await _warn(
                ctx,
                source_id,
                "appointment.unparseable_datetime",
                f"Cita omitida: fecha/hora no parseable ({scheduled_date} {scheduled_time}).",
            )
            return None
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=UTC)

        duration = payload.get("duration_minutes") or _DEFAULT_DURATION_MIN
        end_dt = start_dt + timedelta(minutes=int(duration))

        status = _STATUS_MAP.get((payload.get("coarse_status") or "unknown").lower(), "scheduled")

        # Cabinet (Gesdén ``TBoxes``) — landed earlier by the
        # ``catalog_item`` mapper. Missing chair_uuid is fine: the
        # cabinet is optional on the model and the operator can
        # assign one later on the kanban board.
        chair_uuid = payload.get("chair_uuid")
        cabinet_id = await ctx.resolver.get("catalog_item", str(chair_uuid)) if chair_uuid else None

        data: dict[str, Any] = {
            "patient_id": patient_id,
            "professional_id": professional_id,
            "start_time": start_dt,
            "end_time": end_dt,
            "status": status,
            "cabinet_id": cabinet_id,
        }
        data = {k: v for k, v in data.items() if v is not None}

        # History replay: the chair may map to a cabinet that is inactive
        # today; the appointment still belongs there (#1237).
        appointment = await AppointmentService.create_appointment(
            ctx.db,
            ctx.clinic_id,
            data,
            created_by=ctx.created_by,
            allow_inactive_cabinet=True,
        )
        await ctx.resolver.set(
            entity_type="appointment",
            canonical_uuid=canonical_uuid,
            source_system=source_system,
            dentalpin_table="appointments",
            dentalpin_id=appointment.id,
        )

        await _maybe_record_appointment_note(
            ctx,
            payload=payload,
            appointment_id=appointment.id,
            appointment_created_at=appointment.created_at or start_dt,
            professional_id=professional_id,
            canonical_uuid=canonical_uuid,
            source_system=source_system,
        )

        return appointment.id


async def _maybe_record_appointment_note(
    ctx: MapperContext,
    *,
    payload: dict[str, Any],
    appointment_id: UUID,
    appointment_created_at: datetime,
    professional_id: UUID,
    canonical_uuid: str,
    source_system: str,
) -> None:
    """Mirror legacy free-text ``notes`` into a polymorphic ClinicalNote.

    Default ``note_type='appointment_administrative'`` — Gesdén stores
    reception-style memos on appointments more often than clinical ones.
    Idempotent: the side-effect is tracked under the synthetic
    ``appointment_note`` entity_type so re-running execute is a no-op.
    """
    body = (payload.get("notes") or "").strip()
    note_canonical = f"{canonical_uuid}:note"

    if not body:
        await ctx.resolver.mark_skipped("appointment_note", note_canonical, source_system)
        return

    if await ctx.resolver.was_skipped("appointment_note", note_canonical):
        return
    if await ctx.resolver.get("appointment_note", note_canonical) is not None:
        return

    note = ClinicalNote(
        clinic_id=ctx.clinic_id,
        note_type="appointment_administrative",
        owner_type="appointment",
        owner_id=appointment_id,
        tooth_number=None,
        body=body,
        author_id=professional_id or ctx.created_by,
        created_at=appointment_created_at,
        updated_at=appointment_created_at,
    )
    ctx.db.add(note)
    await ctx.db.flush()

    await ctx.resolver.set(
        entity_type="appointment_note",
        canonical_uuid=note_canonical,
        source_system=source_system,
        dentalpin_table="clinical_notes",
        dentalpin_id=note.id,
    )


async def _warn(ctx: MapperContext, source_id: str, code: str, message: str) -> None:
    ctx.db.add(
        ImportWarning(
            job_id=ctx.job_id,
            entity_type="appointment",
            source_id=source_id,
            severity="warn",
            code=code,
            message=message,
        )
    )
