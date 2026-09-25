"""Patient matching for inbound enquiries.

The one heuristic this module owns: a phone number is compared by its
**trailing 9 digits**, so 600 111 222 forms of the same number collapse
to one patient. It is a heuristic, not a normaliser — numbers shorter
than 9 digits compare whole, so a short legacy number can false-positive.
That is why the convert drawer still lets a human confirm before
anything is written.

Kept in its own file (no HTTP, no service imports) so the rule is
readable and unit-testable on its own; a second copy of it anywhere is
how matching drifts.
"""

from __future__ import annotations

import logging
import re
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.patients.models import Patient

logger = logging.getLogger(__name__)

# How many patients one enquiry may fan out to. A family sharing one
# phone/email legitimately matches two or three patients; the cap bounds
# the recall fan-out a single (or leaked) key can trigger.
MATCH_LIMIT = 3

_PHONE_KEY_LENGTH = 9
_NON_DIGITS = re.compile(r"\D")


def phone_key(raw: str | None) -> str:
    """Digits only, last 9 (or fewer when the number is shorter)."""
    digits = _NON_DIGITS.sub("", raw or "")
    if len(digits) >= _PHONE_KEY_LENGTH:
        return digits[-_PHONE_KEY_LENGTH:]
    return digits


async def find_matching_patients(
    db: AsyncSession,
    clinic_id: UUID,
    phone: str | None,
    email: str | None,
) -> list[Patient]:
    """Clinic-scoped, non-archived patients matching this phone OR email.

    Phone matches sort first, then most recently created. Archived charts
    are excluded: an archived patient's enquiry takes the normal lead
    path, which is where a reactivation decision belongs.
    """
    key = phone_key(phone)
    address = (email or "").strip().lower()
    if not key and not address:
        return []

    match_clauses = []
    phone_match = None
    if key:
        # The SQL twin of phone_key() above: the last 9 digits of a
        # digit-only copy of the stored number. Any change here must
        # change that function too.
        phone_match = (
            func.right(
                func.regexp_replace(func.coalesce(Patient.phone, ""), r"\D", "", "g"),
                _PHONE_KEY_LENGTH,
            )
            == key
        )
        match_clauses.append(phone_match)
    if address:
        match_clauses.append(func.lower(Patient.email) == address)

    stmt = select(Patient).where(
        Patient.clinic_id == clinic_id,  # mandatory — never omit
        Patient.status != "archived",
        or_(*match_clauses),
    )

    if phone_match is not None:
        # A phone match is a stronger signal than an email one (a shared
        # family inbox is common; a shared phone is not).
        stmt = stmt.order_by(case((phone_match, 0), else_=1).asc(), Patient.created_at.desc())
    else:
        stmt = stmt.order_by(Patient.created_at.desc())

    result = await db.execute(stmt.limit(MATCH_LIMIT))
    matches = list(result.scalars().all())
    if len(matches) == MATCH_LIMIT:
        # Best-effort truncation signal: the query cannot distinguish
        # "exactly 3" from "more than 3" without a second round trip.
        logger.info(
            "leads: match limit (%d) reached for clinic %s — recall fan-out truncated",
            MATCH_LIMIT,
            clinic_id,
        )
    return matches
