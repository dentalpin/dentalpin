"""imaging_viewer: index/list/get/archive + tenant isolation."""

from __future__ import annotations

import io
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.imaging_viewer import service as service_module
from app.modules.imaging_viewer.service import ImagingStudyService, extract_dicom_tags
from app.modules.media.models import Document
from app.modules.patients.models import Patient


class _FakeStorage:
    """In-memory stand-in for the media storage backend (no filesystem)."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def retrieve(self, path: str) -> bytes:
        return self.files[path]


@pytest.fixture()
def fake_storage(monkeypatch: pytest.MonkeyPatch) -> _FakeStorage:
    storage = _FakeStorage()
    monkeypatch.setattr(service_module, "get_storage_backend", lambda: storage)
    return storage


async def _document(
    db: AsyncSession,
    clinic: Clinic,
    patient: Patient,
    storage: _FakeStorage,
    mime_type: str = "application/dicom",
) -> Document:
    user_id = (await db.execute(select(User))).scalars().first().id
    path = f"{clinic.id}/{patient.id}/2026-09/{uuid4()}.dcm"
    storage.files[path] = b"not-real-dicom-bytes"
    doc = Document(
        clinic_id=clinic.id,
        patient_id=patient.id,
        document_type="other",
        title="CBCT",
        original_filename="cbct.dcm",
        storage_path=path,
        mime_type=mime_type,
        file_size=22,
        uploaded_by=user_id,
    )
    db.add(doc)
    await db.flush()
    return doc


@pytest.mark.asyncio
async def test_index_get_list_archive_happy_path(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    doc = await _document(db_session, test_clinic, test_patient, fake_storage)

    study, created = await ImagingStudyService.index_study(
        db_session,
        test_clinic.id,
        test_patient.id,
        doc.id,
        study_uid="1.2.3.4",
        modality="CT",
    )
    assert study.study_uid == "1.2.3.4"
    assert study.modality == "CT"
    assert study.status == "active"
    assert created is True

    fetched = await ImagingStudyService.get_study(db_session, test_clinic.id, study.id)
    assert fetched is not None
    assert fetched.id == study.id

    items, total = await ImagingStudyService.list_studies(
        db_session, test_clinic.id, test_patient.id
    )
    assert total == 1
    assert items[0].id == study.id

    await ImagingStudyService.archive_study(db_session, study)

    items, total = await ImagingStudyService.list_studies(
        db_session, test_clinic.id, test_patient.id
    )
    assert total == 0
    # Soft-delete keeps the row fetchable for historical refs (M2).
    fetched = await ImagingStudyService.get_study(db_session, test_clinic.id, study.id)
    assert fetched is not None
    assert fetched.status == "archived"


@pytest.mark.asyncio
async def test_cross_clinic_ids_resolve_to_nothing(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    doc = await _document(db_session, test_clinic, test_patient, fake_storage)
    study, _created = await ImagingStudyService.index_study(
        db_session, test_clinic.id, test_patient.id, doc.id, study_uid="9.9.9"
    )

    other_clinic = uuid4()
    assert await ImagingStudyService.get_study(db_session, other_clinic, study.id) is None
    _, total = await ImagingStudyService.list_studies(db_session, other_clinic, test_patient.id)
    assert total == 0
    with pytest.raises(LookupError):
        await ImagingStudyService.get_frame_bytes(db_session, other_clinic, study.id)
    with pytest.raises(LookupError):
        await ImagingStudyService.index_study(db_session, other_clinic, test_patient.id, doc.id)


@pytest.mark.asyncio
async def test_reindex_same_document_returns_existing_row(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    """Idempotent indexing: a shared StudyInstanceUID (or a double POST)
    returns the existing active row instead of duplicating it."""
    doc = await _document(db_session, test_clinic, test_patient, fake_storage)
    first, created_first = await ImagingStudyService.index_study(
        db_session, test_clinic.id, test_patient.id, doc.id, study_uid="7.7.7"
    )
    assert created_first is True
    second, created_second = await ImagingStudyService.index_study(
        db_session, test_clinic.id, test_patient.id, doc.id, study_uid="7.7.7"
    )
    assert created_second is False
    assert second.id == first.id
    items, total = await ImagingStudyService.list_studies(
        db_session, test_clinic.id, test_patient.id
    )
    assert total == 1


def test_extract_dicom_tags_degrades_to_empty_on_garbage() -> None:
    assert extract_dicom_tags(b"not-real-dicom-bytes") == {}


def test_dicom_mime_accepted_for_upload() -> None:
    """DICOM uploads must validate: the whole arc starts at upload."""
    import io

    from fastapi import UploadFile
    from starlette.datastructures import Headers

    from app.modules.media.validation import validate_mime_type

    upload = UploadFile(
        filename="cbct.dcm",
        file=io.BytesIO(b"fake"),
        headers=Headers({"content-type": "application/dicom"}),
    )
    assert validate_mime_type(upload) == "application/dicom"


@pytest.mark.asyncio
async def test_study_date_parsed_from_tags(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    """StudyDate tag lands on the column (listings always carry a date)."""
    storage = fake_storage
    path = f"{test_clinic.id}/{test_patient.id}/2026-09/{uuid4()}.dcm"
    storage.files[path] = _dicom_bytes(study_date="20260504")
    doc2 = Document(
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        document_type="other",
        title="DX",
        original_filename="dx.dcm",
        storage_path=path,
        mime_type="application/dicom",
        file_size=10,
        uploaded_by=(await db_session.execute(select(User))).scalars().first().id,
    )
    db_session.add(doc2)
    await db_session.flush()
    study, _ = await ImagingStudyService.index_study(
        db_session, test_clinic.id, test_patient.id, doc2.id
    )
    assert study.study_date is not None
    assert (study.study_date.year, study.study_date.month, study.study_date.day) == (
        2026,
        5,
        4,
    )
    assert study.dicom_metadata.get("StudyDate") == "20260504"


def _dicom_bytes(
    rows: int = 64,
    cols: int = 64,
    study_date: str | None = None,
    window: tuple[int, int] | None = None,
    mono1: bool = False,
) -> bytes:
    """Minimal valid DICOM (Explicit VR Little Endian, uncompressed)."""
    pydicom = pytest.importorskip("pydicom")
    np = pytest.importorskip("numpy")
    from pydicom.dataset import Dataset, FileDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    arr = (np.arange(rows * cols, dtype=np.uint16).reshape(rows, cols) % 4096).astype(np.uint16)
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = generate_uid()
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.PatientName = "Test^Patient"
    ds.Modality = "CT"
    ds.StudyInstanceUID = "1.9.9"
    if study_date is not None:
        ds.StudyDate = study_date
    ds.Rows, ds.Columns = rows, cols
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME1" if mono1 else "MONOCHROME2"
    if window is not None:
        ds.WindowCenter, ds.WindowWidth = window
    ds.PixelData = arr.tobytes()
    buf = io.BytesIO()
    pydicom.dcmwrite(buf, ds)
    return buf.getvalue()


async def _renderable_study(db_session, test_clinic, test_patient, fake_storage, **kwargs):
    from app.modules.imaging_viewer.service import ImagingStudyService

    storage = fake_storage
    path = f"{test_clinic.id}/{test_patient.id}/2026-09/{uuid4()}.dcm"
    raw = _dicom_bytes(**kwargs)
    storage.files[path] = raw
    user_id = (await db_session.execute(select(User))).scalars().first().id
    doc2 = Document(
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        document_type="other",
        title="DX",
        original_filename="dx.dcm",
        storage_path=path,
        mime_type="application/dicom",
        file_size=len(raw),
        uploaded_by=user_id,
    )
    db_session.add(doc2)
    await db_session.flush()
    study, _ = await ImagingStudyService.index_study(
        db_session, test_clinic.id, test_patient.id, doc2.id, raw=raw
    )
    png = await ImagingStudyService.render_study_png(db_session, test_clinic.id, study.id)
    return study, png


@pytest.mark.asyncio
async def test_render_png_returns_valid_image(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    pytest.importorskip("PIL")
    _study, png = await _renderable_study(db_session, test_clinic, test_patient, fake_storage)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    from PIL import Image

    img = Image.open(io.BytesIO(png))
    assert img.size == (64, 64)
    assert img.mode == "L"


@pytest.mark.asyncio
async def test_render_png_windowing_and_mono1(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    pytest.importorskip("PIL")
    _study, plain = await _renderable_study(db_session, test_clinic, test_patient, fake_storage)
    _study2, windowed = await _renderable_study(
        db_session, test_clinic, test_patient, fake_storage, window=(2000, 400)
    )
    assert plain != windowed
    _study3, inverted = await _renderable_study(
        db_session, test_clinic, test_patient, fake_storage, mono1=True
    )
    assert inverted != plain


@pytest.mark.asyncio
async def test_render_png_rejects_garbage_and_foreign_clinic(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    from app.modules.imaging_viewer.service import (
        ImagingStudyService,
        UnrenderableStudyError,
    )

    doc = await _document(db_session, test_clinic, test_patient, fake_storage)
    study, _ = await ImagingStudyService.index_study(
        db_session, test_clinic.id, test_patient.id, doc.id
    )
    with pytest.raises(UnrenderableStudyError):
        await ImagingStudyService.render_study_png(db_session, test_clinic.id, study.id)
    with pytest.raises(LookupError):
        await ImagingStudyService.render_study_png(db_session, uuid4(), study.id)


@pytest.mark.asyncio
async def test_handler_indexes_dicom_and_sniffs_octet_stream(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    """The upload handler indexes DICOM bytes and sniffs octet-stream
    uploads with a DICM magic — gallery files stay out."""
    from app.modules.imaging_viewer import ImagingViewerModule

    handler = ImagingViewerModule()._on_photo_uploaded

    async def _doc_with(mime: str, raw: bytes) -> Document:
        path = f"{test_clinic.id}/{test_patient.id}/2026-09/{uuid4()}.dcm"
        fake_storage.files[path] = raw
        user_id = (await db_session.execute(select(User))).scalars().first().id
        doc = Document(
            clinic_id=test_clinic.id,
            patient_id=test_patient.id,
            document_type="other",
            title="X",
            original_filename="x.dcm",
            storage_path=path,
            mime_type=mime,
            file_size=len(raw),
            uploaded_by=user_id,
        )
        db_session.add(doc)
        await db_session.flush()
        return doc

    dicom_raw = _dicom_bytes()
    doc1 = await _doc_with("application/dicom", dicom_raw)
    await handler(
        {
            "document_id": str(doc1.id),
            "clinic_id": str(test_clinic.id),
            "patient_id": str(test_patient.id),
        },
        db=db_session,
    )
    items, total = await ImagingStudyService.list_studies(
        db_session, test_clinic.id, test_patient.id
    )
    assert total == 1

    doc2 = await _doc_with("application/octet-stream", dicom_raw)
    await handler(
        {
            "document_id": str(doc2.id),
            "clinic_id": str(test_clinic.id),
            "patient_id": str(test_patient.id),
        },
        db=db_session,
    )
    _, total = await ImagingStudyService.list_studies(db_session, test_clinic.id, test_patient.id)
    assert total == 2

    doc3 = await _doc_with("application/octet-stream", b"definitely-not-dicom")
    await handler(
        {
            "document_id": str(doc3.id),
            "clinic_id": str(test_clinic.id),
            "patient_id": str(test_patient.id),
        },
        db=db_session,
    )
    _, total = await ImagingStudyService.list_studies(db_session, test_clinic.id, test_patient.id)
    assert total == 2


@pytest.mark.asyncio
async def test_handler_failure_never_breaks_the_upload(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed index rolls back only its own savepoint — the borrowing
    session stays usable (no PendingRollbackError for the upload)."""
    from app.modules.imaging_viewer import ImagingViewerModule
    from app.modules.imaging_viewer import service as service_module

    async def _boom(*args, **kwargs):
        raise RuntimeError("flush exploded")

    monkeypatch.setattr(service_module.ImagingStudyService, "index_core", _boom)
    handler = ImagingViewerModule()._on_photo_uploaded
    doc = await _document(db_session, test_clinic, test_patient, fake_storage)
    # Must return normally (best-effort), and the session must still work.
    await handler(
        {
            "document_id": str(doc.id),
            "clinic_id": str(test_clinic.id),
            "patient_id": str(test_patient.id),
        },
        db=db_session,
    )
    items, total = await ImagingStudyService.list_studies(
        db_session, test_clinic.id, test_patient.id
    )
    assert total == 0
