"""Map ``user`` → :class:`auth.User` + receptionist :class:`ClinicMembership`.

DPMF v0.1 emits ``user`` as a standalone entity covering Gesdén's
non-clinical staff (administradoras, recepción, contabilidad…). They
don't appear as ``professional`` rows because they aren't clinicians,
but the source's audit trail references them via
``budget.elaborated_by_user_uuid`` / ``payment.user_uuid`` /
``fiscal_document.user_uuid`` / ``applied_treatment.user_uuid``.

Without a mapper for ``user`` these rows fell through to
``RawEntity`` and every imported entity attributed authorship to the
admin who launched the migration (``ctx.created_by``), erasing the
original creator history.

Behaviour:

- ``email`` is the natural key. Synthesise
  ``migrado+user-<short_uuid>@dental-bridge.local`` when the source
  has none so the User row is creatable.
- Re-use an existing User if the email already exists (typical when
  the same person appears as both ``user`` and ``professional`` in
  the source — the professional mapper landed first and created the
  User).
- Create the User with a non-loginable password hash (matches
  ``professional.py`` pattern). The admin must send a reset link
  before the imported person can sign in.
- ``is_active`` mirrors the source's ``deactivated`` flag.
- Always ensure a ``ClinicMembership(role='receptionist')`` exists.
  The receptionist role is the minimum non-clinical role in
  DentalPin's RBAC matrix (``backend/app/core/auth/permissions.py``);
  the admin can promote individual users to ``admin`` later from the
  Users page.
"""

from __future__ import annotations

import secrets
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.auth.models import ClinicMembership, User
from app.core.auth.rbac import resolve_role_id

from .base import MapperContext


class UserMapper:
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
        existing = await ctx.resolver.get("user", canonical_uuid)
        if existing is not None:
            return existing

        email = (payload.get("email") or "").strip().lower() or None
        first_name = (payload.get("given_name") or "").strip() or "Usuario"
        last_name = (payload.get("family_name") or "").strip() or "—"

        if not email:
            email = f"migrado+user-{canonical_uuid[:8]}@dental-bridge.local"

        existing_user = await ctx.db.execute(select(User).where(User.email == email))
        user = existing_user.scalar_one_or_none()
        if user is None:
            user = User(
                id=uuid4(),
                email=email,
                password_hash=f"!migration_disabled:{secrets.token_urlsafe(32)}",
                first_name=first_name,
                last_name=last_name,
                is_active=not bool(payload.get("deactivated", False)),
            )
            ctx.db.add(user)
            await ctx.db.flush()

        # Idempotent membership upsert. If the user is also a
        # professional, the professional mapper may have already
        # created a higher-privilege membership (dentist, hygienist…);
        # don't downgrade it.
        membership_q = await ctx.db.execute(
            select(ClinicMembership).where(
                ClinicMembership.user_id == user.id,
                ClinicMembership.clinic_id == ctx.clinic_id,
            )
        )
        membership = membership_q.scalar_one_or_none()
        if membership is None:
            ctx.db.add(
                ClinicMembership(
                    id=uuid4(),
                    clinic_id=ctx.clinic_id,
                    user_id=user.id,
                    role="receptionist",
                    role_id=await resolve_role_id(ctx.db, ctx.clinic_id, "receptionist"),
                )
            )
            await ctx.db.flush()

        await ctx.resolver.set(
            entity_type="user",
            canonical_uuid=canonical_uuid,
            source_system=source_system,
            dentalpin_table="users",
            dentalpin_id=user.id,
        )
        return user.id
