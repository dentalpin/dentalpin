"""Historical appointments keep a chair that is now an inactive cabinet (#1237).

The chair mapper resolves Gesdén ``TBoxes`` by name, inactive cabinets
included. Agenda refuses new bookings into an inactive cabinet, but an
import replays history: the appointment must land with its cabinet
instead of being rolled back.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.agenda.models import Appointment, Cabinet
from tests.modules.migration_import.test_appointment_notes_routing import (
    _apply,
    _bootstrap,
    _ctx,
)


@pytest.mark.asyncio
async def test_import_keeps_appointment_in_inactive_cabinet(db_session) -> None:
    clinic, admin, prof, patient = await _bootstrap(db_session)
    cabinet = Cabinet(
        id=uuid4(),
        clinic_id=clinic.id,
        name="Box 3",
        color="#000",
        display_order=0,
        is_active=False,
    )
    db_session.add(cabinet)
    await db_session.flush()
    ctx = await _ctx(db_session, clinic.id, admin.id)
    chair_uuid = str(uuid4())
    await ctx.resolver.set(
        entity_type="catalog_item",
        canonical_uuid=chair_uuid,
        source_system="gesden",
        dentalpin_table="cabinets",
        dentalpin_id=cabinet.id,
    )

    apt_id, _ = await _apply(
        ctx,
        patient_id=patient.id,
        professional_id=prof.id,
        payload={"chair_uuid": chair_uuid, "coarse_status": "completed"},
    )
    await db_session.flush()

    apt = (
        await db_session.execute(select(Appointment).where(Appointment.id == apt_id))
    ).scalar_one()
    assert apt.cabinet_id == cabinet.id
    assert apt.cabinet == "Box 3"
