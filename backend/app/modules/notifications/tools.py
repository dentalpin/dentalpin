"""Agent tools for the notifications module.

Thin wrapper over :class:`NotificationGateway` — no business logic here.
``send_notification`` enqueues through the same consent + channel-resolution
path as every other producer (it never bypasses ``do_not_contact`` or clinic
settings). Structured params only, so it stays cloud-eligible under redaction.
See ``docs/technical/copilot-agentic-architecture.md`` §3.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.agents import AgentContext, Tool, ToolCategory

from .channels import Channel
from .gateway import NotificationGateway
from .models import NotificationType


class SendNotificationArgs(BaseModel):
    patient_id: UUID
    notification_type: NotificationType = Field(description="Tipo de notificación.")
    channel: Channel | None = Field(
        default=None,
        description="Canal forzado (email / whatsapp). None = automático con fallback.",
    )
    context: dict[str, str] = Field(
        default_factory=dict,
        description="Variables adicionales de plantilla (p. ej. fecha de la cita).",
    )


async def _send_notification(ctx: AgentContext, params: SendNotificationArgs) -> dict:
    from app.modules.patients.models import Patient

    patient = (
        await ctx.db.execute(
            select(Patient).where(
                Patient.clinic_id == ctx.clinic_id, Patient.id == params.patient_id
            )
        )
    ).scalar_one_or_none()
    if patient is None:
        return {"error": "patient_not_found"}

    context = dict(params.context)
    context.setdefault("patient_name", f"{patient.first_name} {patient.last_name}")

    msg = await NotificationGateway.enqueue(
        ctx.db,
        ctx.clinic_id,
        params.notification_type,
        context=context,
        patient_id=params.patient_id,
        channels=[params.channel.value] if params.channel else None,
        triggered_by_user_id=ctx.supervisor_id,
    )
    if msg is None:
        return {"status": "duplicate_skipped"}
    return {
        "message_id": msg.id,
        "channel": msg.channel,
        "status": msg.status,
        "error_message": msg.error_message,
    }


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="send_notification",
            description=(
                "Encolar una notificación a un paciente por su canal preferido "
                "(email / WhatsApp), con fallback a email. Respeta el "
                "consentimiento del paciente (do_not_contact) y la configuración "
                "de la clínica. La entrega es asíncrona (cola de salida)."
            ),
            parameters=SendNotificationArgs,
            handler=_send_notification,
            permissions=["notifications.send"],
            category=ToolCategory.WRITE,
        ),
    ]
