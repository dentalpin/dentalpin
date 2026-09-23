"""imaging_ai: queue/list/cancel + background execution with a fake runner."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.imaging_ai import service as service_module
from app.modules.imaging_ai.models import JOB_DONE, JOB_FAILED
from app.modules.imaging_ai.runner import RunnerResult
from app.modules.imaging_ai.service import AiJobService
from app.modules.media import storage as media_storage
from app.modules.media.models import Document
from app.modules.patients.models import Patient


class FakeRunner:
    """Deterministic stand-in for nnU-Net (no torch anywhere near tests)."""

    name = "fake"

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok

    async def run(self, dicom_bytes: bytes, work_dir: Path):
        assert dicom_bytes == b"study-bytes"
        if not self.ok:
            return RunnerResult(ok=False, error="model exploded")
        return RunnerResult(
            ok=True,
            artifacts={"overlay.png": b"png-bytes"},
            log_excerpt="fake run",
        )


@pytest.fixture()
def fake_runner(monkeypatch: pytest.MonkeyPatch) -> FakeRunner:
    runner = FakeRunner()
    monkeypatch.setattr(service_module, "get_runner", lambda backend="nnunet": runner)
    return runner


class _FakeMediaStorage:
    """In-memory stand-in for the media storage backend (no filesystem)."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def store(self, data: bytes, path: str) -> str:
        self.files[path] = data
        return path

    async def retrieve(self, path: str) -> bytes:
        return self.files[path]


@pytest.fixture()
def fake_media_storage(monkeypatch: pytest.MonkeyPatch) -> _FakeMediaStorage:
    storage = _FakeMediaStorage()
    monkeypatch.setattr(media_storage, "get_storage_backend", lambda: storage)
    return storage


async def _document(db: AsyncSession, clinic: Clinic, patient: Patient) -> Document:
    user_id = (await db.execute(select(User))).scalars().first().id
    storage = media_storage.get_storage_backend()
    path = f"{clinic.id}/{patient.id}/2026-09/{uuid4()}.dcm"
    await storage.store(b"study-bytes", path)
    doc = Document(
        clinic_id=clinic.id,
        patient_id=patient.id,
        document_type="other",
        title="CBCT",
        original_filename="cbct.dcm",
        storage_path=path,
        mime_type="application/dicom",
        file_size=11,
        uploaded_by=user_id,
    )
    db.add(doc)
    await db.flush()
    return doc


@pytest.mark.asyncio
async def test_queue_get_list_cancel_happy_path(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    user_id = (await db_session.execute(select(User))).scalars().first().id
    doc = await _document(db_session, test_clinic, test_patient)

    job = await AiJobService.queue_job(
        db_session,
        test_clinic.id,
        test_patient.id,
        user_id,
        uuid4(),
        doc.id,
    )
    assert job.status == "queued"
    assert job.backend == "nnunet"

    fetched = await AiJobService.get_job(db_session, test_clinic.id, job.id)
    assert fetched is not None

    items, total = await AiJobService.list_jobs(db_session, test_clinic.id, test_patient.id)
    assert total == 1

    await AiJobService.cancel_job(db_session, job)
    assert job.status == "cancelled"

    with pytest.raises(ValueError):
        await AiJobService.cancel_job(db_session, job)


@pytest.mark.asyncio
async def test_queue_rejects_foreign_patient_or_document(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    user_id = (await db_session.execute(select(User))).scalars().first().id
    doc = await _document(db_session, test_clinic, test_patient)
    other = uuid4()
    with pytest.raises(LookupError):
        await AiJobService.queue_job(db_session, other, test_patient.id, user_id, uuid4(), doc.id)
    with pytest.raises(LookupError):
        await AiJobService.queue_job(
            db_session, test_clinic.id, test_patient.id, user_id, uuid4(), uuid4()
        )


@pytest.mark.asyncio
async def test_background_run_ingests_artifacts(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_runner: FakeRunner,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    user_id = (await db_session.execute(select(User))).scalars().first().id
    doc = await _document(db_session, test_clinic, test_patient)
    job = await AiJobService.queue_job(
        db_session, test_clinic.id, test_patient.id, user_id, uuid4(), doc.id
    )

    await AiJobService.execute_in_background(job.id, test_clinic.id)

    # The background run commits on its own session; expire the identity
    # map here or the re-read below returns the stale queued instance.
    # (Capture plain ids first — expire_all() also expires the fixtures.)
    clinic_id, job_id = test_clinic.id, job.id
    patient_id = test_patient.id
    db_session.expire_all()
    finished = await AiJobService.get_job(db_session, clinic_id, job_id)
    assert finished is not None
    assert finished.status == JOB_DONE
    assert len(finished.artifact_document_ids) == 1
    artifact = (
        await db_session.execute(
            select(Document).where(
                Document.id == finished.artifact_document_ids[0],
                Document.clinic_id == clinic_id,
            )
        )
    ).scalar_one_or_none()
    assert artifact is not None
    assert artifact.patient_id == patient_id


@pytest.mark.asyncio
async def test_background_run_marks_failure(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_runner: FakeRunner,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    fake_runner.ok = False
    user_id = (await db_session.execute(select(User))).scalars().first().id
    doc = await _document(db_session, test_clinic, test_patient)
    job = await AiJobService.queue_job(
        db_session, test_clinic.id, test_patient.id, user_id, uuid4(), doc.id
    )

    await AiJobService.execute_in_background(job.id, test_clinic.id)

    clinic_id, job_id = test_clinic.id, job.id
    db_session.expire_all()
    finished = await AiJobService.get_job(db_session, clinic_id, job_id)
    assert finished is not None
    assert finished.status == JOB_FAILED
    assert finished.error == "model exploded"


@pytest.mark.asyncio
async def test_cross_clinic_ids_resolve_to_nothing(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    other = uuid4()
    assert await AiJobService.get_job(db_session, other, uuid4()) is None
    _, total = await AiJobService.list_jobs(db_session, other)
    assert total == 0


@pytest.mark.asyncio
async def test_queue_rejects_unknown_backend(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    user_id = (await db_session.execute(select(User))).scalars().first().id
    with pytest.raises(ValueError):
        await AiJobService.queue_job(
            db_session,
            test_clinic.id,
            test_patient.id,
            user_id,
            uuid4(),
            uuid4(),
            backend="watson",
        )


def _tiny_dicom_bytes() -> bytes:
    """Minimal single-frame DICOM (2x2 grayscale) for the pano path."""
    import io

    import numpy as np
    import pydicom
    from pydicom.dataset import Dataset, FileDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    arr = np.arange(4, dtype=np.uint16).reshape(2, 2) * 1000
    file_meta = Dataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.StudyInstanceUID = generate_uid()
    ds.Modality = "OT"
    ds.Rows, ds.Columns = 2, 2
    ds.BitsAllocated, ds.BitsStored, ds.HighBit = 16, 16, 15
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelRepresentation = 0
    ds.PixelData = arr.tobytes()
    buf = io.BytesIO()
    pydicom.dcmwrite(buf, ds)
    return buf.getvalue()


STUB_MAIN = """import argparse
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--input", required=True)
p.add_argument("--output", required=True)
a = p.parse_args()
out = Path(a.output)
out.mkdir(parents=True, exist_ok=True)
# Minimal valid 1x1 PNG (exercises the thumbnail path on ingest).
png = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)
(out / "overlay.png").write_bytes(png)
print("stub pano done")
"""


@pytest.mark.asyncio
async def test_pano_backend_runs_stub_and_ingests(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_media_storage: _FakeMediaStorage,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from app.modules.imaging_ai.runner import PanoRunner

    (tmp_path / "main.py").write_text(STUB_MAIN)
    monkeypatch.setattr(
        service_module, "get_runner", lambda backend="nnunet": PanoRunner(app_dir=tmp_path)
    )

    user_id = (await db_session.execute(select(User))).scalars().first().id
    storage = media_storage.get_storage_backend()
    path = f"{test_clinic.id}/{test_patient.id}/2026-09/{uuid4()}.dcm"
    await storage.store(_tiny_dicom_bytes(), path)
    doc = Document(
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        document_type="other",
        title="Pano",
        original_filename="pano.dcm",
        storage_path=path,
        mime_type="application/dicom",
        file_size=64,
        uploaded_by=user_id,
    )
    db_session.add(doc)
    await db_session.flush()

    job = await AiJobService.queue_job(
        db_session,
        test_clinic.id,
        test_patient.id,
        user_id,
        uuid4(),
        doc.id,
        backend="pano",
    )
    assert job.backend == "pano"
    assert job.model_id == "dental-pano-ai"

    await AiJobService.execute_in_background(job.id, test_clinic.id)

    clinic_id, job_id = test_clinic.id, job.id
    db_session.expire_all()
    finished = await AiJobService.get_job(db_session, clinic_id, job_id)
    assert finished is not None
    assert finished.status == JOB_DONE
    assert len(finished.artifact_document_ids) == 1


@pytest.mark.asyncio
async def test_pano_runner_refuses_without_app(
    tmp_path,
) -> None:
    from app.modules.imaging_ai.runner import PanoRunner

    result = await PanoRunner(app_dir=tmp_path / "missing").run(b"whatever", tmp_path)
    assert result.ok is False
    assert "DENTALPIN_PANO_APP" in (result.error or "")


STUB_TESSERACT = """#!/bin/sh
# Minimal tesseract stand-in: `tesseract <input> <outbase> -l <lang>`.
echo "TOTAL 12,50" > "$2.txt"
"""

STUB_TESSERACT_BLANK = """#!/bin/sh
: > "$2.txt"
"""


def _stub_binary(tmp_path, name: str, body: str) -> str:
    import os

    path = tmp_path / name
    path.write_text(body)
    os.chmod(path, 0o755)
    return str(path)


@pytest.mark.asyncio
async def test_ocr_backend_runs_stub_and_ingests_text(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_media_storage: _FakeMediaStorage,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from app.modules.imaging_ai.runner import OcrRunner

    stub = _stub_binary(tmp_path, "tesseract", STUB_TESSERACT)
    monkeypatch.setattr(
        service_module, "get_runner", lambda backend="nnunet": OcrRunner(tesseract_bin=stub)
    )
    # Artifact ingest resolves the backend through media.service's own
    # binding (top-level import), so patch it too — otherwise artifacts
    # land in real storage and the test can't read them back.
    import app.modules.media.service as media_service_module

    monkeypatch.setattr(media_service_module, "get_storage_backend", lambda: fake_media_storage)

    user_id = (await db_session.execute(select(User))).scalars().first().id
    storage = media_storage.get_storage_backend()
    path = f"{test_clinic.id}/{test_patient.id}/2026-09/{uuid4()}.jpg"
    await storage.store(b"fake-receipt-bytes", path)
    doc = Document(
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        document_type="other",
        title="Receipt",
        original_filename="receipt.jpg",
        storage_path=path,
        mime_type="image/jpeg",
        file_size=18,
        uploaded_by=user_id,
    )
    db_session.add(doc)
    await db_session.flush()

    job = await AiJobService.queue_job(
        db_session,
        test_clinic.id,
        test_patient.id,
        user_id,
        uuid4(),
        doc.id,
        backend="ocr",
    )
    assert job.backend == "ocr"
    assert job.model_id == "tesseract-ocr"

    await AiJobService.execute_in_background(job.id, test_clinic.id)

    clinic_id, job_id, source_id = test_clinic.id, job.id, doc.id
    db_session.expire_all()
    finished = await AiJobService.get_job(db_session, clinic_id, job_id)
    assert finished is not None
    assert finished.status == JOB_DONE
    assert len(finished.artifact_document_ids) == 1

    artifact = await db_session.get(Document, UUID(str(finished.artifact_document_ids[0])))
    assert artifact is not None
    assert artifact.mime_type == "text/plain"
    assert "ai-transcript" in (artifact.tags or [])
    assert artifact.paired_document_id == source_id
    stored = await storage.retrieve(artifact.storage_path)
    assert b"TOTAL" in stored


@pytest.mark.asyncio
async def test_ocr_runner_refuses_without_binary(tmp_path) -> None:
    from app.modules.imaging_ai.runner import OcrRunner

    result = await OcrRunner(tesseract_bin="/nonexistent/tesseract").run(b"whatever", tmp_path)
    assert result.ok is False
    assert "tesseract not found" in (result.error or "")


@pytest.mark.asyncio
async def test_ocr_blank_image_succeeds_without_artifacts(tmp_path) -> None:
    from app.modules.imaging_ai.runner import OcrRunner

    stub = _stub_binary(tmp_path, "tesseract-blank", STUB_TESSERACT_BLANK)
    result = await OcrRunner(tesseract_bin=stub).run(b"whatever", tmp_path)
    assert result.ok is True
    assert result.artifacts == {}
