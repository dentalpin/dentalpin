"""Agenda event handlers.

``clinic.created`` → one default cabinet so the calendar has a column
from the first login. Idempotent: skipped if any cabinet exists.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.database import async_session_maker

from .service import CabinetService

logger = logging.getLogger(__name__)

_DEFAULT_CABINET_NAME = {
    "es": "Gabinete 1",
    "en": "Room 1",
    "fr": "Cabinet 1",
    "pt": "Gabinete 1",
    "ta": "அறை 1",
    "hi": "कक्ष 1",
}


async def on_clinic_created(data: dict[str, Any]) -> None:
    """own-session (issue #183): ``clinic.created`` is published after
    ``POST /auth/setup`` commits, so there are no uncommitted rows to miss —
    and seeding a fresh clinic must not stretch the signup transaction.
    """
    clinic_id_raw = data.get("clinic_id")
    if not clinic_id_raw:
        return
    try:
        clinic_id = UUID(str(clinic_id_raw))
    except (ValueError, TypeError):
        return

    name = _DEFAULT_CABINET_NAME.get(data.get("language") or "es", _DEFAULT_CABINET_NAME["en"])

    async with async_session_maker() as db:
        try:
            if await CabinetService.list_cabinets(db, clinic_id):
                return
            await CabinetService.create_cabinet(db, clinic_id, {"name": name, "color": "#3B82F6"})
            await db.commit()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("agenda.on_clinic_created failed: %s", exc, exc_info=True)
            await db.rollback()
