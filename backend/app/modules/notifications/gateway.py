"""Multi-channel notification gateway: consent gate, channel resolution,
outbox enqueue, and the dispatch loop.

Our communications logic lives here; adapters (email, whatsapp_kapso, …) only
put a rendered message on the wire. ``enqueue`` never touches the network — it
persists a ``queued`` row and returns; the scheduled ``dispatch_outbox`` job
sends with retry/backoff.
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType, event_bus

from .channels import Channel, OutboundMessage, SendStatus, channel_registry
from .models import CommunicationMessage
from .service import NotificationService, resolve_clinic_communication_locale

logger = logging.getLogger(__name__)

_BACKOFF_CAP_SECONDS = 3600
_DISPATCH_BATCH = 50
_SESSION_WINDOW = timedelta(hours=24)


def _backoff_seconds(attempts: int) -> int:
    """Exponential backoff with cap: 1m, 2m, 4m, … ≤ 1h."""
    return min(60 * (2 ** max(0, attempts - 1)), _BACKOFF_CAP_SECONDS)


def _session_window_open(prefs) -> bool:
    """True when the patient's 24h free-form session window is still open
    (i.e. they sent us an inbound message less than 24h ago)."""
    last = getattr(prefs, "last_inbound_at", None) if prefs is not None else None
    if last is None:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return datetime.now(UTC) - last < _SESSION_WINDOW


def _sanitize(context: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in context.items() if k not in ("password", "token")}


class NotificationGateway:
    """Owns enqueue + dispatch for every channel."""

    # ------------------------------------------------------------------ enqueue
    @staticmethod
    async def enqueue(
        db: AsyncSession,
        clinic_id: UUID,
        notification_type: str,
        *,
        context: dict[str, Any],
        patient_id: UUID | None = None,
        to_address: str | None = None,
        channels: list[str] | None = None,
        force_send: bool = False,
        message_kind: str | None = None,
        body_text: str | None = None,
        triggered_by_event: str | None = None,
        triggered_by_user_id: UUID | None = None,
        dedup_key: str | None = None,
    ) -> CommunicationMessage | None:
        """Queue a notification for delivery.

        Returns the queued ``CommunicationMessage`` (status ``queued`` or
        ``skipped``), or ``None`` when a row with the same ``dedup_key``
        already exists (idempotent no-op).
        """
        # Idempotency: never double-enqueue the same logical message.
        if dedup_key:
            existing = await db.execute(
                select(CommunicationMessage.id).where(
                    CommunicationMessage.clinic_id == clinic_id,
                    CommunicationMessage.dedup_key == dedup_key,
                )
            )
            if existing.first():
                return None

        patient = await NotificationGateway._load_patient(db, clinic_id, patient_id)

        # Consent: do_not_contact is a hard block on every channel, even when
        # force_send is set (manual sends / agent tool never override it).
        if patient is not None and patient.do_not_contact:
            return await NotificationGateway._skip(
                db,
                clinic_id,
                notification_type,
                patient_id,
                to_address or (patient.email or ""),
                "do_not_contact",
                triggered_by_event,
                triggered_by_user_id,
            )

        # Clinic-level enable / auto_send + per-patient per-type opt-in.
        if not force_send:
            should, reason = await NotificationService.should_send_notification(
                db, clinic_id, notification_type, patient_id
            )
            if not should:
                return await NotificationGateway._skip(
                    db,
                    clinic_id,
                    notification_type,
                    patient_id,
                    to_address or (patient.email if patient else "") or "",
                    reason,
                    triggered_by_event,
                    triggered_by_user_id,
                )

        # Locale: clinic default → patient preference override.
        locale = await resolve_clinic_communication_locale(db, clinic_id)
        prefs = (
            await NotificationService.get_patient_preferences(db, clinic_id, patient_id)
            if patient_id
            else None
        )
        if prefs and prefs.preferred_locale:
            locale = prefs.preferred_locale

        # Channel resolution: first viable channel from the ordered list.
        requested = channels or await NotificationGateway._clinic_channels(
            db, clinic_id, notification_type
        )
        resolved = await NotificationGateway._resolve_channel(
            db,
            clinic_id,
            notification_type,
            patient,
            prefs,
            locale,
            requested,
            to_address,
            message_kind,
        )
        if resolved is None:
            return await NotificationGateway._skip(
                db,
                clinic_id,
                notification_type,
                patient_id,
                to_address or (patient.email if patient else "") or "",
                "no_viable_channel",
                triggered_by_event,
                triggered_by_user_id,
            )
        channel, addr, resolved_kind, _provider_template = resolved

        # Subject is resolved now (email) for the logs view; the body is
        # (re)rendered at dispatch time. Session (free-form) sends carry the
        # literal text in body_text and need no template.
        subject = None
        if resolved_kind == "template":
            template = await NotificationService.get_template(
                db, clinic_id, notification_type, locale, channel=channel.value
            )
            subject = template.subject if template else None

        msg = CommunicationMessage(
            clinic_id=clinic_id,
            channel=channel.value,
            to_address=addr,
            patient_id=patient_id,
            template_key=notification_type,
            message_kind=resolved_kind,
            subject=subject,
            body_text=body_text,
            status="queued",
            # stash the resolved locale so dispatch renders in the right language
            context_data=_sanitize({**context, "locale": locale}),
            triggered_by_event=triggered_by_event,
            triggered_by_user_id=triggered_by_user_id,
            dedup_key=dedup_key,
            next_attempt_at=datetime.now(UTC),
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        await NotificationGateway._publish(msg, EventType.NOTIFICATION_QUEUED)
        return msg

    # ------------------------------------------------------------------ dispatch
    @staticmethod
    async def dispatch_outbox(db: AsyncSession, limit: int = _DISPATCH_BATCH) -> int:
        """Send a batch of due queued/failed messages. Returns count attempted.

        Each row is locked ``FOR UPDATE SKIP LOCKED`` so concurrent dispatch
        ticks never grab the same message. Per-row exceptions are isolated.
        """
        now = datetime.now(UTC)
        rows = (
            (
                await db.execute(
                    select(CommunicationMessage)
                    .where(
                        CommunicationMessage.status.in_(("queued", "failed")),
                        CommunicationMessage.attempts < CommunicationMessage.max_attempts,
                        (CommunicationMessage.next_attempt_at.is_(None))
                        | (CommunicationMessage.next_attempt_at <= now),
                    )
                    .order_by(CommunicationMessage.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )

        attempted = 0
        for msg in rows:
            attempted += 1
            try:
                await NotificationGateway._dispatch_one(db, msg)
            except Exception as exc:  # noqa: BLE001 — isolate one poisoned row
                logger.error("dispatch failed for message %s: %s", msg.id, exc, exc_info=True)
                await db.rollback()
                await NotificationGateway._mark_failed(db, msg, str(exc))
        return attempted

    @staticmethod
    async def _dispatch_one(db: AsyncSession, msg: CommunicationMessage) -> None:
        adapter = channel_registry.get_for_channel(msg.channel)
        if adapter is None:
            await NotificationGateway._mark_failed(db, msg, f"no adapter for channel {msg.channel}")
            return

        msg.status = "sending"
        msg.attempts += 1
        # ponytail: commit before the network call so we don't hold a row lock
        # across I/O. Ceiling: a crash mid-send leaves the row in 'sending'
        # (visible in the logs view). Upgrade path: sweep 'sending' rows whose
        # updated_at is older than N minutes back to 'failed'.
        await db.commit()

        # Template sends (re)render from the template at send time; session
        # (free-form) sends carry the literal text in msg.body_text.
        template = None
        if msg.message_kind == "template":
            template = await NotificationService.get_template(
                db, msg.clinic_id, msg.template_key, _locale_of(msg), channel=msg.channel
            )
        outbound = OutboundMessage(
            channel=Channel(msg.channel),
            to_address=msg.to_address,
            clinic_id=msg.clinic_id,
            template_key=msg.template_key,
            locale=_locale_of(msg),
            context=msg.context_data or {},
            to_name=(msg.context_data or {}).get("patient_name"),
            patient_id=msg.patient_id,
            message_kind=msg.message_kind,
            provider_template_name=template.provider_template_name if template else None,
            subject=template.subject if template else msg.subject,
            body_html=template.body_html if template else None,
            body_text=(template.body_text if template else None) or msg.body_text,
        )

        result = await adapter.send(db, outbound)
        if result.status == SendStatus.SENT:
            msg.status = "sent"
            msg.sent_at = result.sent_at or datetime.now(UTC)
            msg.provider = result.provider
            msg.provider_message_id = result.provider_message_id
            msg.error_message = None
            await db.commit()
            await NotificationGateway._publish(msg, EventType.NOTIFICATION_SENT)
        else:
            await NotificationGateway._mark_failed(db, msg, result.error_message or "send failed")

    @staticmethod
    async def _mark_failed(db: AsyncSession, msg: CommunicationMessage, error: str) -> None:
        msg.status = "failed"
        msg.error_message = error[:2000]
        if msg.attempts < msg.max_attempts:
            msg.next_attempt_at = datetime.now(UTC) + timedelta(
                seconds=_backoff_seconds(msg.attempts)
            )
        await db.commit()
        await NotificationGateway._publish(msg, EventType.NOTIFICATION_FAILED)

    # ------------------------------------------------------------------ delivery
    @staticmethod
    async def record_delivery_status(
        db: AsyncSession, clinic_id: UUID, provider_message_id: str, status: str
    ) -> CommunicationMessage | None:
        """Apply a vendor webhook delivery/read receipt. Clinic-scoped."""
        msg = (
            await db.execute(
                select(CommunicationMessage).where(
                    CommunicationMessage.clinic_id == clinic_id,
                    CommunicationMessage.provider_message_id == provider_message_id,
                )
            )
        ).scalar_one_or_none()
        if msg is None:
            return None
        now = datetime.now(UTC)
        if status == "delivered" and msg.status not in ("read",):
            msg.status = "delivered"
            msg.delivered_at = now
        elif status == "read":
            msg.status = "read"
            msg.read_at = now
            msg.delivered_at = msg.delivered_at or now
        elif status == "failed":
            msg.status = "failed"
        await db.commit()
        if msg.status in ("delivered", "read"):
            await NotificationGateway._publish(msg, EventType.NOTIFICATION_DELIVERED)
        return msg

    # ------------------------------------------------------------------ inbound
    @staticmethod
    async def record_inbound_reply(
        db: AsyncSession,
        clinic_id: UUID,
        *,
        channel: str,
        from_address: str,
        body: str,
        patient_id: UUID | None = None,
        provider_message_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> CommunicationMessage | None:
        """Record an inbound patient message as an `inbound` thread row.

        Idempotent on ``provider_message_id`` (the vendor's message id), opens
        the 24h session window (``last_inbound_at``), and publishes
        ``NOTIFICATION_REPLY_RECEIVED``. Returns ``None`` on a duplicate.
        """
        if provider_message_id:
            dup = (
                await db.execute(
                    select(CommunicationMessage.id).where(
                        CommunicationMessage.clinic_id == clinic_id,
                        CommunicationMessage.dedup_key == provider_message_id,
                    )
                )
            ).first()
            if dup:
                return None

        occurred = occurred_at or datetime.now(UTC)
        msg = CommunicationMessage(
            clinic_id=clinic_id,
            channel=channel,
            direction="inbound",
            to_address=from_address,
            patient_id=patient_id,
            template_key="inbound",
            message_kind="session",
            status="received",
            body_text=body,
            provider=channel,
            provider_message_id=provider_message_id,
            dedup_key=provider_message_id,
            sent_at=occurred,
        )
        db.add(msg)
        # Open the 24h free-form window so staff can reply.
        if patient_id:
            prefs = await NotificationService.get_or_create_patient_preferences(
                db, clinic_id, patient_id
            )
            prefs.last_inbound_at = occurred
        await db.commit()
        await db.refresh(msg)

        await event_bus.publish(
            EventType.NOTIFICATION_REPLY_RECEIVED,
            {
                "clinic_id": str(clinic_id),
                "patient_id": str(patient_id) if patient_id else None,
                "message_id": str(msg.id),
                "channel": channel,
                "from_address": from_address,
                "reply_text": body,
                "occurred_at": occurred.isoformat(),
            },
        )
        return msg

    @staticmethod
    async def resolve_patient_by_phone(db: AsyncSession, clinic_id: UUID, phone: str):
        """Resolve a clinic patient by phone, ignoring formatting.

        Exact match first, then a last-9-digits match so ``+34 600 11 22 33``
        finds a patient stored as ``600112233``. Clinic-scoped.
        """
        from app.modules.patients.models import Patient

        exact = (
            await db.execute(
                select(Patient).where(Patient.clinic_id == clinic_id, Patient.phone == phone)
            )
        ).scalar_one_or_none()
        if exact:
            return exact

        digits = re.sub(r"\D", "", phone or "")
        if len(digits) < 6:
            return None
        suffix = digits[-9:]
        return (
            (
                await db.execute(
                    select(Patient).where(
                        Patient.clinic_id == clinic_id,
                        Patient.phone.is_not(None),
                        func.regexp_replace(Patient.phone, r"\D", "", "g").like(f"%{suffix}"),
                    )
                )
            )
            .scalars()
            .first()
        )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    async def _load_patient(db: AsyncSession, clinic_id: UUID, patient_id: UUID | None):
        if not patient_id:
            return None
        from app.modules.patients.models import Patient

        return (
            await db.execute(
                select(Patient).where(Patient.clinic_id == clinic_id, Patient.id == patient_id)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def _clinic_channels(
        db: AsyncSession, clinic_id: UUID, notification_type: str
    ) -> list[str]:
        settings = await NotificationService.get_clinic_settings(db, clinic_id)
        if settings:
            type_settings = settings.settings.get(notification_type, {})
            channels = type_settings.get("channels")
            if channels:
                return list(channels)
        return ["email"]  # ponytail: missing config ⇒ email-only, no migration

    @staticmethod
    async def _resolve_channel(
        db,
        clinic_id,
        notification_type,
        patient,
        prefs,
        locale,
        requested,
        to_address,
        requested_kind=None,
    ):
        for name in requested:
            try:
                channel = Channel(name)
            except ValueError:
                continue
            adapter = channel_registry.get_for_channel(channel)
            if adapter is None or not await adapter.supports(db, clinic_id):
                continue

            if channel == Channel.EMAIL:
                addr = (patient.email if patient else None) or to_address
                if not addr:
                    continue
                if prefs is not None and not prefs.email_enabled:
                    continue
                return channel, addr, "template", None

            if channel == Channel.SMS:
                addr = (patient.phone if patient else None) or to_address
                if not addr:
                    continue
                if prefs is not None and not prefs.sms_enabled:
                    continue
                return channel, addr, "template", None

            if channel == Channel.WHATSAPP:
                addr = patient.phone if patient else None
                if not addr:
                    continue
                # Free-form reply: allowed only inside the 24h session window
                # the patient's last inbound message opened. No opt-in needed
                # (the patient initiated), no template required.
                if requested_kind == "session":
                    if _session_window_open(prefs):
                        return channel, addr, "session", None
                    continue
                # Proactive: requires opt-in + an approved Meta template (HSM).
                if not (prefs and prefs.whatsapp_enabled):
                    continue
                tmpl = await NotificationService.get_template(
                    db, clinic_id, notification_type, locale, channel="whatsapp"
                )
                if (
                    not tmpl
                    or tmpl.provider_template_status != "approved"
                    or not tmpl.provider_template_name
                ):
                    continue
                return channel, addr, "template", tmpl.provider_template_name
        return None

    @staticmethod
    async def _skip(
        db,
        clinic_id,
        notification_type,
        patient_id,
        to_address,
        reason,
        triggered_by_event,
        triggered_by_user_id,
    ) -> CommunicationMessage:
        logger.info("skip notification %s: %s", notification_type, reason)
        msg = CommunicationMessage(
            clinic_id=clinic_id,
            channel="email",
            to_address=to_address or "",
            patient_id=patient_id,
            template_key=notification_type,
            status="skipped",
            error_message=reason,
            triggered_by_event=triggered_by_event,
            triggered_by_user_id=triggered_by_user_id,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    @staticmethod
    async def _publish(msg: CommunicationMessage, event_type: str) -> None:
        occurred = msg.sent_at or msg.delivered_at or msg.created_at
        payload = {
            "clinic_id": str(msg.clinic_id),
            "patient_id": str(msg.patient_id) if msg.patient_id else None,
            "message_id": str(msg.id),
            "channel": msg.channel,
            "template_key": msg.template_key,
            "subject": msg.subject,
            "status": msg.status,
            "error_message": msg.error_message,
            "occurred_at": occurred.isoformat() if occurred else None,
        }
        await event_bus.publish(event_type, payload)

        # Dual-publish the legacy EMAIL_* events for one release so
        # patient_timeline keeps recording email comms unchanged.
        if msg.channel == Channel.EMAIL:
            legacy = {**payload, "email_log_id": str(msg.id), "recipient_email": msg.to_address}
            if event_type == EventType.NOTIFICATION_SENT:
                await event_bus.publish(EventType.EMAIL_SENT, legacy)
            elif event_type == EventType.NOTIFICATION_FAILED:
                await event_bus.publish(EventType.EMAIL_FAILED, legacy)


def _locale_of(msg: CommunicationMessage) -> str:
    ctx = msg.context_data or {}
    return ctx.get("locale") or "es"
