"""imaging_viewer RVG import: scan determinism, matching, approval, links, isolation."""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.media.service as media_service_module
from app.core.auth.models import Clinic, User
from app.modules.imaging_viewer import service as service_module
from app.modules.imaging_viewer.models import RvgLink
from app.modules.imaging_viewer.service import RvgConflictError, RvgService
from app.modules.patients.models import Patient


class _FakeStorage:
    """In-memory stand-in for the media storage backend (no filesystem)."""

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
def canned_tags(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Deterministic identity tags regardless of pydicom availability."""
    tags = {
        "PatientID": "DNI-123",
        "PatientName": "Patient^Test",
        "PatientBirthDate": "19900101",
        "StudyInstanceUID": "1.2.826.0.1.9999.1",
        "Modality": "DX",
        "StudyDate": "20260904",
    }
    monkeypatch.setattr(service_module, "extract_identity_tags", lambda raw: dict(tags))
    return tags


async def _user_id(db: AsyncSession) -> UUID:
    return (await db.execute(select(User))).scalars().first().id


async def _second_clinic(db: AsyncSession) -> Clinic:
    clinic = Clinic(id=uuid4(), name="Other Clinic", tax_id="B87654321")
    db.add(clinic)
    await db.commit()
    return clinic


@pytest.mark.asyncio
async def test_scan_suggests_national_id_match(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    canned_tags: dict,
) -> None:
    test_patient.national_id = "DNI-123"
    await db_session.commit()

    row, created = await RvgService.scan_bytes(
        db_session, test_clinic.id, "rvg001.dcm", b"bytes-one"
    )
    assert created is True
    assert row.status == "pending"
    assert row.suggested_patient_id == test_patient.id
    assert row.match_score and row.match_score >= 60
    assert "national_id" in (row.match_reason or "")


@pytest.mark.asyncio
async def test_rescan_same_bytes_is_noop(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    canned_tags: dict,
) -> None:
    first, created_first = await RvgService.scan_bytes(
        db_session, test_clinic.id, "rvg001.dcm", b"same-bytes"
    )
    second, created_second = await RvgService.scan_bytes(
        db_session, test_clinic.id, "rvg001-copy.dcm", b"same-bytes"
    )
    assert created_first is True
    assert created_second is False
    assert first.id == second.id


@pytest.mark.asyncio
async def test_unreadable_file_stays_discoverable(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service_module, "extract_identity_tags", lambda raw: {})
    row, created = await RvgService.scan_bytes(
        db_session, test_clinic.id, "broken.dcm", b"not-dicom-at-all"
    )
    assert created is True
    assert row.status == "failed"
    assert row.error

    items, total = await RvgService.list_imports(db_session, test_clinic.id, status="failed")
    assert total == 1
    assert items[0].id == row.id


@pytest.mark.asyncio
async def test_approve_materializes_and_stores_link(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
    canned_tags: dict,
) -> None:
    user_id = await _user_id(db_session)
    row, _ = await RvgService.scan_bytes(db_session, test_clinic.id, "rvg002.dcm", b"bytes-two")
    assert row.status == "pending"

    decided = await RvgService.approve(
        db_session, test_clinic.id, row.id, test_patient.id, user_id, raw=b"bytes-two"
    )
    assert decided.status == "approved"
    assert decided.document_id is not None
    assert decided.study_id is not None

    link = (
        await db_session.execute(
            select(RvgLink).where(
                RvgLink.clinic_id == test_clinic.id,
                RvgLink.dicom_patient_id == "DNI-123",
            )
        )
    ).scalar_one_or_none()
    assert link is not None
    assert link.patient_id == test_patient.id


@pytest.mark.asyncio
async def test_linked_identity_auto_imports(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
    canned_tags: dict,
) -> None:
    user_id = await _user_id(db_session)
    first, _ = await RvgService.scan_bytes(db_session, test_clinic.id, "a.dcm", b"file-a")
    await RvgService.approve(
        db_session, test_clinic.id, first.id, test_patient.id, user_id, raw=b"file-a"
    )

    second, created = await RvgService.scan_bytes(db_session, test_clinic.id, "b.dcm", b"file-b")
    assert created is True
    assert second.status == "approved"
    assert second.match_reason == "linked"
    assert second.patient_id == test_patient.id
    assert second.study_id is not None


@pytest.mark.asyncio
async def test_approve_twice_conflicts_and_unknown_patient_404s(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
    canned_tags: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = await _user_id(db_session)
    row, _ = await RvgService.scan_bytes(db_session, test_clinic.id, "c.dcm", b"file-c")
    await RvgService.approve(
        db_session, test_clinic.id, row.id, test_patient.id, user_id, raw=b"file-c"
    )
    with pytest.raises(RvgConflictError):
        await RvgService.approve(
            db_session, test_clinic.id, row.id, test_patient.id, user_id, raw=b"file-c"
        )

    # A file with an unseen identity stays pending; approving it for an
    # unknown patient is a 404-style LookupError.
    monkeypatch.setattr(
        service_module,
        "extract_identity_tags",
        lambda raw: {"PatientID": "DNI-999", "PatientName": "Unknown^Nobody"},
    )
    other, _ = await RvgService.scan_bytes(db_session, test_clinic.id, "d.dcm", b"file-d")
    assert other.status == "pending"
    with pytest.raises(LookupError):
        await RvgService.approve(
            db_session, test_clinic.id, other.id, uuid4(), user_id, raw=b"file-d"
        )


@pytest.mark.asyncio
async def test_reject_keeps_row_for_audit(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    canned_tags: dict,
) -> None:
    row, _ = await RvgService.scan_bytes(db_session, test_clinic.id, "e.dcm", b"file-e")
    decided = await RvgService.reject(db_session, test_clinic.id, row.id, reason="wrong sensor")
    assert decided.status == "rejected"
    assert decided.error == "wrong sensor"
    with pytest.raises(RvgConflictError):
        await RvgService.reject(db_session, test_clinic.id, row.id)


@pytest.mark.asyncio
async def test_ambiguous_match_stays_suggestionless(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    canned_tags: dict,
) -> None:
    twin = Patient(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Test",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
    )
    db_session.add(twin)
    test_patient.date_of_birth = date(1990, 1, 1)
    await db_session.commit()

    row, _ = await RvgService.scan_bytes(db_session, test_clinic.id, "f.dcm", b"file-f")
    assert row.status == "pending"
    assert row.suggested_patient_id is None
    assert row.match_reason == "ambiguous"


@pytest.mark.asyncio
async def test_cross_clinic_isolation(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
    canned_tags: dict,
) -> None:
    other_clinic = await _second_clinic(db_session)
    user_id = await _user_id(db_session)

    mine, _ = await RvgService.scan_bytes(db_session, test_clinic.id, "g.dcm", b"shared-bytes")
    theirs, created = await RvgService.scan_bytes(
        db_session, other_clinic.id, "g.dcm", b"shared-bytes"
    )
    assert created is True
    assert theirs.id != mine.id

    # Approving with a patient from another clinic is a 404-style LookupError.
    with pytest.raises(LookupError):
        await RvgService.approve(
            db_session, other_clinic.id, theirs.id, test_patient.id, user_id, raw=b"shared-bytes"
        )
    # Queue listing never leaks across clinics.
    items, total = await RvgService.list_imports(db_session, other_clinic.id)
    assert total == 1
    assert items[0].id == theirs.id


@pytest.mark.asyncio
async def test_scan_then_approve_over_http(
    client,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    fake_storage: _FakeStorage,
    canned_tags: dict,
) -> None:
    """The real RVG flow over HTTP: scan parks the file in pending/, the
    approval queue lists it, and approve reads its bytes from there.

    Regression: the scan moved every handled file to processed/ while
    approve only looked in the clinic root, so a queued file could never be
    approved (404 'Source file no longer in the watch folder') and the
    button in the queue was dead.
    """
    from pathlib import Path

    watch_root = Path(str(tmp_path)) / "rvg-root"
    clinic_dir = watch_root / str(test_clinic.id)
    clinic_dir.mkdir(parents=True)
    (clinic_dir / "scan.dcm").write_bytes(b"fake-dicom-bytes")
    monkeypatch.setenv("DENTALPIN_RVG_WATCH_DIR", str(watch_root))

    scanned = await client.post(
        "/api/v1/imaging_viewer/rvg/scan",
        json={"retry_failed": False},
        headers=auth_headers,
    )
    assert scanned.status_code == 200, scanned.text
    assert scanned.json()["data"]["pending"] == 1
    assert (clinic_dir / "pending" / "scan.dcm").is_file()

    queue = await client.get(
        "/api/v1/imaging_viewer/rvg/imports",
        params={"status": "pending"},
        headers=auth_headers,
    )
    assert queue.status_code == 200, queue.text
    rows = queue.json()["data"]
    assert len(rows) == 1
    assert rows[0]["filename"] == "scan.dcm"

    approved = await client.post(
        f"/api/v1/imaging_viewer/rvg/imports/{rows[0]['id']}/approve",
        json={"patient_id": str(test_patient.id)},
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"
    assert any(p == b"fake-dicom-bytes" for p in fake_storage.files.values())
    # Decided -> retired out of pending/, and the queue no longer lists it.
    assert not (clinic_dir / "pending" / "scan.dcm").exists()
    assert (clinic_dir / "processed" / "scan.dcm").is_file()
    again = await client.post(
        f"/api/v1/imaging_viewer/rvg/imports/{rows[0]['id']}/approve",
        json={"patient_id": str(test_patient.id)},
        headers=auth_headers,
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_scan_watch_dir_files_by_outcome_and_drains_past_limit(
    test_clinic: Clinic, db_session: AsyncSession, tmp_path
) -> None:
    """A folder holding more than the batch limit drains over successive
    ticks. A row still awaiting a human decision is parked in pending/ so
    approve can read its bytes; a row the tick decided itself (here: a
    failed parse) goes to processed/. Either way later-sorting files are
    reached and ticks never re-hash."""
    from pathlib import Path

    watch = Path(str(tmp_path)) / "watch"
    watch.mkdir()
    for i in range(55):
        (watch / f"f{i:03d}.dcm").write_bytes(b"not-dicom-%d" % i)
    counts = await RvgService.scan_watch_dir(db_session, test_clinic.id, str(watch))
    assert counts["scanned"] == 50
    assert counts["failed"] == 50
    assert sorted(p.name for p in watch.iterdir() if p.is_file()) == [
        f"f{i:03d}.dcm" for i in range(50, 55)
    ]
    assert len(list((watch / "processed").iterdir())) == 50
    assert list((watch / "pending").iterdir()) == []
    counts2 = await RvgService.scan_watch_dir(db_session, test_clinic.id, str(watch))
    assert counts2["scanned"] == 5
    assert [p for p in watch.iterdir() if p.is_file()] == []
