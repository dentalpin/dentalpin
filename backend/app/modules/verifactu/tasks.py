"""APScheduler integration for Verifactu background jobs + event handlers.

The scheduler is owned by the host app at :mod:`app.core.scheduler`;
the module hands it the specs below via ``VerifactuModule.get_scheduled_jobs``
(only while installed — issue #91).

Jobs:

* ``verifactu_submissions`` — every 60 s, drain pending records and
  submit to AEAT.
* ``verifactu_stuck_reaper`` — every 5 min, demote records left in
  ``state='sending'`` for >10 min (worker crash recovery).
* ``verifactu_cert_expiry`` — daily at 08:00, alert clinic admins
  whose certificate expires in ≤30 days.

Event handlers:

* ``verifactu.record.rejected`` → email clinic admins about an AEAT
  rejection (throttled to 1 alert per clinic per 30 min). Subscribed via
  ``VerifactuModule.get_event_handlers``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.email import email_service
from app.core.scheduling import ScheduledJob
from app.database import async_session_maker

from .models import VerifactuSettings
from .services.submission_queue import process_all, reap_stuck_sending

logger = logging.getLogger(__name__)

JOB_ID_SUBMISSIONS = "verifactu_submissions"
JOB_ID_REAPER = "verifactu_stuck_reaper"
JOB_ID_CERT_CHECK = "verifactu_cert_expiry"

REJECTED_ALERT_THROTTLE = timedelta(minutes=30)


async def process_verifactu_submissions() -> None:
    """Periodic job: drain Verifactu queue across every enabled clinic."""

    counts = await process_all(async_session_maker)
    if counts:
        logger.info("verifactu: processed %s", counts)


async def reap_stuck_records() -> None:
    """Periodic job: rescue records stuck in ``state='sending'``."""

    await reap_stuck_sending(async_session_maker)


async def daily_cert_check() -> None:
    """Daily job: alert clinic admins about certificates expiring soon."""

    from .services.cert_expiry import check_expiring_certs

    await check_expiring_certs(async_session_maker)


def scheduled_jobs() -> list[ScheduledJob]:
    """Specs for :meth:`VerifactuModule.get_scheduled_jobs`."""

    return [
        ScheduledJob(
            id=JOB_ID_SUBMISSIONS,
            func=process_verifactu_submissions,
            trigger="interval",
            trigger_args={"seconds": 60},
            name="Drain Verifactu submission queue",
        ),
        ScheduledJob(
            id=JOB_ID_REAPER,
            func=reap_stuck_records,
            trigger="interval",
            trigger_args={"minutes": 5},
            name="Reap Verifactu records stuck in 'sending'",
        ),
        ScheduledJob(
            id=JOB_ID_CERT_CHECK,
            func=daily_cert_check,
            trigger="cron",
            trigger_args={"hour": 8, "minute": 0},
            name="Check Verifactu certificates expiring soon",
        ),
    ]


async def _admins_for(db, clinic_id: UUID) -> list[User]:
    result = await db.execute(
        select(User)
        .join(ClinicMembership, ClinicMembership.user_id == User.id)
        .where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.role == "admin",
            User.is_active.is_(True),
        )
    )
    return list(result.scalars())


async def _notify_rejected(payload: dict) -> None:
    """Email clinic admins about a rejected Verifactu record.

    Throttled per clinic to one email per
    :data:`REJECTED_ALERT_THROTTLE` (default 30 min). Otherwise a
    systemic issue (bad NIF, expired cert) processed in a single batch
    would email admins dozens of times in a row.
    """

    clinic_id_str = payload.get("clinic_id")
    if not clinic_id_str:
        return
    clinic_id = UUID(clinic_id_str)
    now = datetime.now(UTC)
    throttle_cutoff = now - REJECTED_ALERT_THROTTLE

    async with async_session_maker() as db:
        settings_q = await db.execute(
            select(VerifactuSettings)
            .where(VerifactuSettings.clinic_id == clinic_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        settings = settings_q.scalar_one_or_none()
        if (
            settings is not None
            and settings.last_rejected_alert_at is not None
            and settings.last_rejected_alert_at >= throttle_cutoff
        ):
            return

        clinic_q = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
        clinic = clinic_q.scalar_one_or_none()
        if clinic is None:
            return

        admins = await _admins_for(db, clinic_id)
        if not admins:
            return

        ctx_base = {
            "clinic_name": clinic.name,
            "invoice_number": payload.get("serie_numero") or "",
            "codigo_error": payload.get("codigo_error"),
            "friendly_message": payload.get("friendly_message")
            or payload.get("descripcion_error")
            or "Sin detalle.",
            "suggested_cta": payload.get("suggested_cta"),
            "field": payload.get("field"),
            "queue_url": None,  # filled at deploy time via env if needed
        }

        for admin in admins:
            ctx = dict(ctx_base, admin_name=admin.full_name)
            try:
                await email_service.send_templated(
                    to_email=admin.email,
                    to_name=admin.full_name,
                    template_key="verifactu_record_rejected",
                    context=ctx,
                    subject="Factura rechazada por AEAT — acción requerida",
                    locale="es",
                    db=db,
                    clinic_id=clinic_id,
                )
            except Exception:  # noqa: BLE001 — one admin failing must not block others
                logger.exception(
                    "verifactu rejected-alert: failed for admin %s clinic %s",
                    admin.id,
                    clinic_id,
                )

        if settings is not None:
            settings.last_rejected_alert_at = now
            await db.commit()


def on_rejected_event(payload: dict) -> None:
    """Bus adapter for ``verifactu.record.rejected`` — forwards to the async handler."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_notify_rejected(payload))
    except RuntimeError:
        asyncio.run(_notify_rejected(payload))
