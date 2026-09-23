"""imaging_viewer: index/list/get/archive + tenant isolation."""

from __future__ import annotations

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

    study = await ImagingStudyService.index_study(
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
    study = await ImagingStudyService.index_study(
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
async def test_frame_bytes_come_from_the_indexed_document(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    doc = await _document(db_session, test_clinic, test_patient, fake_storage)
    study = await ImagingStudyService.index_study(
        db_session, test_clinic.id, test_patient.id, doc.id, study_uid="5.5.5"
    )
    content, mime_type = await ImagingStudyService.get_frame_bytes(
        db_session, test_clinic.id, study.id
    )
    assert content == b"not-real-dicom-bytes"
    assert mime_type == "application/dicom"


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
async def test_qido_lists_study_uids_clinic_scoped(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    doc = await _document(db_session, test_clinic, test_patient, fake_storage)
    await ImagingStudyService.index_study(
        db_session, test_clinic.id, test_patient.id, doc.id, study_uid="1.2.9", modality="CT"
    )
    rows = await ImagingStudyService.qido_studies(db_session, test_clinic.id, test_patient.id)
    assert len(rows) == 1
    assert rows[0]["StudyInstanceUID"] == "1.2.9"
    assert rows[0]["Modality"] == "CT"
    assert rows[0]["NumberOfStudyRelatedInstances"] == 1

    other = uuid4()
    assert await ImagingStudyService.qido_studies(db_session, other, test_patient.id) == []


@pytest.mark.asyncio
async def test_wado_frame_resolves_by_uid(
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
    fake_storage: _FakeStorage,
) -> None:
    doc = await _document(db_session, test_clinic, test_patient, fake_storage)
    await ImagingStudyService.index_study(
        db_session, test_clinic.id, test_patient.id, doc.id, study_uid="7.7.7"
    )
    content, mime_type = await ImagingStudyService.get_frame_bytes_by_uid(
        db_session, test_clinic.id, "7.7.7"
    )
    assert content == b"not-real-dicom-bytes"
    assert mime_type == "application/dicom"

    with pytest.raises(LookupError):
        await ImagingStudyService.get_frame_bytes_by_uid(db_session, test_clinic.id, "nope")
    with pytest.raises(LookupError):
        await ImagingStudyService.get_frame_bytes_by_uid(db_session, uuid4(), "7.7.7")
