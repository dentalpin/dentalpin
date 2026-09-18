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
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.patients.models import Patient
from app.modules.recalls.service import RecallService

from .models import canonical_days

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


def _format_availability(days: list[str] | None, slot: str | None) -> str | None:
    """Availability as a language-free token: "mon, wed · afternoon".

    The recall note is stored text shared by every consumer, so it cannot be
    rendered in the reader's language — day codes and the slot identifier
    read the same to a Spanish and an English front desk, and they are the
    only part of the enquiry that is not already free text written by the
    person themselves. The lead card renders the same information with
    localized weekday names; this is the fallback for the recall path, where
    no lead row exists.
    """
    codes = canonical_days(days) or []
    parts: list[str] = []
    if codes:
        parts.append(", ".join(codes))
    if slot:
        parts.append(str(slot))
    return " · ".join(parts) or None


def _compose_enquiry_note(data: dict) -> str:
    """motive / description / availability, blank-line separated.

    No invented labels: the note is data the staff reads, and the first two
    parts are the enquirer's own words.
    """
    parts: list[str] = []
    for field in ("motive", "description"):
        value = str(data.get(field) or "").strip()
        if value:
            parts.append(value)
    availability = _format_availability(
        data.get("availability_days"), data.get("availability_slot")
    )
    if availability:
        parts.append(availability)
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
    note = _compose_enquiry_note(data)
    today = date.today()
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
