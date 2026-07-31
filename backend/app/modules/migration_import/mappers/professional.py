"""Map ``professional`` → :class:`auth.User` + :class:`ClinicMembership`.

We create a non-loginable User shell (random unguessable password hash)
so the rest of the system can reference the professional via FK
(``appointments.professional_id``, etc.). Login stays blocked by the
``!migration_disabled:`` password hash until an admin sends a reset.

The User row itself is created ``is_active=True`` so the admin sees
imported professionals as live entries in the Users page (matching the
source PMS, where these people are actively working in the clinic).
The inactive flag is reserved for users an admin has explicitly
disabled — not for "needs password reset".

Email collisions across clinics resolve to the existing User —
DentalPin's User table is global, ClinicMembership is per-clinic.

Soft filtering (``ctx.professional_filters``): rows that match any of
the four operator-enabled signals (source-marked inactive, agenda-orphan,
no recent activity, non-clinical role) are still created so historical
FKs keep resolving, but with ``is_active=False`` and
``role='assistant'``. The agenda filters by role + is_active so those
users disappear from clinician dropdowns. The operator can promote them
later from Settings → Users.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.auth.models import ClinicMembership, User

from ..models import ImportWarning
from .base import MapperContext, ProfessionalFilterOptions

# Map DPMF's canonical `role` string (see dental-bridge's
# ``ProfessionalRole`` StrEnum) into DentalPin's membership role values.
# The source enum emits ``doctor`` — DentalPin calls the same role
# ``dentist``. Anything unrecognised falls back to "assistant" so the
# user can do something useful while the admin re-roles.
_ROLE_MAP: dict[str, str] = {
    "doctor": "dentist",
    "dentist": "dentist",
    "hygienist": "hygienist",
    "auxiliary": "assistant",
    "assistant": "assistant",
    "receptionist": "receptionist",
    "admin": "admin",
}

# Source-canonical role values that count as "clinical" (visible in the
# agenda). Everything else is considered non-clinical for the optional
# fourth filter signal.
_CLINICAL_ROLES: frozenset[str] = frozenset({"doctor", "dentist", "hygienist"})


def _parse_activity_date(value: object | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _months_between(later: date, earlier: date) -> int:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def _filter_reason(
    payload: dict[str, Any],
    source_id: str,
    opts: ProfessionalFilterOptions,
) -> str | None:
    """Return the first matching filter signal, or ``None`` to keep active.

    Activity rescues orphan: a ``TUsuAgd`` row without a ``TColabos`` link
    is treated as a placeholder *only* when it has no recent clinical
    trace. Real clinics routinely keep practising staff on agenda columns
    that the operator never linked back to a colaborador record — those
    rows own real appointments and must stay agenda-visible.
    """
    last = _parse_activity_date(payload.get("last_activity_at"))
    has_recent_activity = (
        opts.min_activity_months > 0
        and last is not None
        and _months_between(date.today(), last) <= opts.min_activity_months
    )

    if opts.exclude_inactive_in_source and bool(payload.get("deactivated", False)):
        return "inactive_in_source"
    if opts.exclude_agenda_orphans and source_id.startswith("usuagd:"):
        if not has_recent_activity:
            return "agenda_orphan"
    if opts.min_activity_months > 0 and not has_recent_activity:
        if last is None:
            return "no_activity_recorded"
        return "no_recent_activity"
    if opts.exclude_non_clinical_roles:
        role = (payload.get("role") or "other").lower()
        if role not in _CLINICAL_ROLES:
            return "non_clinical_role"
    return None


class ProfessionalMapper:
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
        existing = await ctx.resolver.get("professional", canonical_uuid)
        if existing is not None:
            return existing

        email = (payload.get("email") or "").strip().lower() or None
        first_name = (payload.get("given_name") or "").strip() or "Profesional"
        last_name = (payload.get("family_name") or "").strip() or "—"

        # Fall back to a synthetic email so the User row is creatable.
        # The admin sees these in the Users page and merges/edits.
        if not email:
            slug = (
                "".join(ch.lower() for ch in f"{first_name}{last_name}" if ch.isalnum())
                or canonical_uuid[:8]
            )
            email = f"migrado+{slug}-{canonical_uuid[:8]}@dental-bridge.local"

        # Apply operator-tunable filters. A matching reason demotes the
        # row to is_active=False + role=assistant so it stays out of the
        # agenda but historical FKs still resolve. When ``professional_filters``
        # is ``None`` (legacy callers / tests that bypass the executor),
        # we fall back to the historical behaviour: only ``deactivated``
        # in the payload demotes the row, everything else stays active.
        if ctx.professional_filters is None:
            filter_reason = (
                "inactive_in_source" if bool(payload.get("deactivated", False)) else None
            )
        else:
            filter_reason = _filter_reason(payload, source_id, ctx.professional_filters)
        is_active = filter_reason is None

        # Re-use an existing User if email already known.
        existing_user = await ctx.db.execute(select(User).where(User.email == email))
        user = existing_user.scalar_one_or_none()
        if user is None:
            user = User(
                id=uuid4(),
                email=email,
                # Sentinel hash bcrypt cannot match; login stays blocked
                # until an admin sends a password reset.
                password_hash=f"!migration_disabled:{secrets.token_urlsafe(32)}",
                first_name=first_name,
                last_name=last_name,
                is_active=is_active,
            )
            ctx.db.add(user)
            await ctx.db.flush()
        elif not is_active and user.is_active:
            # Email collision with a row this same job filtered out a
            # moment ago — keep the inactive state sticky so a later
            # active row does not silently re-enable a filtered staff.
            # Do NOT downgrade users that were already active before the
            # job started (that would be a destructive side effect).
            pass

        # Ensure membership in the target clinic.
        membership_q = await ctx.db.execute(
            select(ClinicMembership).where(
                ClinicMembership.user_id == user.id,
                ClinicMembership.clinic_id == ctx.clinic_id,
            )
        )
        membership = membership_q.scalar_one_or_none()
        if membership is None:
            if is_active:
                role = _ROLE_MAP.get((payload.get("role") or "").lower(), "assistant")
            else:
                # Filtered rows never become dentist/hygienist — the
                # agenda filter (auth/router.py) hides them via
                # is_professional=False, which is a defence-in-depth
                # against future mistakes around is_active.
                role = "assistant"
            membership = ClinicMembership(
                id=uuid4(),
                clinic_id=ctx.clinic_id,
                user_id=user.id,
                role=role,
            )
            ctx.db.add(membership)
            await ctx.db.flush()

        if filter_reason is not None:
            ctx.db.add(
                ImportWarning(
                    id=uuid4(),
                    job_id=ctx.job_id,
                    entity_type="professional",
                    source_id=source_id,
                    severity="info",
                    code=f"professional.filtered.{filter_reason}",
                    message=(
                        f"Imported {last_name}, {first_name} as inactive (filter: {filter_reason})."
                    ),
                    raw_data=None,
                )
            )

        await ctx.resolver.set(
            entity_type="professional",
            canonical_uuid=canonical_uuid,
            source_system=source_system,
            dentalpin_table="users",
            dentalpin_id=user.id,
        )
        return user.id
