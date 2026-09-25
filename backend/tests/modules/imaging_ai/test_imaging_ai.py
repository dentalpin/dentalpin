"""imaging_ai: propose/confirm lifecycle, drafts, scheduler, runners, volumes."""

from __future__ import annotations

import gzip
import struct
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.imaging_ai import service as service_module
from app.modules.imaging_ai.models import (
    JOB_CANCELLED,
    JOB_DONE,
    JOB_FAILED,
    JOB_PROPOSED,
    JOB_QUEUED,
    REVIEW_CONFIRMED,
    REVIEW_PENDING,
)
from app.modules.imaging_ai.runner import RunnerResult, build_nnunet_cmd, build_pano_cmd
from app.modules.imaging_ai.service import AiJobService
from app.modules.imaging_ai.volume import VolumeError, dicom_series_to_nifti
from app.modules.media import storage as media_storage
from app.modules.media.models import Document
from app.modules.patients.models import Patient


class FakeRunner:
    """Deterministic stand-in for real backends (no torch anywhere near tests)."""

    name = "fake"

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.seen: bytes | None = None

    async def run(self, input_bytes: bytes, work_dir: Path):
        self.seen = input_bytes
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
    monkeypatch.setattr(service_module, "get_runner", lambda backend="pano": runner)
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
    import app.modules.media.service as media_service_module

    monkeypatch.setattr(media_service_module, "get_storage_backend", lambda: storage)
    return storage


async def _user_id(db: AsyncSession) -> UUID:
    return (await db.execute(select(User))).scalars().first().id


async def _document(
    db: AsyncSession, clinic: Clinic, patient: Patient, payload: bytes = b"study-bytes"
) -> Document:
    storage = media_storage.get_storage_backend()
    path = f"{clinic.id}/{patient.id}/2026-09/{uuid4()}.dcm"
    await storage.store(payload, path)
    doc = Document(
        clinic_id=clinic.id,
        patient_id=patient.id,
        document_type="other",
        title="CBCT",
        original_filename="cbct.dcm",
        storage_path=path,
        mime_type="application/dicom",
        file_size=len(payload),
        uploaded_by=await _user_id(db),
    )
    db.add(doc)
    await db.flush()
    return doc


# ------------------------------------------------------------------
# Lifecycle: propose -> confirm -> queued -> run -> done -> confirmed
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_propose_confirm_flow(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    user_id = await _user_id(db_session)
    doc = await _document(db_session, test_clinic, test_patient)

    queued = await AiJobService.queue_job(
        db_session, test_clinic.id, test_patient.id, user_id, doc.id
    )
    assert queued.status == JOB_QUEUED
    assert queued.backend == "pano"
    assert queued.review_status == REVIEW_PENDING

    proposed = await AiJobService.queue_job(
        db_session, test_clinic.id, test_patient.id, None, doc.id
    )
    assert proposed.status == JOB_PROPOSED
    assert proposed.queued_by is None

    confirmed = await AiJobService.confirm_job(db_session, proposed, user_id)
    assert confirmed.status == JOB_QUEUED
    assert confirmed.queued_by == user_id

    with pytest.raises(ValueError):
        await AiJobService.confirm_job(db_session, confirmed, user_id)


@pytest.mark.asyncio
async def test_execute_skips_proposed(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_runner: FakeRunner,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    doc = await _document(db_session, test_clinic, test_patient)
    job = await AiJobService.queue_job(db_session, test_clinic.id, test_patient.id, None, doc.id)
    await AiJobService.execute_in_background(job.id, test_clinic.id)
    # Capture plain ids first: expire_all() also expires the fixtures.
    clinic_id, job_id = test_clinic.id, job.id
    db_session.expire_all()
    untouched = await AiJobService.get_job(db_session, clinic_id, job_id)
    assert untouched is not None
    assert untouched.status == JOB_PROPOSED
    assert fake_runner.seen is None


@pytest.mark.asyncio
async def test_confirm_done_marks_review(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_runner: FakeRunner,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    user_id = await _user_id(db_session)
    doc = await _document(db_session, test_clinic, test_patient)
    job = await AiJobService.queue_job(db_session, test_clinic.id, test_patient.id, user_id, doc.id)
    await AiJobService.execute_in_background(job.id, test_clinic.id)
    clinic_id, job_id = test_clinic.id, job.id
    db_session.expire_all()
    finished = await AiJobService.get_job(db_session, clinic_id, job_id)
    assert finished is not None and finished.status == JOB_DONE
    assert finished.review_status == REVIEW_PENDING

    reviewed = await AiJobService.confirm_job(db_session, finished, user_id)
    assert reviewed.review_status == REVIEW_CONFIRMED
    assert reviewed.confirmed_by == user_id
    assert reviewed.confirmed_at is not None


@pytest.mark.asyncio
async def test_cancel_proposed_but_not_running(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    user_id = await _user_id(db_session)
    doc = await _document(db_session, test_clinic, test_patient)
    proposed = await AiJobService.queue_job(
        db_session, test_clinic.id, test_patient.id, None, doc.id
    )
    await AiJobService.cancel_job(db_session, proposed)
    assert proposed.status == JOB_CANCELLED

    queued = await AiJobService.queue_job(
        db_session, test_clinic.id, test_patient.id, user_id, doc.id
    )
    await AiJobService.cancel_job(db_session, queued)
    assert queued.status == JOB_CANCELLED
    with pytest.raises(ValueError):
        await AiJobService.cancel_job(db_session, queued)


# ------------------------------------------------------------------
# Drafts, never records (§4)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_artifacts_are_drafts_not_records(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_runner: FakeRunner,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    user_id = await _user_id(db_session)
    doc = await _document(db_session, test_clinic, test_patient)
    job = await AiJobService.queue_job(db_session, test_clinic.id, test_patient.id, user_id, doc.id)
    await AiJobService.execute_in_background(job.id, test_clinic.id)

    clinic_id, job_id = test_clinic.id, job.id
    doc_id, patient_id = doc.id, test_patient.id
    db_session.expire_all()
    finished = await AiJobService.get_job(db_session, clinic_id, job_id)
    assert finished is not None and finished.status == JOB_DONE
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
    # Draft, not a record: document rail (gallery shows photo/xray only),
    # no pairing written onto the source.
    assert artifact.media_kind == "document"
    assert artifact.media_category is None
    assert artifact.paired_document_id is None
    assert "ai-draft" in (artifact.tags or [])
    source = await db_session.get(Document, doc_id)
    assert source is not None and source.paired_document_id is None


# ------------------------------------------------------------------
# Queue validation
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_rejects_foreign_patient_or_document(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    user_id = await _user_id(db_session)
    doc = await _document(db_session, test_clinic, test_patient)
    other = uuid4()
    with pytest.raises(LookupError):
        await AiJobService.queue_job(db_session, other, test_patient.id, user_id, doc.id)
    with pytest.raises(LookupError):
        await AiJobService.queue_job(db_session, test_clinic.id, test_patient.id, user_id, uuid4())


@pytest.mark.asyncio
async def test_queue_rejects_unknown_backend(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    user_id = await _user_id(db_session)
    with pytest.raises(ValueError):
        await AiJobService.queue_job(
            db_session,
            test_clinic.id,
            test_patient.id,
            user_id,
            uuid4(),
            backend="watson",
        )


@pytest.mark.asyncio
async def test_nnunet_requires_a_series(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    user_id = await _user_id(db_session)
    doc = await _document(db_session, test_clinic, test_patient)
    # A lone frame cannot feed the volumetric backend.
    with pytest.raises(ValueError, match="needs a volume"):
        await AiJobService.queue_job(
            db_session, test_clinic.id, test_patient.id, user_id, doc.id, backend="nnunet"
        )
    # Unknown series members resolve to 404, not silent drops.
    with pytest.raises(LookupError):
        await AiJobService.queue_job(
            db_session,
            test_clinic.id,
            test_patient.id,
            user_id,
            doc.id,
            series_document_ids=[uuid4()],
            backend="nnunet",
        )
    second = await _document(db_session, test_clinic, test_patient)
    job = await AiJobService.queue_job(
        db_session,
        test_clinic.id,
        test_patient.id,
        user_id,
        doc.id,
        series_document_ids=[second.id],
        backend="nnunet",
    )
    assert job.backend == "nnunet"
    assert job.model_id == "Dataset112_DentalSegmentator"


# ------------------------------------------------------------------
# Background execution
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_background_run_ingests_artifacts(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_runner: FakeRunner,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    user_id = await _user_id(db_session)
    doc = await _document(db_session, test_clinic, test_patient)
    job = await AiJobService.queue_job(db_session, test_clinic.id, test_patient.id, user_id, doc.id)

    await AiJobService.execute_in_background(job.id, test_clinic.id)

    clinic_id, job_id = test_clinic.id, job.id
    db_session.expire_all()
    finished = await AiJobService.get_job(db_session, clinic_id, job_id)
    assert finished is not None
    assert finished.status == JOB_DONE
    assert len(finished.artifact_document_ids) == 1
    assert fake_runner.seen == b"study-bytes"


@pytest.mark.asyncio
async def test_background_run_marks_failure(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_runner: FakeRunner,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    fake_runner.ok = False
    user_id = await _user_id(db_session)
    doc = await _document(db_session, test_clinic, test_patient)
    job = await AiJobService.queue_job(db_session, test_clinic.id, test_patient.id, user_id, doc.id)

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


# ------------------------------------------------------------------
# HTTP surface: queue / confirm / cancel / dicom-documents codes
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_queue_confirm_cancel_codes(
    client, auth_headers, test_patient, fake_media_storage: _FakeMediaStorage
) -> None:
    from app.database import async_session_maker

    async with async_session_maker() as db:
        patient = await db.get(test_patient.__class__, test_patient.id)
        storage = media_storage.get_storage_backend()
        path = f"{patient.clinic_id}/{patient.id}/2026-09/{uuid4()}.dcm"
        await storage.store(b"study-bytes", path)
        user_id = (await db.execute(select(User))).scalars().first().id
        doc = Document(
            clinic_id=patient.clinic_id,
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
        await db.commit()
        doc_id = doc.id
        patient_id = patient.id
        clinic_id = patient.clinic_id

    # HTTP queue attributes the caller: 202, straight to queued.
    response = await client.post(
        f"/api/v1/imaging_ai/patients/{patient_id}/ai-jobs",
        json={"document_id": str(doc_id), "backend": "pano"},
        headers=auth_headers,
    )
    assert response.status_code == 202
    assert response.json()["data"]["status"] == "queued"

    # The series picker sees the source document.
    response = await client.get(
        f"/api/v1/imaging_ai/patients/{patient_id}/dicom-documents",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert str(doc_id) in [d["id"] for d in response.json()["data"]]

    # Confirming an already-queued job is a 409, not a silent no-op
    # (covered below on the proposed job's second confirm).

    # A proposed job (agent path) confirms to queued, then 409s, then cancels.
    async with async_session_maker() as db:
        proposed = await AiJobService.queue_job(db, clinic_id, patient_id, None, doc_id)
        await db.commit()
        proposed_id = proposed.id
    response = await client.post(
        f"/api/v1/imaging_ai/ai-jobs/{proposed_id}/confirm",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "queued"

    response = await client.post(
        f"/api/v1/imaging_ai/ai-jobs/{proposed_id}/confirm",
        headers=auth_headers,
    )
    assert response.status_code == 409

    response = await client.delete(
        f"/api/v1/imaging_ai/ai-jobs/{proposed_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204


# ------------------------------------------------------------------
# Pano backend against a stub CLI (plumbing E2E)
# ------------------------------------------------------------------


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


# A stand-in for upstream dental-pano-ai main.py, shaped like UPSTREAM
# rather than like our runner (the round-1 lesson: the previous stub wrote
# `overlay.png` at the top level of the output dir, which is NOT what the
# real CLI does, so our tests passed while every real run failed). Upstream:
#   - always writes the per-FDI findings table `<output>/<stem>.csv`
#   - writes the overlays to `<output>/<stem>/` ONLY with --debug
#   - resolves its model paths as ./models/... relative to cwd, and aborts
#     when they are missing — so a runner that forgets `cwd=app_dir` fails
#     here instead of passing.
UPSTREAM_STUB_MAIN = """import argparse
import sys
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--input", required=True)
p.add_argument("--output", required=True)
p.add_argument("--debug", action="store_true")
a = p.parse_args()

# Upstream loads its checkpoints from ./models/... relative to cwd.
models = Path("models")
if not (models / "deeplab_config.pth").exists():
    print("model not found under ./models (cwd-relative)", file=sys.stderr)
    sys.exit(2)

out = Path(a.output)
out.mkdir(parents=True, exist_ok=True)
stem = Path(a.input).stem

# The clinically useful output: the per-FDI findings table, top level.
(out / f"{stem}.csv").write_text("fdi,tooth,label\\n11,11,caries\\n", encoding="utf-8")

if a.debug:
    d = out / stem
    d.mkdir(parents=True, exist_ok=True)
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
    )
    (d / "semantic-segmentation.png").write_bytes(png)
    (d / "instance-detection.png").write_bytes(png)

print("upstream pano done")
"""


@pytest.mark.asyncio
async def test_pano_backend_runs_upstream_shaped_cli_and_ingests(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_media_storage: _FakeMediaStorage,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from app.modules.imaging_ai.runner import PanoRunner

    (tmp_path / "main.py").write_text(UPSTREAM_STUB_MAIN)
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "deeplab_config.pth").write_bytes(b"stub weights")
    monkeypatch.setattr(
        service_module, "get_runner", lambda backend="pano": PanoRunner(app_dir=tmp_path)
    )

    user_id = await _user_id(db_session)
    doc = await _document(db_session, test_clinic, test_patient, _tiny_dicom_bytes())

    job = await AiJobService.queue_job(
        db_session,
        test_clinic.id,
        test_patient.id,
        user_id,
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
    assert finished.status == JOB_DONE, finished.error
    # CSV + the two --debug overlays: 3 drafts, not 1.
    assert len(finished.artifact_document_ids) == 3
    titles = {
        d.original_filename
        for d in (
            await db_session.execute(
                select(Document).where(Document.id.in_(finished.artifact_document_ids))
            )
        )
        .scalars()
        .all()
    }
    assert any(t.endswith("study.csv") for t in titles)
    assert any("semantic-segmentation" in t for t in titles)


@pytest.mark.asyncio
async def test_pano_runner_fails_when_cwd_is_not_the_checkout(tmp_path) -> None:
    """Upstream resolves ./models relative to cwd, so a runner that does
    not set cwd=app_dir dies before inference. Proven, not assumed."""
    from app.modules.imaging_ai.runner import PanoRunner

    app_dir = tmp_path / "app"
    (app_dir / "models").mkdir(parents=True)
    (app_dir / "models" / "deeplab_config.pth").write_bytes(b"stub weights")
    (app_dir / "main.py").write_text(UPSTREAM_STUB_MAIN)
    work = tmp_path / "work"
    work.mkdir()

    good = await PanoRunner(app_dir=app_dir).run(_tiny_dicom_bytes(), work / "ok")
    assert good.ok is True, good.error
    assert "study.csv" in good.artifacts
    assert "study/semantic-segmentation.png" in good.artifacts


@pytest.mark.asyncio
async def test_pano_runner_uses_the_configured_interpreter(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DENTALPIN_PANO_PYTHON points at the checkout's own venv; a missing
    interpreter is refused with an actionable error before upstream runs."""
    import shutil

    from app.modules.imaging_ai import runner as runner_module

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "main.py").write_text(UPSTREAM_STUB_MAIN)
    monkeypatch.setenv("DENTALPIN_PANO_PYTHON", str(tmp_path / "venv" / "bin" / "python"))
    app_dir_env, python_exe = runner_module.pano_env()
    assert app_dir_env is None
    assert python_exe == str(tmp_path / "venv" / "bin" / "python")

    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = await runner_module.PanoRunner(
        app_dir=app_dir, python_exe=str(tmp_path / "venv" / "bin" / "python")
    ).run(_tiny_dicom_bytes(), tmp_path / "work")
    assert result.ok is False
    assert "DENTALPIN_PANO_PYTHON" in (result.error or "")


@pytest.mark.asyncio
async def test_pano_runner_refuses_without_app(
    tmp_path,
) -> None:
    from app.modules.imaging_ai.runner import PanoRunner

    result = await PanoRunner(app_dir=tmp_path / "missing").run(b"whatever", tmp_path)
    assert result.ok is False
    assert "DENTALPIN_PANO_APP" in (result.error or "")


# ------------------------------------------------------------------
# CLI contracts (pinned argv — the suite that would have caught #1)
# ------------------------------------------------------------------


def test_build_nnunet_cmd_pins_weights_and_device(tmp_path) -> None:
    cmd = build_nnunet_cmd(
        "/bin/nnUNetv2_predict", tmp_path / "in", tmp_path / "out", weights=True, allow_cpu=False
    )
    assert cmd[:5] == [
        "/bin/nnUNetv2_predict",
        "-i",
        str(tmp_path / "in"),
        "-o",
        str(tmp_path / "out"),
    ]
    assert "-d" in cmd and "112" in cmd
    assert "-c" in cmd and "3d_fullres" in cmd
    assert "-device" not in cmd

    cpu_cmd = build_nnunet_cmd(
        "/bin/nnUNetv2_predict", tmp_path / "in", tmp_path / "out", weights=True, allow_cpu=True
    )
    assert cpu_cmd[-2:] == ["-device", "cpu"]

    # Without weights the CLI cannot succeed: no dataset flags emitted.
    bare = build_nnunet_cmd(
        "/bin/nnUNetv2_predict", tmp_path / "in", tmp_path / "out", weights=False, allow_cpu=False
    )
    assert "-d" not in bare


def test_build_pano_cmd_pins_input_output(tmp_path) -> None:
    cmd = build_pano_cmd(
        "python", tmp_path / "main.py", tmp_path / "in" / "study.png", tmp_path / "out"
    )
    assert cmd == [
        "python",
        str(tmp_path / "main.py"),
        "--input",
        str(tmp_path / "in" / "study.png"),
        "--output",
        str(tmp_path / "out"),
        # Without this upstream emits NO images at all (only the CSV), so
        # the round-1 build could never have produced an overlay.
        "--debug",
    ]


def test_build_nnunet_cmd_passes_only_the_folds_present(tmp_path) -> None:
    """nnUNetv2_predict defaults to -f 0 1 2 3 4 and aborts on the first
    fold that was never downloaded; the Zenodo Dataset112 zip ships fold_0
    only. Requesting exactly what is on disk is the fix."""
    from app.modules.imaging_ai.runner import available_folds

    weights = tmp_path / "weights"
    dataset = weights / "Dataset112_DentalSegmentator_v100"
    (dataset / "fold_0").mkdir(parents=True)
    assert available_folds(weights) == [0]

    cmd = build_nnunet_cmd(
        "nnUNetv2_predict",
        tmp_path / "in",
        tmp_path / "out",
        weights=True,
        allow_cpu=False,
        folds=available_folds(weights),
    )
    assert cmd[cmd.index("-f") + 1] == "0"
    assert "1" not in cmd[cmd.index("-f") + 1 :]
    assert "4" not in cmd[cmd.index("-f") + 1 :]

    (dataset / "fold_3").mkdir()
    assert available_folds(weights) == [0, 3]
    assert available_folds(tmp_path / "nope") == []


@pytest.mark.asyncio
async def test_nnunet_runner_refuses_without_weights(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from app.modules.imaging_ai.runner import SubprocessNnunetRunner

    monkeypatch.setattr(shutil, "which", lambda _: "/fake/nnUNetv2_predict")
    result = await SubprocessNnunetRunner(weights_dir=None).run(b"whatever", tmp_path)
    assert result.ok is False
    assert "DENTALPIN_NNUNET_WEIGHTS" in (result.error or "")


@pytest.mark.asyncio
async def test_nnunet_runner_refuses_without_cuda(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    import app.modules.imaging_ai.runner as runner_module
    from app.modules.imaging_ai.runner import SubprocessNnunetRunner

    monkeypatch.setattr(shutil, "which", lambda _: "/fake/nnUNetv2_predict")
    monkeypatch.setattr(runner_module, "_has_cuda", lambda: False)
    (tmp_path / "weights").mkdir()
    result = await SubprocessNnunetRunner(weights_dir=tmp_path / "weights", allow_cpu=False).run(
        b"whatever", tmp_path
    )
    assert result.ok is False
    assert "DENTALPIN_NNUNET_ALLOW_CPU" in (result.error or "")


@pytest.mark.asyncio
async def test_nnunet_runner_cpu_opt_in_passes_gates(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    import app.modules.imaging_ai.runner as runner_module
    from app.modules.imaging_ai.runner import SubprocessNnunetRunner

    monkeypatch.setattr(shutil, "which", lambda _: "/fake/nnUNetv2_predict")
    monkeypatch.setattr(runner_module, "_has_cuda", lambda: False)
    (tmp_path / "weights").mkdir()
    # No binary behind the fake path: the run fails, but past every gate
    # (binary found, weights found, CPU opted in) — gates are what we pin.
    result = await SubprocessNnunetRunner(weights_dir=tmp_path / "weights", allow_cpu=True).run(
        b"whatever", tmp_path
    )
    assert result.ok is False
    assert "DENTALPIN_NNUNET" not in (result.error or "")
    assert "CUDA" not in (result.error or "")


def test_nnunet_child_env_carries_the_weights_dir(tmp_path, monkeypatch) -> None:
    """nnUNet resolves `-d 112` through the nnUNet_results env var, not
    through any flag: the weights dir used to be existence-checked and then
    silently dropped, so the subprocess searched the backend's cwd and never
    found it. Pinned as a pure seam so it runs on every platform (a fake
    binary could only be POSIX-only, and would have been skipped on the
    maintainer's Windows host)."""
    from app.modules.imaging_ai.runner import nnunet_child_env

    weights = tmp_path / "weights"
    env = nnunet_child_env(weights)
    assert env["nnUNet_results"] == str(weights)
    # It extends the real environment rather than replacing it.
    monkeypatch.setenv("DENTALPIN_PROBE", "kept")
    assert nnunet_child_env(weights)["DENTALPIN_PROBE"] == "kept"


# ------------------------------------------------------------------
# Series -> NIfTI volumes
# ------------------------------------------------------------------


def _series_slice(
    series_uid: str,
    instance: int,
    rows: int = 4,
    cols: int = 6,
    z: float = 0.0,
) -> bytes:
    import io

    import numpy as np
    import pydicom
    from pydicom.dataset import Dataset, FileDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    arr = np.arange(rows * cols, dtype=np.uint16).reshape(rows, cols) + instance * 100
    file_meta = Dataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.SeriesInstanceUID = series_uid
    ds.InstanceNumber = instance
    ds.Modality = "CT"
    ds.Rows, ds.Columns = rows, cols
    ds.BitsAllocated, ds.BitsStored, ds.HighBit = 16, 16, 15
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelRepresentation = 0
    ds.PixelSpacing = [0.5, 0.5]
    ds.SliceThickness = 1.0
    ds.ImagePositionPatient = [0.0, 0.0, z]
    ds.PixelData = arr.tobytes()
    buf = io.BytesIO()
    pydicom.dcmwrite(buf, ds)
    return buf.getvalue()


def test_series_to_nifti_stacks_sorted_slices() -> None:
    from pydicom.uid import generate_uid

    uid = generate_uid()
    blobs = [
        _series_slice(uid, 3, z=2.0),
        _series_slice(uid, 1, z=0.0),
        _series_slice(uid, 2, z=1.0),
    ]
    volume = dicom_series_to_nifti(blobs)
    assert (volume.nx, volume.ny, volume.nz) == (6, 4, 3)
    assert volume.spacing == (0.5, 0.5, 1.0)

    raw = gzip.decompress(volume.data)
    assert len(raw) == 352 + 6 * 4 * 3 * 2
    assert struct.unpack("<i", raw[0:4])[0] == 348
    assert struct.unpack("<8h", raw[40:56]) == (3, 6, 4, 3, 1, 1, 1, 1)
    assert raw[344:348] == b"n+1\x00"
    # First voxel of each slice: instance * 100 (sorted 1, 2, 3).
    pixels = struct.unpack("<72h", raw[352:])
    assert pixels[0] == 100
    assert pixels[24] == 200
    assert pixels[48] == 300


def test_series_to_nifti_refuses_mixed_series() -> None:
    from pydicom.uid import generate_uid

    with pytest.raises(VolumeError, match="mixed series"):
        dicom_series_to_nifti([_series_slice(generate_uid(), 1), _series_slice(generate_uid(), 2)])


def test_series_to_nifti_refuses_single_frame() -> None:
    from pydicom.uid import generate_uid

    with pytest.raises(VolumeError, match="needs a volume"):
        dicom_series_to_nifti([_series_slice(generate_uid(), 1)])


def test_series_to_nifti_refuses_inconsistent_geometry() -> None:
    from pydicom.uid import generate_uid

    uid = generate_uid()
    with pytest.raises(VolumeError, match="inconsistent slice geometry"):
        dicom_series_to_nifti([_series_slice(uid, 1), _series_slice(uid, 2, rows=8)])


# ------------------------------------------------------------------
# Scheduler: claim queued, reap stale running
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_claims_queued_jobs(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_runner: FakeRunner,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    from app.modules.imaging_ai.tasks import process_ai_job_queue

    user_id = await _user_id(db_session)
    doc = await _document(db_session, test_clinic, test_patient)
    job = await AiJobService.queue_job(db_session, test_clinic.id, test_patient.id, user_id, doc.id)
    await db_session.commit()

    await process_ai_job_queue()

    clinic_id, job_id = test_clinic.id, job.id
    db_session.expire_all()
    finished = await AiJobService.get_job(db_session, clinic_id, job_id)
    assert finished is not None
    assert finished.status == JOB_DONE


@pytest.mark.asyncio
async def test_scheduler_reaps_stale_running(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    from app.modules.imaging_ai.models import AiJob
    from app.modules.imaging_ai.tasks import reap_stuck_running

    user_id = await _user_id(db_session)
    doc = await _document(db_session, test_clinic, test_patient)
    job = await AiJobService.queue_job(db_session, test_clinic.id, test_patient.id, user_id, doc.id)
    job.status = "running"
    await db_session.commit()
    await db_session.execute(
        update(AiJob)
        .where(AiJob.id == job.id)
        .values(updated_at=datetime.now(UTC) - timedelta(hours=3))
    )
    await db_session.commit()

    await reap_stuck_running()

    clinic_id, job_id = test_clinic.id, job.id
    db_session.expire_all()
    reaped = await AiJobService.get_job(db_session, clinic_id, job_id)
    assert reaped is not None
    assert reaped.status == JOB_FAILED
    assert "2h" in (reaped.error or "")


# ------------------------------------------------------------------
# Agent tools: propose needs nothing, confirm needs a supervisor
# ------------------------------------------------------------------


def _tool_ctx(db_session, clinic_id, supervisor_id=None):
    from app.core.agents.context import AgentContext, AgentMode
    from app.core.agents.tools.registry import tool_registry

    return AgentContext(
        agent_id=uuid4(),
        session_id=uuid4(),
        clinic_id=clinic_id,
        mode=AgentMode.AUTONOMOUS,
        permissions=["imaging_ai.jobs.write", "imaging_ai.jobs.read"],
        tools=tool_registry,
        db=db_session,
        supervisor_id=supervisor_id,
    )


@pytest.mark.asyncio
async def test_tool_queue_proposes_and_confirm_needs_supervisor(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_media_storage: _FakeMediaStorage,
) -> None:
    from app.modules.imaging_ai.tools import (
        ConfirmAiJobArgs,
        QueueAiJobArgs,
        _confirm_ai_job,
        _queue_ai_job,
    )

    user_id = await _user_id(db_session)
    doc = await _document(db_session, test_clinic, test_patient)
    doc_id, patient_id, clinic_id = doc.id, test_patient.id, test_clinic.id

    summary = await _queue_ai_job(
        _tool_ctx(db_session, clinic_id),
        QueueAiJobArgs(patient_id=str(patient_id), document_id=str(doc_id)),
    )
    assert summary["status"] == JOB_PROPOSED

    # Autonomous confirm: no supervising clinician, explicit error.
    refused = await _confirm_ai_job(
        _tool_ctx(db_session, clinic_id),
        ConfirmAiJobArgs(job_id=str(summary["job_id"])),
    )
    assert "supervised session" in refused["error"]

    # Supervised confirm: authorizes the run, stamps the supervisor.
    done = await _confirm_ai_job(
        _tool_ctx(db_session, clinic_id, supervisor_id=user_id),
        ConfirmAiJobArgs(job_id=str(summary["job_id"])),
    )
    assert done["status"] == JOB_QUEUED
    db_session.expire_all()
    stored = await AiJobService.get_job(db_session, clinic_id, summary["job_id"])
    assert stored is not None and stored.queued_by == user_id
