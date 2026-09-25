"""Matched-enquiry routing: an enquiry from a known patient becomes a recall.

RecallService.create is the **only** writer of a recall here. It dedupes
per (patient, reason) against active recalls and publishes
recall.created transactionally, which feeds activity_journal and (when
installed) recall_reminders. A hand-written insert would silently drop
both — never route around it.

recalls is in manifest.depends, so importing RecallService is legal.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.patients.models import Patient
from app.modules.recalls.service import RecallService

logger = logging.getLogger(__name__)

# The recall reason matched enquiries land on. "other" already exists in
# recalls.models.REASONS; a dedicated lead_callback reason would filter
# better but means editing another module's enum, its interval defaults,
# its picker and ten locale files — a follow-up, not a side effect of
# this module.
ENQUIRY_REASON = "other"

# Ceiling for the composed note. RecallService.create overwrites
# reason_note on its dedupe path, so a flood that kept appending would
# grow one row without bound.
NOTE_CAP = 4000
_NOTE_SEPARATOR = "\n\n---\n\n"


# The identity header's label, per clinic communication language.
#
# A stored note has no reader locale — the app's UI language lives in the
# browser (frontend/app/composables/useLocale.ts, localStorage only) and never
# reaches the API, and intake has no user session at all — so the label is
# written in the *clinic's* language and frozen with the note. The source is
# `clinic.settings["communication_language"]`, the same one the budget PDFs and
# the notifications gateway read; the fallback is the platform default for
# clinic-authored text (notifications' DEFAULT_COMMUNICATION_LOCALE).
#
# The non-es/en labels are first-pass translations of "Web form — submitted
# as": one dict entry each, so a clinic that prefers different wording is a
# one-line fix. `test_routing.py` guards the key set against the host locale
# list (core/pdf_locales.PDF_LOCALES).
_IDENTITY_LABELS: dict[str, str] = {
    "es": "Formulario web — enviado como",
    "en": "Web form — submitted as",
    "fr": "Formulaire web — envoyé en tant que",
    "pt": "Formulário web — enviado como",
    "it": "Modulo web — inviato come",
    "de": "Webformular — gesendet als",
    "pl": "Formularz internetowy — wysłano jako",
    "hu": "Webes űrlap — beküldve mint",
    "ta": "இணையதளப் படிவம் — சமர்ப்பிக்கப்பட்டது",
    "ar": "نموذج الموقع الإلكتروني — أُرسل باسم",
}
_FALLBACK_LOCALE = "es"


def _identity_label(locale: str | None) -> str:
    """The header label for a clinic language; never misses, never raises."""
    return _IDENTITY_LABELS.get(locale or "") or _IDENTITY_LABELS[_FALLBACK_LOCALE]


def _identity_header(data: dict, locale: str) -> str | None:
    """Who the form *said* it was, verbatim.

    The matched-patient path drops the submitted name/phone/email: the recall
    hangs off the patient the enquiry matched, so this note is all that is
    left of them. Without it, a stranger's words — or a relative's, or a
    one-digit typo in the phone — read exactly like the patient's own, and the
    front desk acts on them. With it, the mismatch is visible before the call
    is made.
    """
    parts = [str(data.get(field) or "").strip() for field in ("full_name", "phone", "email")]
    submitted = " · ".join(part for part in parts if part)
    return f"{_identity_label(locale)}: {submitted}" if submitted else None


def _compose_enquiry_note(data: dict, *, locale: str) -> str:
    """Identity header, then motive / description.

    Only the header carries invented words — and those come from the clinic's
    language, not the reader's (see ``_IDENTITY_LABELS``); everything after it
    is the enquirer's own text. The header goes first so that when ``NOTE_CAP``
    truncates, the identity is never the part that gets cut — that is the
    part the call depends on.

    The submitted availability (days / slot) is deliberately **left out**. It
    is a booking window for a first appointment, not part of what the patient
    wanted to say, and the call-back records the second thing. The consequence
    to know about: a matched enquiry writes no lead row, so its availability is
    not stored anywhere at all — see the module CLAUDE.md.
    """
    parts: list[str] = []
    header = _identity_header(data, locale)
    if header:
        parts.append(header)
    for field in ("motive", "description"):
        value = str(data.get(field) or "").strip()
        if value:
            parts.append(value)
    return "\n\n".join(parts)[:NOTE_CAP]


def _merged_note(existing_note: str | None, note: str) -> str | None:
    """Append note to an existing note without ever losing text.

    A staff member may have written their own other recall for this
    patient, and a repeat enquiry must not stack a second copy of the
    same block. So:

    * no existing note -> the new note;
    * the block is already in there -> the existing note, unchanged;
    * appending would exceed the cap -> the existing note, unchanged;
    * otherwise -> existing + separator + new.
    """
    if not existing_note:
        return note
    if not note or note in existing_note:
        return existing_note
    if len(existing_note) + len(_NOTE_SEPARATOR) + len(note) > NOTE_CAP:
        return existing_note
    return f"{existing_note}{_NOTE_SEPARATOR}{note}"


def _safe_zone(name: str | None) -> ZoneInfo:
    """Resolve an IANA id defensively — a hand-edited tz must not 500 intake."""
    try:
        return ZoneInfo(name) if name else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("leads: invalid clinic timezone %r; falling back to UTC", name)
        return ZoneInfo("UTC")


async def _clinic_context(db: AsyncSession, clinic_id: UUID) -> tuple[ZoneInfo, str]:
    """``(timezone, communication language)`` for a clinic, in one read.

    Both live on the core ``Clinic`` row — ``clinics.timezone`` and
    ``clinics.settings["communication_language"]`` — so neither needs a
    cross-module import. Deliberately local rather than importing
    ``agenda.tz`` (timezone) or ``notifications.service`` (language): neither
    module is in this module's ``manifest.depends``, and
    ``tests/test_module_isolation.py`` fails a stealth cross-module import.
    Same shape as ``copilot/tasks.py::_clinic_tz``.
    """
    row = (
        await db.execute(select(Clinic.timezone, Clinic.settings).where(Clinic.id == clinic_id))
    ).first()
    tz_name, settings = row if row is not None else (None, None)
    language = str((settings or {}).get("communication_language") or "")
    return _safe_zone(tz_name), (language if language in _IDENTITY_LABELS else _FALLBACK_LOCALE)


def _local_day(tz: ZoneInfo, now: datetime | None = None) -> date:
    """The calendar day ``now`` (default: now) falls on in ``tz``.

    "Call today" is a wall-clock statement about the clinic: near midnight, a
    server in a different timezone would write yesterday's or tomorrow's date
    onto the recall. ``now`` is injectable so a test can pin an instant and
    assert which clinic-local day it lands on.
    """
    return (now or datetime.now(UTC)).astimezone(tz).date()


async def route_matched_enquiry(
    db: AsyncSession,
    clinic_id: UUID,
    patients: list[Patient],
    data: dict,
    recommended_by: UUID | None,
) -> list[Patient]:
    """Queue a recall for each matched patient; return the patients touched.

    Every match gets a recall — each one needs a phone call, and a family
    sharing a phone is a legitimate two-patient match.

    An opted-out (do_not_contact) patient's recall is created in
    needs_review so it never sits in the default call list (which filters
    opted-out patients out and would silently swallow the enquiry).
    Outbound contact stays blocked independently by the notifications
    gateway, even with force_send.
    """
    tz, locale = await _clinic_context(db, clinic_id)
    note = _compose_enquiry_note(data, locale=locale)
    today = _local_day(tz)
    recalled: list[Patient] = []

    for patient in patients:
        existing = await RecallService.find_pending_for(db, clinic_id, patient.id, ENQUIRY_REASON)
        recall, _created = await RecallService.create(
            db,
            clinic_id,
            {
                "patient_id": patient.id,
                "due_month": today,  # the service normalises to day-1
                "due_date": today,  # "call today"
                "reason": ENQUIRY_REASON,
                "priority": "high",  # the call list sorts high first
                "reason_note": _merged_note(existing.reason_note if existing else None, note),
                "assigned_professional_id": None,
            },
            recommended_by=recommended_by,
        )
        if patient.do_not_contact and recall.status != "needs_review":
            recall.status = "needs_review"
            await db.flush()
        recalled.append(patient)

    logger.info(
        "leads: enquiry routed to %s recall(s) for clinic %s",
        len(recalled),
        clinic_id,
    )
    return recalled
