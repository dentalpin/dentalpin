"""Business logic for the imaging_viewer module."""

from __future__ import annotations

import hashlib
import logging
import os
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType, event_bus
from app.modules.media.models import Document
from app.modules.media.service import DocumentService
from app.modules.media.storage import get_storage_backend
from app.modules.patients.models import Patient

from .models import ImagingAnnotation, ImagingStudy, RvgImport, RvgLink

logger = logging.getLogger(__name__)

DICOM_MIME_TYPES = frozenset({"application/dicom", "application/octet-stream"})


def extract_dicom_tags(raw: bytes) -> dict:
    """Extract identity tags from DICOM bytes. Empty dict when unparsable.

    pydicom is an optional dependency of the MVP proxy path: when it is not
    installed (or the bytes are not DICOM), indexing still succeeds with the
    caller-supplied ``study_uid``/``modality`` and empty tags.
    """
    try:
        import pydicom
    except ImportError:
        return {}
    try:
        ds = pydicom.dcmread(__import__("io").BytesIO(raw), stop_before_pixels=True)
    except Exception:  # noqa: BLE001 — any malformed input maps to "no tags"
        return {}
    tags: dict = {}
    for keyword in (
        "StudyInstanceUID",
        "Modality",
        "StudyDate",
        "BodyPartExamined",
        "ImagerPixelSpacing",
        "PixelSpacing",
    ):
        value = ds.get(keyword, None)
        if value not in (None, ""):
            tags[keyword] = str(value)
    rows = ds.get("Rows", None)
    columns = ds.get("Columns", None)
    if rows is not None:
        tags["Rows"] = int(rows)
    if columns is not None:
        tags["Columns"] = int(columns)
    return tags


class ImagingStudyService:
    @staticmethod
    async def index_study(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        document_id: UUID,
        study_uid: str | None = None,
        modality: str | None = None,
    ) -> ImagingStudy:
        """Index a media document as a viewable DICOM study.

        The document must belong to the same clinic + patient; anything else
        raises ``LookupError`` (the router maps it to 404 — no cross-tenant
        oracle). Pixel data is never copied: the study points at the document.
        """
        document = (
            await db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.clinic_id == clinic_id,
                    Document.patient_id == patient_id,
                    Document.status == "active",
                )
            )
        ).scalar_one_or_none()
        if document is None:
            raise LookupError("Document not found")

        storage = get_storage_backend()
        raw = await storage.retrieve(document.storage_path)
        tags = extract_dicom_tags(raw)
        resolved_uid = study_uid or tags.get("StudyInstanceUID") or str(document.id)
        resolved_modality = modality or tags.get("Modality")

        study = ImagingStudy(
            clinic_id=clinic_id,
            patient_id=patient_id,
            document_id=document.id,
            study_uid=resolved_uid,
            modality=resolved_modality,
            dicom_metadata=tags,
        )
        db.add(study)
        await db.commit()
        await db.refresh(study)

        await event_bus.publish(
            EventType.IMAGING_STUDY_INDEXED,
            {
                "study_id": str(study.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(patient_id),
                "document_id": str(document.id),
                "study_uid": resolved_uid,
            },
        )
        return study

    @staticmethod
    async def get_study(db: AsyncSession, clinic_id: UUID, study_id: UUID) -> ImagingStudy | None:
        """Fetch one study, clinic-scoped. Soft-archived rows stay fetchable."""
        return (
            await db.execute(
                select(ImagingStudy).where(
                    ImagingStudy.id == study_id,
                    ImagingStudy.clinic_id == clinic_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_studies(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        include_archived: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ImagingStudy], int]:
        """List a patient's studies with multi-tenancy and pagination."""
        stmt = select(ImagingStudy).where(
            ImagingStudy.clinic_id == clinic_id,
            ImagingStudy.patient_id == patient_id,
        )
        if not include_archived:
            stmt = stmt.where(ImagingStudy.status == "active")
        stmt = stmt.order_by(ImagingStudy.created_at.desc())

        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

        page_size = min(max(page_size, 1), 100)
        offset = (max(page, 1) - 1) * page_size
        items = list((await db.execute(stmt.offset(offset).limit(page_size))).scalars().all())
        return items, total

    @staticmethod
    async def archive_study(db: AsyncSession, study: ImagingStudy) -> ImagingStudy:
        """Soft-archive a study (patient data is never hard-deleted)."""
        study.status = "archived"
        await AnnotationService.archive_for_study(db, study)
        await db.commit()
        await db.refresh(study)
        return study

    @staticmethod
    async def qido_studies(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[dict]:
        """Minimal QIDO-RS study list for the embedded viewer.

        One entry per active study; single-frame studies report a single
        related instance. UIDs are opaque — the viewer must echo them back
        into the WADO paths below, never interpret them.
        """
        items, _ = await ImagingStudyService.list_studies(
            db, clinic_id, patient_id, page=1, page_size=100
        )
        return [
            {
                "StudyInstanceUID": s.study_uid,
                "Modality": s.modality or "OT",
                "StudyDate": s.study_date.strftime("%Y%m%d") if s.study_date else "",
                "NumberOfStudyRelatedInstances": 1,
            }
            for s in items
        ]

    @staticmethod
    async def get_frame_bytes_by_uid(
        db: AsyncSession, clinic_id: UUID, study_uid: str
    ) -> tuple[bytes, str]:
        """WADO-RS minimal frame resolution. Series/instance segments are
        accepted opaque (single-frame studies); the study UID is the key."""
        study = (
            await db.execute(
                select(ImagingStudy).where(
                    ImagingStudy.clinic_id == clinic_id,
                    ImagingStudy.study_uid == study_uid,
                    ImagingStudy.status == "active",
                )
            )
        ).scalar_one_or_none()
        if study is None:
            raise LookupError("Study not found")
        return await ImagingStudyService.get_frame_bytes(db, clinic_id, study.id)

    @staticmethod
    async def get_frame_bytes(
        db: AsyncSession, clinic_id: UUID, study_id: UUID
    ) -> tuple[bytes, str]:
        """Resolve the study's DICOM bytes for the viewer proxy.

        Both the study and the backing document are re-checked against the
        clinic: a study id from another clinic resolves to ``LookupError``.
        Returns ``(bytes, mime_type)``.
        """
        study = await ImagingStudyService.get_study(db, clinic_id, study_id)
        if study is None or study.status != "active":
            raise LookupError("Study not found")
        document = (
            await db.execute(
                select(Document).where(
                    Document.id == study.document_id,
                    Document.clinic_id == clinic_id,
                    Document.status == "active",
                )
            )
        ).scalar_one_or_none()
        if document is None:
            raise LookupError("Study not found")
        storage = get_storage_backend()
        return await storage.retrieve(document.storage_path), document.mime_type


class RvgConflictError(Exception):
    """An RVG import was already decided (approve/reject twice). Maps to 409."""


IDENTITY_TAG_KEYWORDS = (
    "PatientID",
    "PatientName",
    "PatientBirthDate",
    "StudyInstanceUID",
    "Modality",
    "StudyDate",
)


def extract_identity_tags(raw: bytes) -> dict:
    """Extract patient-identity DICOM tags. Empty dict when unparsable."""
    try:
        import pydicom
    except ImportError:
        return {}
    try:
        ds = pydicom.dcmread(__import__("io").BytesIO(raw), stop_before_pixels=True)
    except Exception:  # noqa: BLE001 — any malformed input maps to "no tags"
        return {}
    tags: dict = {}
    for keyword in IDENTITY_TAG_KEYWORDS:
        value = ds.get(keyword, None)
        if value not in (None, ""):
            tags[keyword] = str(value)
    return tags


def _dicom_name_tokens(patient_name: str) -> set[str]:
    """Split a DICOM ``LAST^FIRST`` name into lowercase tokens."""
    return {t.strip().lower() for t in patient_name.replace("^", " ").split() if t.strip()}


def _score_patient(tags: dict, patient: Patient) -> tuple[int, list[str]]:
    """Score one candidate patient against identity tags. Returns (score, reasons)."""
    score = 0
    reasons: list[str] = []
    dicom_id = tags.get("PatientID")
    if dicom_id and patient.national_id and patient.national_id == dicom_id:
        score += 60
        reasons.append("national_id")
    birth = tags.get("PatientBirthDate")
    if birth and patient.date_of_birth and patient.date_of_birth.strftime("%Y%m%d") == birth:
        score += 25
        reasons.append("dob")
    dicom_name = tags.get("PatientName")
    if dicom_name:
        dicom_tokens = _dicom_name_tokens(dicom_name)
        patient_tokens = {
            t for t in (patient.first_name, patient.last_name) if t for t in t.lower().split()
        }
        if dicom_tokens and patient_tokens:
            overlap = len(dicom_tokens & patient_tokens) / len(dicom_tokens)
            name_points = round(overlap * 30)
            if name_points:
                score += name_points
                reasons.append("name")
    return score, reasons


RVG_SUGGEST_THRESHOLD = 40
RVG_SCAN_BATCH_LIMIT = 50


class RvgService:
    """RVG watch-folder import: scan → match → human approval → auto-import links."""

    @staticmethod
    async def _active_patients(db: AsyncSession, clinic_id: UUID) -> list[Patient]:
        return list(
            (
                await db.execute(
                    select(Patient).where(
                        Patient.clinic_id == clinic_id,
                        Patient.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    async def suggest_patient(
        db: AsyncSession, clinic_id: UUID, tags: dict
    ) -> tuple[UUID | None, int | None, str | None]:
        """Best patient suggestion for identity tags.

        Returns ``(patient_id, score, reason)``; all-None when nothing clears
        the threshold or the top score ties (ambiguous — a human decides).
        """
        candidates = await RvgService._active_patients(db, clinic_id)
        scored = [(p.id, *_score_patient(tags, p)) for p in candidates]
        scored = [(pid, s, r) for pid, s, r in scored if s >= RVG_SUGGEST_THRESHOLD]
        if not scored:
            return None, None, None
        scored.sort(key=lambda item: item[1], reverse=True)
        if len(scored) > 1 and scored[0][1] == scored[1][1]:
            return None, None, "ambiguous"
        best_id, best_score, reasons = scored[0]
        return best_id, best_score, "+".join(reasons)

    @staticmethod
    async def _materialize(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        user_id: UUID,
        filename: str,
        raw: bytes,
        tags: dict,
    ) -> tuple[Document, ImagingStudy]:
        """Create the media document + study index for an approved import.

        Creating a DICOM document fires ``media.photo_uploaded``, whose
        auto-index handler may already have indexed it — reuse that study
        instead of double-indexing the same document.
        """
        document = await DocumentService.create_document(
            db,
            clinic_id,
            patient_id,
            user_id,
            file_data=raw,
            original_filename=filename,
            mime_type="application/dicom",
            document_type="other",
            title=f"RVG import: {filename}",
            description="Auto-imported from the RVG watch folder.",
            media_kind="xray",
            media_category="xray",
        )
        existing_study = (
            await db.execute(
                select(ImagingStudy).where(
                    ImagingStudy.clinic_id == clinic_id,
                    ImagingStudy.document_id == document.id,
                    ImagingStudy.status == "active",
                )
            )
        ).scalar_one_or_none()
        if existing_study is not None:
            return document, existing_study
        study = await ImagingStudyService.index_study(
            db,
            clinic_id,
            patient_id,
            document.id,
            study_uid=tags.get("StudyInstanceUID"),
            modality=tags.get("Modality"),
        )
        return document, study

    @staticmethod
    async def scan_bytes(
        db: AsyncSession,
        clinic_id: UUID,
        filename: str,
        raw: bytes,
        retry_failed: bool = False,
    ) -> tuple[RvgImport, bool]:
        """Scan one file's bytes. Deterministic: same bytes → same outcome.

        Returns ``(row, created)``. Re-scans of known hashes are no-ops
        (``created=False``) unless the row failed and ``retry_failed`` is set.
        Approved DICOM identities (``RvgLink``) import immediately, attributed
        to the link creator (scheduler ticks have no actor of their own).
        """
        content_hash = hashlib.sha256(raw).hexdigest()
        existing = (
            await db.execute(
                select(RvgImport).where(
                    RvgImport.clinic_id == clinic_id,
                    RvgImport.content_hash == content_hash,
                )
            )
        ).scalar_one_or_none()
        if existing is not None and not (existing.status == "failed" and retry_failed):
            return existing, False

        tags = extract_identity_tags(raw)
        has_identity = bool(tags.get("PatientID") or tags.get("PatientName"))
        if not has_identity:
            row = await RvgService._record_failed(
                db,
                existing,
                clinic_id,
                filename,
                content_hash,
                tags,
                "unreadable DICOM or no identity tags",
            )
            return row, existing is None

        dicom_patient_id = tags.get("PatientID")
        if dicom_patient_id:
            link = (
                await db.execute(
                    select(RvgLink).where(
                        RvgLink.clinic_id == clinic_id,
                        RvgLink.dicom_patient_id == dicom_patient_id,
                    )
                )
            ).scalar_one_or_none()
            if link is not None:
                patient = (
                    await db.execute(
                        select(Patient).where(
                            Patient.id == link.patient_id,
                            Patient.clinic_id == clinic_id,
                            Patient.status == "active",
                        )
                    )
                ).scalar_one_or_none()
                if patient is None:
                    # Linked patient is gone — drop the dead link, queue for review.
                    await db.delete(link)
                else:
                    document, study = await RvgService._materialize(
                        db, clinic_id, patient.id, link.created_by, filename, raw, tags
                    )
                    row = existing or RvgImport(
                        clinic_id=clinic_id, filename=filename, content_hash=content_hash
                    )
                    row.filename = filename
                    row.identity_tags = tags
                    row.patient_id = patient.id
                    row.document_id = document.id
                    row.study_id = study.id
                    row.suggested_patient_id = patient.id
                    row.match_score = 100
                    row.match_reason = "linked"
                    row.status = "approved"
                    row.error = None
                    db.add(row)
                    await db.commit()
                    await db.refresh(row)
                    return row, existing is None

        suggested_id, score, reason = await RvgService.suggest_patient(db, clinic_id, tags)
        row = existing or RvgImport(
            clinic_id=clinic_id, filename=filename, content_hash=content_hash
        )
        row.filename = filename
        row.identity_tags = tags
        row.suggested_patient_id = suggested_id
        row.match_score = score
        row.match_reason = reason
        row.status = "pending"
        row.error = None
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row, existing is None

    @staticmethod
    async def _record_failed(
        db: AsyncSession,
        existing: RvgImport | None,
        clinic_id: UUID,
        filename: str,
        content_hash: str,
        tags: dict,
        error: str,
    ) -> RvgImport:
        row = existing or RvgImport(
            clinic_id=clinic_id, filename=filename, content_hash=content_hash
        )
        row.filename = filename
        row.identity_tags = tags
        row.status = "failed"
        row.error = error
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def scan_watch_dir(
        db: AsyncSession,
        clinic_id: UUID,
        path: str,
        limit: int = RVG_SCAN_BATCH_LIMIT,
        retry_failed: bool = False,
    ) -> dict:
        """Scan up to ``limit`` files from a watch dir, best-effort per file.

        A broken file records a failed row — it never aborts the tick.
        Returns counts ``{scanned, created, approved, pending, failed}``.
        """
        counts = {"scanned": 0, "created": 0, "approved": 0, "pending": 0, "failed": 0}
        try:
            names = sorted(os.listdir(path))
        except OSError:
            return counts
        for name in names[:limit]:
            full = os.path.join(path, name)
            if not os.path.isfile(full):
                continue
            counts["scanned"] += 1
            try:
                with open(full, "rb") as fh:
                    raw = fh.read()
                row, created = await RvgService.scan_bytes(
                    db, clinic_id, name, raw, retry_failed=retry_failed
                )
            except Exception:  # noqa: BLE001 — per-file best-effort, tick continues
                logger.exception("RvgService.scan_watch_dir: failed on %s", name)
                continue
            if created:
                counts["created"] += 1
            counts[row.status if row.status in counts else "pending"] += 1
        return counts

    @staticmethod
    async def list_imports(
        db: AsyncSession,
        clinic_id: UUID,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[RvgImport], int]:
        """List RVG import rows, optionally filtered by status."""
        stmt = select(RvgImport).where(RvgImport.clinic_id == clinic_id)
        if status:
            stmt = stmt.where(RvgImport.status == status)
        stmt = stmt.order_by(RvgImport.created_at.desc())
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        page_size = min(max(page_size, 1), 100)
        offset = (max(page, 1) - 1) * page_size
        items = list((await db.execute(stmt.offset(offset).limit(page_size))).scalars().all())
        return items, total

    @staticmethod
    async def get_import(db: AsyncSession, clinic_id: UUID, import_id: UUID) -> RvgImport | None:
        return (
            await db.execute(
                select(RvgImport).where(
                    RvgImport.id == import_id,
                    RvgImport.clinic_id == clinic_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def approve(
        db: AsyncSession,
        clinic_id: UUID,
        import_id: UUID,
        patient_id: UUID,
        user_id: UUID,
        raw: bytes | None = None,
    ) -> RvgImport:
        """Approve a pending import: materialize document + study, store the link.

        ``raw`` carries the source bytes (the endpoint re-reads the watch-dir
        file; callers holding the bytes — retries, tools — pass them in).
        Raises ``LookupError`` for unknown import/patient/file (→ 404) and
        ``RvgConflictError`` when the row is already decided (→ 409).
        """
        row = await RvgService.get_import(db, clinic_id, import_id)
        if row is None:
            raise LookupError("Import not found")
        if row.status != "pending":
            raise RvgConflictError(f"Import is already {row.status}")
        patient = (
            await db.execute(
                select(Patient).where(
                    Patient.id == patient_id,
                    Patient.clinic_id == clinic_id,
                    Patient.status == "active",
                )
            )
        ).scalar_one_or_none()
        if patient is None:
            raise LookupError("Patient not found")
        if raw is None:
            raise LookupError("Source file no longer in the watch folder")

        document, study = await RvgService._materialize(
            db, clinic_id, patient.id, user_id, row.filename, raw, row.identity_tags
        )
        dicom_patient_id = (row.identity_tags or {}).get("PatientID")
        if dicom_patient_id:
            link = (
                await db.execute(
                    select(RvgLink).where(
                        RvgLink.clinic_id == clinic_id,
                        RvgLink.dicom_patient_id == dicom_patient_id,
                    )
                )
            ).scalar_one_or_none()
            if link is None:
                db.add(
                    RvgLink(
                        clinic_id=clinic_id,
                        patient_id=patient.id,
                        dicom_patient_id=dicom_patient_id,
                        created_by=user_id,
                    )
                )
            else:
                link.patient_id = patient.id
                link.created_by = user_id
        row.patient_id = patient.id
        row.document_id = document.id
        row.study_id = study.id
        row.status = "approved"
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def reject(
        db: AsyncSession,
        clinic_id: UUID,
        import_id: UUID,
        reason: str | None = None,
    ) -> RvgImport:
        """Reject a pending import. The row stays for audit."""
        row = await RvgService.get_import(db, clinic_id, import_id)
        if row is None:
            raise LookupError("Import not found")
        if row.status != "pending":
            raise RvgConflictError(f"Import is already {row.status}")
        row.status = "rejected"
        row.error = reason
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def list_links(db: AsyncSession, clinic_id: UUID) -> list[RvgLink]:
        return list(
            (
                await db.execute(
                    select(RvgLink)
                    .where(RvgLink.clinic_id == clinic_id)
                    .order_by(RvgLink.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    async def delete_link(db: AsyncSession, clinic_id: UUID, link_id: UUID) -> bool:
        """Drop an approved DICOM-identity link. Queued rows are unaffected."""
        link = (
            await db.execute(
                select(RvgLink).where(
                    RvgLink.id == link_id,
                    RvgLink.clinic_id == clinic_id,
                )
            )
        ).scalar_one_or_none()
        if link is None:
            return False
        await db.delete(link)
        await db.commit()
        return True


ANNOTATION_KINDS = ("ruler", "freehand", "note")
ANNOTATION_MAX_POINTS = 500
ANNOTATION_MAX_TEXT = 500


def _spacing_mm(tags: dict) -> float | None:
    """First pixel-spacing value in mm, or None when the study has none."""
    for key in ("ImagerPixelSpacing", "PixelSpacing"):
        raw = (tags or {}).get(key)
        if not raw:
            continue
        try:
            value = float(str(raw).replace("\\", " ").split()[0])
        except (ValueError, IndexError):
            continue
        if value > 0:
            return value
    return None


class AnnotationService:
    """Human overlays on studies. Originals immutable; delete archives (L7)."""

    @staticmethod
    def _validate(kind: str, payload: dict) -> dict:
        """Validate + normalize an annotation payload. Raises ValueError (→ 422)."""
        if kind not in ANNOTATION_KINDS:
            raise ValueError(f"Unknown annotation kind: {kind}")
        points = payload.get("points", [])
        if not isinstance(points, list) or not all(
            isinstance(p, (list, tuple))
            and len(p) == 2
            and all(isinstance(c, (int, float)) and 0 <= c <= 1 for c in p)
            for p in points
        ):
            raise ValueError("points must be a list of [x, y] pairs in 0-1 range")
        if len(points) > ANNOTATION_MAX_POINTS:
            raise ValueError(f"points capped at {ANNOTATION_MAX_POINTS}")
        text = payload.get("text")
        if kind == "ruler" and len(points) != 2:
            raise ValueError("ruler needs exactly 2 points")
        if kind == "freehand" and len(points) < 2:
            raise ValueError("freehand needs at least 2 points")
        if kind == "note":
            if not isinstance(text, str) or not text.strip():
                raise ValueError("note needs text")
            if len(text) > ANNOTATION_MAX_TEXT:
                raise ValueError(f"text capped at {ANNOTATION_MAX_TEXT} chars")
        clean: dict = {"points": [[float(x), float(y)] for x, y in points]}
        if isinstance(text, str) and text.strip():
            clean["text"] = text.strip()[:ANNOTATION_MAX_TEXT]
        return clean

    @staticmethod
    async def list(db: AsyncSession, clinic_id: UUID, study_id: UUID) -> list[ImagingAnnotation]:
        study = await ImagingStudyService.get_study(db, clinic_id, study_id)
        if study is None:
            raise LookupError("Study not found")
        return list(
            (
                await db.execute(
                    select(ImagingAnnotation)
                    .where(
                        ImagingAnnotation.clinic_id == clinic_id,
                        ImagingAnnotation.study_id == study_id,
                        ImagingAnnotation.status == "active",
                    )
                    .order_by(ImagingAnnotation.created_at.asc())
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    async def create(
        db: AsyncSession,
        clinic_id: UUID,
        study_id: UUID,
        user_id: UUID,
        kind: str,
        payload: dict,
    ) -> ImagingAnnotation:
        study = await ImagingStudyService.get_study(db, clinic_id, study_id)
        if study is None or study.status != "active":
            raise LookupError("Study not found")
        clean = AnnotationService._validate(kind, payload)
        spacing = _spacing_mm(study.dicom_metadata)
        if kind == "ruler" and spacing:
            (x1, y1), (x2, y2) = clean["points"]
            clean["mm"] = round((((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5) * spacing, 2)
        row = ImagingAnnotation(
            clinic_id=clinic_id,
            patient_id=study.patient_id,
            study_id=study.id,
            kind=kind,
            payload=clean,
            spacing_mm=spacing,
            created_by=user_id,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def archive(db: AsyncSession, clinic_id: UUID, annotation_id: UUID) -> bool:
        """Archive an annotation. Returns False when unknown (→ 404)."""
        row = (
            await db.execute(
                select(ImagingAnnotation).where(
                    ImagingAnnotation.id == annotation_id,
                    ImagingAnnotation.clinic_id == clinic_id,
                    ImagingAnnotation.status == "active",
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        row.status = "archived"
        await db.commit()
        return True

    @staticmethod
    async def archive_for_study(db: AsyncSession, study: ImagingStudy) -> None:
        """Archive a study's annotations alongside the study (flush only)."""
        rows = (
            (
                await db.execute(
                    select(ImagingAnnotation).where(
                        ImagingAnnotation.study_id == study.id,
                        ImagingAnnotation.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            row.status = "archived"
        await db.flush()
