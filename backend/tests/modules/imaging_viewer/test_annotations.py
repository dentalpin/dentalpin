"""imaging_viewer annotations: validation, mm math, isolation, cascade."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.media.service as media_service_module
from app.core.auth.models import Clinic, User
from app.modules.imaging_viewer import service as service_module
from app.modules.imaging_viewer.models import ImagingAnnotation
from app.modules.imaging_viewer.service import AnnotationService, ImagingStudyService
from app.modules.media.models import Document
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


async def _study(db, clinic, patient, storage, tags: dict | None = None):
    if tags is not None:
        import app.modules.imaging_viewer.service as svc

        orig = svc.extract_dicom_tags
        svc.extract_dicom_tags = lambda raw: dict(tags)  # noqa: E731
        try:
            return await _study_inner(db, clinic, patient, storage)
        finally:
            svc.extract_dicom_tags = orig
    return await _study_inner(db, clinic, patient, storage)


async def _study_inner(db, clinic, patient, storage):
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
        mime_type="application/dicom",
        file_size=22,
        uploaded_by=user_id,
    )
    db.add(doc)
    await db.flush()
    study, _created = await ImagingStudyService.index_study(
        db, clinic.id, patient.id, doc.id, study_uid=f"9.9.{uuid4().int % 100000}"
    )
    return study


async def _user_id(db: AsyncSession):
    return (await db.execute(select(User))).scalars().first().id


@pytest.mark.asyncio
async def test_ruler_mm_scales_by_pixels_per_axis(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    """Normalized points are image fractions, so each axis is scaled by its
    own pixel count before the per-axis spacing is applied. A 100x200 image
    with 0.5\\0.5 spacing measured corner-to-corner is hypot(50, 100) mm.
    The old math (normalized distance x one spacing value) reported 0.35 mm
    for the same image."""
    study = await _study(
        db_session,
        test_clinic,
        test_patient,
        fake_storage,
        tags={
            "StudyInstanceUID": "1.1.1",
            "Rows": 200,
            "Columns": 100,
            "PixelSpacing": "0.5\\0.5",
        },
    )
    row = await AnnotationService.create(
        db_session,
        test_clinic.id,
        study.id,
        await _user_id(db_session),
        "ruler",
        {"points": [[0, 0], [1, 1]]},
    )
    assert row.payload["mm"] == 111.8
    assert row.spacing_mm == 0.5


@pytest.mark.asyncio
async def test_ruler_mm_uses_row_and_column_spacing_separately(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    """PixelSpacing is [row_spacing\\column_spacing]: a horizontal run is
    governed by the column value only."""
    study = await _study(
        db_session,
        test_clinic,
        test_patient,
        fake_storage,
        tags={
            "StudyInstanceUID": "1.1.2",
            "Rows": 100,
            "Columns": 100,
            "PixelSpacing": "0.5\\0.25",
        },
    )
    horizontal = await AnnotationService.create(
        db_session,
        test_clinic.id,
        study.id,
        await _user_id(db_session),
        "ruler",
        {"points": [[0, 0], [1, 0]]},
    )
    vertical = await AnnotationService.create(
        db_session,
        test_clinic.id,
        study.id,
        await _user_id(db_session),
        "ruler",
        {"points": [[0, 0], [0, 1]]},
    )
    assert horizontal.payload["mm"] == 25.0
    assert vertical.payload["mm"] == 50.0


@pytest.mark.asyncio
async def test_ruler_without_spacing_has_no_mm(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    study = await _study(db_session, test_clinic, test_patient, fake_storage)
    row = await AnnotationService.create(
        db_session,
        test_clinic.id,
        study.id,
        await _user_id(db_session),
        "ruler",
        {"points": [[0, 0], [1, 1]]},
    )
    assert "mm" not in row.payload
    assert row.spacing_mm is None


@pytest.mark.asyncio
async def test_ruler_spacing_without_dimensions_has_no_mm(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    """Pixel spacing without Rows/Columns cannot be converted to a length,
    so no mm is guessed (the row keeps its spacing for display)."""
    study = await _study(
        db_session,
        test_clinic,
        test_patient,
        fake_storage,
        tags={"StudyInstanceUID": "1.1.3", "PixelSpacing": "0.5\\0.5"},
    )
    row = await AnnotationService.create(
        db_session,
        test_clinic.id,
        study.id,
        await _user_id(db_session),
        "ruler",
        {"points": [[0, 0], [1, 1]]},
    )
    assert "mm" not in row.payload
    assert row.spacing_mm == 0.5


@pytest.mark.asyncio
async def test_validation_rejects_bad_payloads(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    study = await _study(db_session, test_clinic, test_patient, fake_storage)
    user_id = await _user_id(db_session)
    with pytest.raises(ValueError):
        await AnnotationService.create(
            db_session, test_clinic.id, study.id, user_id, "laser", {"points": []}
        )
    with pytest.raises(ValueError):
        await AnnotationService.create(
            db_session,
            test_clinic.id,
            study.id,
            user_id,
            "ruler",
            {"points": [[0, 0], [1, 1], [2, 2]]},
        )
    with pytest.raises(ValueError):
        await AnnotationService.create(
            db_session, test_clinic.id, study.id, user_id, "note", {"points": [[0, 0]]}
        )
    with pytest.raises(ValueError):
        await AnnotationService.create(
            db_session,
            test_clinic.id,
            study.id,
            user_id,
            "freehand",
            {"points": [[0, 0], [2, 2]]},
        )


@pytest.mark.asyncio
async def test_list_is_study_scoped_and_cross_clinic_404s(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    study = await _study(db_session, test_clinic, test_patient, fake_storage)
    user_id = await _user_id(db_session)
    await AnnotationService.create(
        db_session,
        test_clinic.id,
        study.id,
        user_id,
        "note",
        {"points": [[0.5, 0.5]], "text": "watch this root"},
    )
    rows = await AnnotationService.list(db_session, test_clinic.id, study.id)
    assert len(rows) == 1
    with pytest.raises(LookupError):
        await AnnotationService.list(db_session, uuid4(), study.id)


@pytest.mark.asyncio
async def test_archive_hides_and_study_archive_cascades(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    study = await _study(db_session, test_clinic, test_patient, fake_storage)
    user_id = await _user_id(db_session)
    row = await AnnotationService.create(
        db_session,
        test_clinic.id,
        study.id,
        user_id,
        "note",
        {"points": [[0.1, 0.1]], "text": "temp"},
    )
    assert await AnnotationService.archive(db_session, test_clinic.id, row.id) is True
    assert await AnnotationService.archive(db_session, test_clinic.id, row.id) is False
    assert await AnnotationService.list(db_session, test_clinic.id, study.id) == []

    row2 = await AnnotationService.create(
        db_session,
        test_clinic.id,
        study.id,
        user_id,
        "note",
        {"points": [[0.2, 0.2]], "text": "keep"},
    )
    await ImagingStudyService.archive_study(db_session, study)
    stored = await db_session.get(ImagingAnnotation, row2.id)
    assert stored is not None and stored.status == "archived"
