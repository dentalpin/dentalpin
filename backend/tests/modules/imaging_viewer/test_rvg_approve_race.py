"""Approving an RVG import decides it once, even when two approvals race.

Approve read the row, checked ``status == "pending"`` and only then wrote
the document, the study and the decision, with nothing locked. Two
approvals at once (two tabs, or a batch and a single approve) both passed
the check and both filed the X-ray, possibly for two different patients.
Production hands each request its own session, so these tests do too.
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.media.service as media_service_module
from app.core.auth.models import Clinic, User
from app.database import async_session_maker
from app.modules.imaging_viewer import service as service_module
from app.modules.imaging_viewer.models import ImagingStudy, RvgImport
from app.modules.imaging_viewer.service import RvgConflictError, RvgService
from app.modules.patients.models import Patient


class _FakeStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def store(self, file_data: bytes, storage_path: str) -> None:
        self.files[storage_path] = file_data

    async def retrieve(self, path: str) -> bytes:
        return self.files[path]


@pytest.fixture()
def fake_storage(monkeypatch: pytest.MonkeyPatch) -> _FakeStorage:
    storage = _FakeStorage()
    monkeypatch.setattr(service_module, "get_storage_backend", lambda: storage)
    monkeypatch.setattr(media_service_module, "get_storage_backend", lambda: storage)
    return storage


@pytest.fixture()
def unseen_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tags that match nobody, so the scanned file waits in the queue."""
    monkeypatch.setattr(
        service_module,
        "extract_identity_tags",
        lambda raw: {"PatientID": "DNI-RACE", "PatientName": "Race^Nobody"},
    )


async def _queued(db: AsyncSession, clinic: Clinic) -> tuple[UUID, UUID, UUID, UUID]:
    user_id = (await db.execute(select(User))).scalars().first().id
    patients = [
        Patient(id=uuid4(), clinic_id=clinic.id, first_name=n, last_name="Race") for n in "AB"
    ]
    db.add_all(patients)
    await db.commit()
    row, _ = await RvgService.scan_bytes(db, clinic.id, "race.dcm", b"race-bytes")
    assert row.status == "pending"
    await db.commit()
    return row.id, patients[0].id, patients[1].id, user_id


async def _studies(db: AsyncSession, clinic_id: UUID) -> int:
    return await db.scalar(
        select(func.count()).select_from(ImagingStudy).where(ImagingStudy.clinic_id == clinic_id)
    )


@pytest.mark.asyncio
async def test_two_approvals_at_once_file_the_image_once(
    db_session: AsyncSession, test_clinic: Clinic, fake_storage, unseen_identity
) -> None:
    clinic_id = test_clinic.id
    import_id, patient_a, patient_b, user_id = await _queued(db_session, test_clinic)
    before = await _studies(db_session, clinic_id)

    async def approve(patient_id: UUID) -> str:
        async with async_session_maker() as db:
            try:
                await RvgService.approve(
                    db, clinic_id, import_id, patient_id, user_id, raw=b"race-bytes"
                )
            except RvgConflictError:
                return "conflict"
            return "approved"

    outcomes = await asyncio.gather(approve(patient_a), approve(patient_b))

    assert sorted(outcomes) == ["approved", "conflict"]
    db_session.expire_all()
    assert await _studies(db_session, clinic_id) == before + 1


@pytest.mark.asyncio
async def test_an_approval_waiting_on_the_row_sees_the_other_decision(
    db_session: AsyncSession, test_clinic: Clinic, fake_storage, unseen_identity
) -> None:
    """The approval must read ``status`` under the lock: once the first
    decision commits, the waiting one re-reads it and files nothing."""
    clinic_id = test_clinic.id
    import_id, patient_a, _, user_id = await _queued(db_session, test_clinic)
    before = await _studies(db_session, clinic_id)

    async with async_session_maker() as holder, async_session_maker() as other:
        locked = (
            await holder.execute(
                select(RvgImport).where(RvgImport.id == import_id).with_for_update()
            )
        ).scalar_one()

        waiting = asyncio.create_task(
            RvgService.approve(other, clinic_id, import_id, patient_a, user_id, raw=b"race-bytes")
        )
        await asyncio.sleep(0.3)
        assert not waiting.done(), "the approval should be blocked on the import row"

        locked.status = "rejected"  # the other reviewer's decision lands
        await holder.commit()
        with pytest.raises(RvgConflictError):
            await waiting
        await other.rollback()

    db_session.expire_all()
    assert await _studies(db_session, clinic_id) == before
