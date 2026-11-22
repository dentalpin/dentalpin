"""telephony business logic: settings, number normalization, matching, ingest."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.email.encryption import encrypt_password
from app.core.events import EventType, event_bus

from .models import CallLog, TelephonySettings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.patients.models import Patient

# CTI event → CallLog.status. "ended" on an unanswered inbound call is
# recorded as missed (some PBXs send ended without a missed event).
_EVENT_STATUS = {
    "call.ringing": "ringing",
    "call.answered": "answered",
    "call.ended": "ended",
    "call.missed": "missed",
}

_BUS_EVENT = {
    "call.ringing": EventType.CALL_RINGING,
    "call.answered": EventType.CALL_ANSWERED,
    "call.ended": EventType.CALL_ENDED,
    "call.missed": EventType.CALL_MISSED,
}


def normalize_number(raw: str | None, default_country: str) -> str | None:
    """Best-effort E.164. Returns the stripped input when parsing fails —
    a call log with an odd-looking number beats a dropped event."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        import phonenumbers

        parsed = phonenumbers.parse(raw, default_country.upper())
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:  # noqa: BLE001 — normalization must never kill ingest
        pass
    return raw


class TelephonyService:
    # ------------------------------------------------------------- settings
    @staticmethod
    async def get_settings(db: AsyncSession, clinic_id: UUID) -> TelephonySettings | None:
        return (
            await db.execute(
                select(TelephonySettings).where(TelephonySettings.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def upsert_settings(
        db: AsyncSession, clinic_id: UUID, data: dict
    ) -> tuple[TelephonySettings, str | None]:
        """Returns ``(settings, plaintext_secret)`` — secret non-None only
        when (re)generated: first save or ``rotate_secret=True``."""
        settings = await TelephonyService.get_settings(db, clinic_id)
        plaintext: str | None = None
        if settings is None:
            plaintext = _generate_secret()
            settings = TelephonySettings(
                clinic_id=clinic_id,
                signing_secret_encrypted=encrypt_password(plaintext),
                default_country=(data.get("default_country") or "ES").upper(),
                is_active=data.get("is_active", True),
            )
            db.add(settings)
        else:
            if data.get("default_country"):
                settings.default_country = data["default_country"].upper()
            if data.get("is_active") is not None:
                settings.is_active = data["is_active"]
            if data.get("rotate_secret"):
                plaintext = _generate_secret()
                settings.signing_secret_encrypted = encrypt_password(plaintext)
        await db.flush()
        return settings, plaintext

    # ------------------------------------------------------------- matching
    @staticmethod
    async def match_patient(
        db: AsyncSession, clinic_id: UUID, number: str | None, *, default_country: str = "ES"
    ) -> Patient | None:
        """Caller → patient: exactly-one match on the normalized phone.

        SQL narrows by the last digits (index-friendly enough at clinic
        scale), Python confirms on the fully-normalized value. Multiple
        matches return None — phase 1 pops the picker client-side from
        the search page instead of guessing a household member.
        """
        from app.modules.patients.models import Patient

        if not number:
            return None
        digits = "".join(c for c in number if c.isdigit())
        if len(digits) < 6:
            return None
        tail = digits[-9:]
        cleaned = func.regexp_replace(Patient.phone, r"[^0-9]", "", "g")
        rows = (
            (
                await db.execute(
                    select(Patient).where(
                        Patient.clinic_id == clinic_id,
                        Patient.phone.is_not(None),
                        cleaned.like(f"%{tail}"),
                    )
                )
            )
            .scalars()
            .all()
        )
        # Confirm on the whole number, normalized the same way as the
        # caller's: a foreign number or a short extension that only shares
        # the last digits is someone else (#973).
        wanted = normalize_number(number, default_country)
        exact = [p for p in rows if normalize_number(p.phone, default_country) == wanted]
        return exact[0] if len(exact) == 1 else None

    # ------------------------------------------------------------- ingest
    @staticmethod
    async def ingest_event(
        db: AsyncSession,
        settings: TelephonySettings,
        payload: dict[str, Any],
    ) -> CallLog | None:
        """Apply one normalized CTI event: upsert the call row, publish.

        Returns the affected row, or None for an event/call_id the
        gateway can't use (accept-and-ignore — a misconfigured PBX must
        not see retry storms).
        """
        event = payload.get("event")
        call_id = str(payload.get("call_id") or "").strip()
        status = _EVENT_STATUS.get(event or "")
        if status is None or not call_id:
            return None

        clinic_id = settings.clinic_id
        from_number = normalize_number(payload.get("from_number"), settings.default_country)
        to_number = normalize_number(payload.get("to_number"), settings.default_country)
        provider = str(payload.get("provider") or "webhook")[:50]

        row = (
            await db.execute(
                select(CallLog).where(
                    CallLog.clinic_id == clinic_id,
                    CallLog.provider == provider,
                    CallLog.call_id == call_id,
                )
            )
        ).scalar_one_or_none()

        now = datetime.now(UTC)
        previous_status = row.status if row is not None else None
        if row is None:
            direction = payload.get("direction") or "inbound"
            # The patient is the far end: the caller on an inbound call, the
            # number dialled on an outbound one (whose from_number is the
            # clinic's own line).
            far_end = to_number if direction == "outbound" else from_number
            patient = await TelephonyService.match_patient(
                db, clinic_id, far_end, default_country=settings.default_country
            )
            fresh = CallLog(
                clinic_id=clinic_id,
                provider=provider,
                call_id=call_id,
                direction=direction,
                from_number=from_number or "",
                to_number=to_number,
                agent_extension=payload.get("agent_extension"),
                patient_id=patient.id if patient else None,
                started_at=_parse_ts(payload.get("started_at")) or now,
            )
            try:
                # Savepoint: two simultaneous *first* events of one call can
                # both miss the SELECT above; the unique constraint arbitrates
                # and the loser adopts the winner's row instead of 500ing.
                async with db.begin_nested():
                    db.add(fresh)
                    await db.flush()
                row = fresh
            except IntegrityError:
                row = (
                    await db.execute(
                        select(CallLog).where(
                            CallLog.clinic_id == clinic_id,
                            CallLog.provider == provider,
                            CallLog.call_id == call_id,
                        )
                    )
                ).scalar_one()

        row.status = status
        if status == "answered" and row.answered_at is None:
            row.answered_at = _parse_ts(payload.get("answered_at")) or now
        if status in ("ended", "missed"):
            row.ended_at = _parse_ts(payload.get("ended_at")) or now
            if payload.get("duration_seconds") is not None:
                try:
                    row.duration_seconds = int(payload["duration_seconds"])
                except (TypeError, ValueError):
                    pass
            # An inbound call that ends without ever being answered was missed.
            if status == "ended" and row.answered_at is None and row.direction == "inbound":
                row.status = "missed"

        settings.last_event_at = now
        await db.flush()

        # The bus carries what was recorded: an ended call stored as missed
        # is a ``call.missed`` (#986), unless an explicit missed event
        # already announced it.
        if event == "call.ended" and row.status == "missed" and previous_status != "missed":
            event = "call.missed"

        bus_payload = {
            "clinic_id": str(clinic_id),
            "call_log_id": str(row.id),
            "call_id": call_id,
            "event": event,
            "direction": row.direction,
            "from_number": row.from_number,
            "to_number": row.to_number,
            "patient_id": str(row.patient_id) if row.patient_id else None,
        }
        await event_bus.publish(_BUS_EVENT[event], bus_payload, db=db)
        if event == "call.ringing" and row.patient_id is None and row.direction == "inbound":
            await event_bus.publish(EventType.CALL_UNKNOWN_CALLER, bus_payload, db=db)
        return row

    # ------------------------------------------------------------- queries
    @staticmethod
    async def list_calls(
        db: AsyncSession,
        clinic_id: UUID,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CallLog], int]:
        # Responses render ``patient.full_name`` — eager-load it; a lazy
        # load from the async request context raises MissingGreenlet.
        stmt = (
            select(CallLog)
            .options(selectinload(CallLog.patient))
            .where(CallLog.clinic_id == clinic_id)
        )
        if status:
            stmt = stmt.where(CallLog.status == status)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (
            (
                await db.execute(
                    stmt.order_by(CallLog.created_at.desc(), CallLog.id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    @staticmethod
    async def active_calls(db: AsyncSession, clinic_id: UUID) -> list[CallLog]:
        """Ringing/answered calls that started in the last few minutes —
        what the polling screen-pop renders."""
        cutoff = datetime.now(UTC).timestamp() - 600
        rows = (
            (
                await db.execute(
                    select(CallLog)
                    .options(selectinload(CallLog.patient))
                    .where(
                        CallLog.clinic_id == clinic_id,
                        CallLog.status.in_(("ringing", "answered")),
                    )
                    .order_by(CallLog.created_at.desc())
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )
        return [r for r in rows if (r.started_at or r.created_at).timestamp() >= cutoff]


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _generate_secret() -> str:
    # tel_ prefix for secret-scanning, mirroring dp_ / whsec_.
    return "tel_" + secrets.token_urlsafe(32)
