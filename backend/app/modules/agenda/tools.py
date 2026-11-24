"""Agent tools for the agenda module.

Thin wrappers over :class:`AppointmentService` — no business logic here.
Every tool filters by ``ctx.clinic_id`` and declares the same RBAC string
as the HTTP routes. Write tools accept ``ctx.supervisor_id`` (the human
in the loop) as the acting user for audit columns. See
``docs/technical/copilot-agentic-architecture.md`` §3.

Availability is intentionally absent here: open-hours computation lives
in the ``schedules`` module (``schedules.get_availability``). Agenda does
not reach across that boundary; the agent combines that tool with
``get_day_overview`` to find a free gap.
"""

from __future__ import annotations

from datetime import date as date_cls
from datetime import datetime, time
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.core.agents import AgentContext, Tool, ToolCategory

from .kanban_service import _fetch_professionals
from .service import (
    VALID_TRANSITIONS,
    AlreadyInStateError,
    AppointmentService,
    CabinetRequiredError,
    CabinetService,
    InvalidTransitionError,
)
from .tz import get_clinic_tz


class DayOverviewArgs(BaseModel):
    date: date_cls = Field(description="Día a consultar (YYYY-MM-DD).")


class GetAppointmentArgs(BaseModel):
    appointment_id: UUID


class NoArgs(BaseModel):
    pass


class BookAppointmentArgs(BaseModel):
    patient_id: UUID
    professional_id: UUID
    start_time: datetime
    end_time: datetime
    cabinet: str | None = Field(default=None, max_length=50)


class CancelAppointmentArgs(BaseModel):
    appointment_id: UUID


class RescheduleAppointmentArgs(BaseModel):
    appointment_id: UUID
    start_time: datetime
    end_time: datetime
    professional_id: UUID | None = None
    cabinet: str | None = Field(default=None, max_length=50)


class UpdateAppointmentStatusArgs(BaseModel):
    appointment_id: UUID
    to_status: Literal["confirmed", "checked_in", "in_treatment", "completed", "no_show"] = Field(
        description="Nuevo estado. Para cancelar usa cancel_appointment."
    )
    note: str | None = Field(default=None, max_length=500)


def _appt_summary(appt, tz: ZoneInfo) -> dict:
    """Times in the clinic timezone, like the REST router (#161, #1104)."""
    patient = appt.patient
    return {
        "id": appt.id,
        "patient_id": appt.patient_id,
        "patient_name": f"{patient.first_name} {patient.last_name}" if patient else None,
        "professional_id": appt.professional_id,
        "start_time": appt.start_time.astimezone(tz),
        "end_time": appt.end_time.astimezone(tz),
        "status": appt.status,
        "cabinet": appt.cabinet,
    }


async def _get_appointment(ctx: AgentContext, params: GetAppointmentArgs) -> dict:
    appt = await AppointmentService.get_appointment(ctx.db, ctx.clinic_id, params.appointment_id)
    if appt is None:
        return {"error": "not_found"}
    return _appt_summary(appt, await get_clinic_tz(ctx.db, ctx.clinic_id))


async def _list_cabinets(ctx: AgentContext, params: NoArgs) -> dict:
    cabinets = await CabinetService.list_cabinets(ctx.db, ctx.clinic_id)
    return {"cabinets": [{"id": c.id, "name": c.name, "is_active": c.is_active} for c in cabinets]}


async def _list_professionals(ctx: AgentContext, params: NoArgs) -> dict:
    rows = await _fetch_professionals(ctx.db, ctx.clinic_id)
    # ``professional_name`` is deliberately outside the redactor's PII key
    # set: staff names are not patient PHI, and the agent must be able to
    # resolve "Dr. Pérez" → id (impossible if the name is tokenized).
    return {
        "professionals": [
            {"id": pid, "professional_name": f"{first} {last}"} for pid, first, last in rows
        ]
    }


async def _get_day_overview(ctx: AgentContext, params: DayOverviewArgs) -> dict:
    # Naive bounds — list_appointments interprets them as clinic-local
    # wall-clock (issue #161), so "the day" matches the clinic, not UTC.
    start = datetime.combine(params.date, time.min)
    end = datetime.combine(params.date, time.max)
    items, total = await AppointmentService.list_appointments(
        ctx.db, ctx.clinic_id, start_date=start, end_date=end
    )
    tz = await get_clinic_tz(ctx.db, ctx.clinic_id)
    return {
        "date": params.date,
        "total": total,
        "appointments": [_appt_summary(a, tz) for a in items],
    }


async def _book_appointment(ctx: AgentContext, params: BookAppointmentArgs) -> dict:
    try:
        appt = await AppointmentService.create_appointment(
            ctx.db,
            ctx.clinic_id,
            params.model_dump(exclude_none=True),
            created_by=ctx.supervisor_id,
        )
    except IntegrityError:
        # Slot conflict. Roll back the failed insert so the session stays
        # usable for the rest of the turn; surface a structured error the
        # model can explain instead of a raw 500.
        await ctx.db.rollback()
        return {"error": "slot_conflict", "detail": "El hueco solicitado no está disponible."}
    tz = await get_clinic_tz(ctx.db, ctx.clinic_id)
    return {"id": appt.id, "start_time": appt.start_time.astimezone(tz), "status": appt.status}


async def _reschedule_appointment(ctx: AgentContext, params: RescheduleAppointmentArgs) -> dict:
    appt = await AppointmentService.get_appointment(ctx.db, ctx.clinic_id, params.appointment_id)
    if appt is None:
        return {"error": "not_found"}
    data = params.model_dump(exclude_none=True)
    data.pop("appointment_id")
    try:
        appt = await AppointmentService.update_appointment(
            ctx.db, appt, data, changed_by=ctx.supervisor_id
        )
    except IntegrityError:
        # update_appointment already rolled the session back.
        return {"error": "slot_conflict", "detail": "El hueco solicitado no está disponible."}
    return _appt_summary(appt, await get_clinic_tz(ctx.db, ctx.clinic_id))


async def _update_appointment_status(
    ctx: AgentContext, params: UpdateAppointmentStatusArgs
) -> dict:
    appt = await AppointmentService.get_appointment(ctx.db, ctx.clinic_id, params.appointment_id)
    if appt is None:
        return {"error": "not_found"}
    try:
        appt = await AppointmentService.transition(
            ctx.db, appt, params.to_status, changed_by=ctx.supervisor_id, note=params.note
        )
    except AlreadyInStateError:
        return {"error": "already_in_state", "status": appt.status}
    except InvalidTransitionError:
        return {
            "error": "invalid_transition",
            "status": appt.status,
            "allowed": sorted(VALID_TRANSITIONS.get(appt.status, set())),
        }
    except CabinetRequiredError:
        return {
            "error": "cabinet_required",
            "detail": "Asigna un gabinete antes de pasar la cita a 'in_treatment'.",
        }
    return {"id": appt.id, "status": appt.status}


async def _cancel_appointment(ctx: AgentContext, params: CancelAppointmentArgs) -> dict:
    appt = await AppointmentService.get_appointment(ctx.db, ctx.clinic_id, params.appointment_id)
    if appt is None:
        return {"error": "not_found"}
    try:
        appt = await AppointmentService.cancel_appointment(
            ctx.db, appt, changed_by=ctx.supervisor_id
        )
    except InvalidTransitionError:
        return {
            "error": "not_cancellable",
            "detail": f"Una cita en estado '{appt.status}' no se puede cancelar.",
        }
    return {"id": appt.id, "status": appt.status}


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="get_day_overview",
            description="Listar las citas de la clínica para un día concreto.",
            parameters=DayOverviewArgs,
            handler=_get_day_overview,
            permissions=["agenda.appointments.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="get_appointment",
            description="Obtener los datos de una cita por su id.",
            parameters=GetAppointmentArgs,
            handler=_get_appointment,
            permissions=["agenda.appointments.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="list_cabinets",
            description="Listar los gabinetes/sillones de la clínica.",
            parameters=NoArgs,
            handler=_list_cabinets,
            permissions=["agenda.cabinets.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="list_professionals",
            description="Listar los profesionales (dentistas/higienistas) de la clínica con su id.",
            parameters=NoArgs,
            handler=_list_professionals,
            permissions=["agenda.appointments.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="book_appointment",
            description="Reservar una cita. Requiere confirmación del usuario.",
            parameters=BookAppointmentArgs,
            handler=_book_appointment,
            permissions=["agenda.appointments.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="reschedule_appointment",
            description=(
                "Mover una cita existente a otra fecha/hora (y opcionalmente "
                "otro profesional o gabinete). Requiere confirmación del usuario."
            ),
            parameters=RescheduleAppointmentArgs,
            handler=_reschedule_appointment,
            permissions=["agenda.appointments.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="update_appointment_status",
            description=(
                "Cambiar el estado de una cita (confirmed, checked_in, "
                "in_treatment, completed, no_show). Para cancelar usa "
                "cancel_appointment. Requiere confirmación del usuario."
            ),
            parameters=UpdateAppointmentStatusArgs,
            handler=_update_appointment_status,
            permissions=["agenda.appointments.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="cancel_appointment",
            description="Cancelar una cita existente. Acción destructiva: requiere confirmación.",
            parameters=CancelAppointmentArgs,
            handler=_cancel_appointment,
            permissions=["agenda.appointments.write"],
            category=ToolCategory.DESTRUCTIVE,
        ),
    ]
