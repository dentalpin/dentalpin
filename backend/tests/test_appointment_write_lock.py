"""Prove clinic lock behavior with separate PostgreSQL transactions."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.auth.models import ClinicMembership
from app.modules.agenda.locks import lock_clinic
from app.modules.agenda.models import AppointmentCabinetEvent, Cabinet
from app.modules.agenda.service import AppointmentService


@pytest.mark.parametrize("operation", ["create", "update", "assign_cabinet"])
async def test_agenda_write_waits_for_clinic_lock(db_session, test_clinic, test_patient, operation):
    clinic_id = test_clinic.id
    professional_id = await db_session.scalar(
        select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == clinic_id)
    )
    cabinet_id = await db_session.scalar(select(Cabinet.id).where(Cabinet.clinic_id == clinic_id))
    start = datetime(2026, 12, 10, 12, tzinfo=UTC)
    data = {
        "patient_id": test_patient.id,
        "professional_id": professional_id,
        "start_time": start,
        "end_time": start + timedelta(minutes=30),
    }
    existing = await AppointmentService.create_appointment(db_session, clinic_id, data.copy())
    appointment_id = existing.id
    await db_session.commit()

    sessions = async_sessionmaker(db_session.bind, expire_on_commit=False)
    async with sessions() as writer:
        loaded = await AppointmentService.get_appointment(writer, clinic_id, appointment_id)
        assert loaded is not None and loaded.cabinet_id is None
        writer_pid = await writer.scalar(text("SELECT pg_backend_pid()"))

        async def write():
            if operation == "create":
                return await AppointmentService.create_appointment(
                    writer,
                    clinic_id,
                    {
                        **data,
                        "start_time": start + timedelta(hours=1),
                        "end_time": start + timedelta(hours=1, minutes=30),
                    },
                )
            if operation == "update":
                return await AppointmentService.update_appointment(
                    writer, loaded, {"end_time": start + timedelta(minutes=45)}
                )
            return await AppointmentService.assign_cabinet(writer, loaded, cabinet_id)

        async with asyncio.TaskGroup() as group:
            async with db_session.begin():
                await lock_clinic(db_session, clinic_id)
                pending = group.create_task(write())

                async with asyncio.timeout(5):
                    while not await db_session.scalar(
                        text("SELECT pg_backend_pid() = ANY(pg_blocking_pids(:pid))"),
                        {"pid": writer_pid},
                    ):
                        assert not pending.done(), "The writer completed while the lock was held"
                        await asyncio.sleep(0.01)
                assert not pending.done()

                if operation == "assign_cabinet":
                    # The waiting transaction loaded the unassigned appointment.
                    # After this commit, its assignment should be a no-op.
                    await AppointmentService.assign_cabinet(db_session, existing, cabinet_id)

        result = pending.result()
        await writer.commit()

    if operation == "create":
        assert result.id != appointment_id
    elif operation == "update":
        assert result.end_time == start + timedelta(minutes=45)
    else:
        assert result.cabinet_id == cabinet_id
        events = (
            await db_session.scalars(
                select(AppointmentCabinetEvent).where(
                    AppointmentCabinetEvent.appointment_id == appointment_id
                )
            )
        ).all()
        assert [event.to_cabinet_id for event in events] == [cabinet_id]


async def test_clinic_write_locks_for_distinct_clinics_do_not_block(db_session):
    sessions = async_sessionmaker(db_session.bind, expire_on_commit=False)
    async with db_session.begin(), sessions.begin() as other:
        await lock_clinic(db_session, uuid4())
        async with asyncio.timeout(5):
            await lock_clinic(other, uuid4())
