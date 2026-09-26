"""Business logic for the imaging_viewer module."""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType, event_bus
from app.modules.media.models import Document
from app.modules.media.service import DocumentService
from app.modules.media.storage import get_storage_backend
from app.modules.patients.models import Patient

from .models import ImagingAnnotation, ImagingStudy, RvgImport, RvgLink

logger = logging.getLogger(__name__)

DICOM_MIME_TYPES = frozenset({"application/dicom", "application/octet-stream"})

# Render ceiling, in pixels, checked from Rows x Columns before any array is
# materialized. pydicom decodes into float64 in the windowing path, so a
# single frame costs rows*columns*8 bytes before Pillow sees it: a
# crafted 50k x 50k header would otherwise take the worker out with an
# OOM kill (SIGKILL, no traceback, no 422). 80 MP covers a generous
# panoramic/stitched study (a 6k x 13k pano is 78 MP) and rejects the
# memory-exhaustion shape with a clean 422. Lower it only with evidence
# from real studies.
MAX_RENDER_PIXELS = 80_000_000

# Watch-folder subdirectories. A row awaiting a human decision is parked in
# pending/ so approve can still read its bytes; once decided, the file is
# retired to processed/ (the tick only ever reads the clinic root, so a
# leftover pending/ file is never re-hashed).
WATCH_PENDING_DIR = "pending"
WATCH_PROCESSED_DIR = "processed"


def _watch_clinic_dir(clinic_id: UUID) -> str | None:
    """Configured clinic watch dir, or None when the watch is unset."""
    root = os.environ.get("DENTALPIN_RVG_WATCH_DIR", "").strip()
    return os.path.join(root, str(clinic_id)) if root else None


def is_dicom_bytes(raw: bytes) -> bool:
    """Magic-byte sniff: Part-10 `DICM` prefix at offset 128.

    Browsers usually upload `.dcm` as `application/octet-stream`, so the
    mime type alone misses most radiology uploads — sniff the bytes.
    """
    return len(raw) > 132 and raw[128:132] == b"DICM"


class UnrenderableStudyError(ValueError):
    """DICOM bytes exist but cannot be rendered to PNG (missing pixel
    libraries or undecodable pixels). The router maps this to 422 —
    re-upload, don't retry."""


async def fetch_document_bytes(document: Document) -> bytes:
    """Read a document's bytes from storage.

    Single call site for all reads (index, render, handler sniff) so tests
    fake storage in exactly one place: the ``get_storage_backend`` global
    of THIS module (looked up at call time, monkeypatch-friendly).
    """
    return await fetch_storage_bytes(document.storage_path)


async def fetch_storage_bytes(storage_path: str) -> bytes:
    """Read storage bytes by path, through the same seam as the document
    variant. The render path resolves the path first and closes its
    transaction before reading, so it cannot use the Document row."""
    storage = get_storage_backend()
    return await storage.retrieve(storage_path)


def _parse_study_date(value: str | None) -> datetime | None:
    """DICOM StudyDate (`YYYYMMDD`) → UTC midnight. Never raises: garbage
    means unknown, and indexing must not fail over a date."""
    if not value:
        return None
    try:
        return datetime(int(value[0:4]), int(value[4:6]), int(value[6:8]), tzinfo=UTC)
    except (ValueError, IndexError):
        return None


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
        ds = pydicom.dcmread(io.BytesIO(raw), stop_before_pixels=True)
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
        raw: bytes | None = None,
    ) -> tuple[ImagingStudy, bool]:
        """Index a media document as a viewable DICOM study.

        The document must belong to the same clinic + patient; anything else
        raises ``LookupError`` (the router maps it to 404 — no cross-tenant
        oracle). Pixel data is never copied: the study points at the document.

        Idempotent: a document that already has an active study returns that
        row with ``created=False`` (second element) instead of duplicating —
        shared StudyInstanceUIDs across RVG frames must never 500 a lookup.
        This is the request-session path: storage I/O, commit, and publish
        all happen here. Transactional callers (event handlers inside
        someone else's session) must use ``index_core`` instead — ADR 0019.
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

        if raw is None:
            raw = await fetch_document_bytes(document)
        try:
            study, created = await ImagingStudyService.index_core(
                db,
                clinic_id,
                patient_id,
                document,
                raw,
                study_uid=study_uid,
                modality=modality,
            )
        except IntegrityError:
            # Lost a concurrent double-index race (pre-check passed on both
            # sides): roll back and return the winner instead of 500ing.
            # Own session only — transactional callers never reach this
            # branch with a borrowed session (their except handles it).
            await db.rollback()
            study = (
                await db.execute(
                    select(ImagingStudy).where(
                        ImagingStudy.clinic_id == clinic_id,
                        ImagingStudy.document_id == document.id,
                        ImagingStudy.status == "active",
                    )
                )
            ).scalar_one_or_none()
            if study is None:
                raise
            created = False
        await db.commit()
        await db.refresh(study)

        await event_bus.publish(
            EventType.IMAGING_STUDY_INDEXED,
            {
                "study_id": str(study.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(patient_id),
                "document_id": str(document.id),
                "study_uid": study.study_uid,
            },
        )
        return study, created

    @staticmethod
    async def index_core(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        document: Document,
        raw: bytes | None,
        study_uid: str | None = None,
        modality: str | None = None,
    ) -> tuple[ImagingStudy, bool]:
        """Flush-only index core for transactional callers (ADR 0019).

        No storage I/O (bytes arrive as ``raw`` — ``None`` means unparsed,
        tags stay empty and fill in nowhere: callers that need metadata
        pass bytes), no commit, no publish. Returns ``(study, created)``;
        an existing active study for the same document short-circuits with
        ``created=False`` so the flush path is deterministic — the caller
        is usually borrowing someone else's session, where a surprise
        ``IntegrityError`` would poison it.
        """
        existing = (
            await db.execute(
                select(ImagingStudy).where(
                    ImagingStudy.clinic_id == clinic_id,
                    ImagingStudy.document_id == document.id,
                    ImagingStudy.status == "active",
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False

        tags = extract_dicom_tags(raw) if raw is not None else {}
        resolved_uid = study_uid or tags.get("StudyInstanceUID") or str(document.id)
        study = ImagingStudy(
            clinic_id=clinic_id,
            patient_id=patient_id,
            document_id=document.id,
            study_uid=resolved_uid,
            modality=modality or tags.get("Modality"),
            study_date=_parse_study_date(tags.get("StudyDate")),
            dicom_metadata=tags,
        )
        db.add(study)
        await db.flush()
        await db.refresh(study)
        return study, True

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
    async def get_frame_bytes(
        db: AsyncSession, clinic_id: UUID, study_id: UUID
    ) -> tuple[bytes, str]:
        """Resolve the study's DICOM bytes for rendering.

        Both the study and the backing document are re-checked against the
        clinic: a study id from another clinic resolves to ``LookupError``.
        Returns ``(bytes, mime_type)``.
        """
        storage_path, mime_type = await ImagingStudyService.get_frame_source(
            db, clinic_id, study_id
        )
        return await fetch_storage_bytes(storage_path), mime_type

    @staticmethod
    async def get_frame_source(
        db: AsyncSession, clinic_id: UUID, study_id: UUID
    ) -> tuple[str, str]:
        """Resolve where a study's bytes live, without reading them.

        Split from :meth:`get_frame_bytes` so the caller can close its
        database transaction before touching storage: a filesystem round
        trip (or an object-store fetch) held open inside a request's
        transaction pins a connection and holds a snapshot for the whole
        read, which is the wrong place to wait on I/O we do not need the
        database for. Returns ``(storage_path, mime_type)``.
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
        return document.storage_path, document.mime_type

    @staticmethod
    async def render_study_png(db: AsyncSession, clinic_id: UUID, study_id: UUID) -> bytes:
        """Render one study to PNG bytes for the viewer + annotation canvas.

        Same clinic re-checks as the byte path (LookupError → 404).
        Undecodable pixels or missing pixel libraries raise
        ``UnrenderableStudyError`` (the router maps it to 422).
        """
        storage_path, _mime = await ImagingStudyService.get_frame_source(db, clinic_id, study_id)
        # Release the connection before the storage read and the CPU-bound
        # render: the row is already loaded, and both the fetch and the
        # decode are I/O and CPU we should not hold a transaction for.
        await db.rollback()
        raw = await fetch_storage_bytes(storage_path)
        return await asyncio.to_thread(render_dicom_png, raw)


def _reject_unsupported_geometry(ds) -> None:
    """Refuse pixel layouts the viewer cannot honestly draw (422).

    Each refusal names the reason and the remedy, because a generic
    "pixels do not render" leaves a clinician with nothing to act on:

    - multi-frame: the first frame would silently misrepresent a study, so
      the frame picker is the honest answer and it does not exist yet.
    - colour (SamplesPerPixel > 1 / RGB): the canvas, the windowing maths
      and the ruler are all single-channel; mapping RGB to luminance here
      would be a guess about clinical intent.
    - encapsulated pixel data: a compressed transfer syntax (JPEG-Lossless,
      JPEG 2000, RLE) needs a decoder plugin that is deliberately not in
      the backend image, so this is an operator-side fix.
    """
    frames = _positive_int(ds.get("NumberOfFrames", None))
    if frames is not None and frames > 1:
        raise UnrenderableStudyError(
            f"multi-frame study ({frames} frames) is not renderable yet; "
            "the viewer shows single-frame studies only"
        )
    samples = _positive_int(ds.get("SamplesPerPixel", None)) or 1
    photometric = str(ds.get("PhotometricInterpretation", "")).upper()
    if samples > 1 or photometric.startswith("RGB") or photometric == "PALETTE COLOR":
        raise UnrenderableStudyError(
            "colour study is not renderable: the DICOM viewer draws single-channel images only"
        )
    transfer_syntax = getattr(getattr(ds, "file_meta", None), "TransferSyntaxUID", None)
    if transfer_syntax is not None and transfer_syntax.is_encapsulated:
        raise UnrenderableStudyError(
            f"compressed transfer syntax {transfer_syntax} needs a decoder "
            "plugin that is not installed on the server; convert the study "
            "to an uncompressed transfer syntax"
        )


def _apply_modality_lut(ds, arr):
    """Modality LUT then VOI LUT when the study carries them.

    Order is the DICOM one (PS3.3 C.11.1) and it is load-bearing: the
    modality LUT maps stored values to modality-specific units and indexes
    with them, so it must run on the INTEGER array, before the float
    conversion, the rescale and the window. Skipping it (or running a VOI
    LUT over raw stored values) is what produced plausible-looking but
    clinically wrong greys, and ``RescaleSlope``/``RescaleIntercept`` were
    ignored entirely before.
    """
    import numpy as np
    from pydicom.pixels import apply_modality_lut, apply_voi_lut

    pixels = arr
    if "ModalityLUTSequence" in ds:
        pixels = apply_modality_lut(pixels, ds)
    pixels = np.asarray(pixels, dtype="float64")
    slope = _float_or_none(ds.get("RescaleSlope", None))
    intercept = _float_or_none(ds.get("RescaleIntercept", None))
    if slope is not None or intercept is not None:
        pixels = pixels * (slope if slope is not None else 1.0) + (
            intercept if intercept is not None else 0.0
        )
    if "VOILUTSequence" in ds:
        pixels = apply_voi_lut(pixels, ds)
    return pixels


def render_dicom_png(raw: bytes) -> bytes:
    """Render DICOM pixel data to grayscale PNG bytes.

    Pipeline: decode → modality LUT + VOI LUT when present (plus
    RescaleSlope/Intercept, which are applied to the stored values first) →
    window. The window is explicit WindowCenter/WindowWidth when present
    (first value of multi-valued), else a min/max stretch of the corrected
    values. MONOCHROME1 is inverted so bones read bright. Raises
    ``UnrenderableStudyError`` when the pixel libraries are missing, the
    geometry is unsupported, or the pixels do not decode — callers map that
    to 422, never 500.
    """
    try:
        import pydicom
        from PIL import Image
    except ImportError as exc:
        raise UnrenderableStudyError(f"pixel libraries unavailable: {exc}") from exc
    try:
        ds = pydicom.dcmread(io.BytesIO(raw))
        rows = _positive_int(ds.get("Rows", None))
        columns = _positive_int(ds.get("Columns", None))
        if rows is None or columns is None:
            raise UnrenderableStudyError("image dimensions missing or invalid")
        if rows * columns > MAX_RENDER_PIXELS:
            raise UnrenderableStudyError(
                f"image too large to render: {rows}x{columns} exceeds {MAX_RENDER_PIXELS} pixels"
            )
        _reject_unsupported_geometry(ds)
        arr = ds.pixel_array
    except UnrenderableStudyError:
        raise
    except Exception as exc:
        raise UnrenderableStudyError(f"pixels do not decode: {exc}") from exc
    try:
        pixels = _apply_modality_lut(ds, arr)
        center = ds.get("WindowCenter", None)
        width = ds.get("WindowWidth", None)
        if isinstance(center, (list, tuple)):
            center = center[0] if len(center) else None
        if isinstance(width, (list, tuple)):
            width = width[0] if len(width) else None
        if center not in (None, "") and width not in (None, ""):
            lo = float(center) - float(width) / 2.0
            hi = float(center) + float(width) / 2.0
        else:
            lo, hi = float(pixels.min()), float(pixels.max())
        if hi <= lo:
            hi = lo + 1.0
        scaled = ((pixels - lo) / (hi - lo) * 255.0).clip(0, 255).astype("uint8")
        if str(ds.get("PhotometricInterpretation", "")).upper() == "MONOCHROME1":
            scaled = 255 - scaled
        buf = io.BytesIO()
        Image.fromarray(scaled, mode="L").save(buf, format="PNG")
        return buf.getvalue()
    except UnrenderableStudyError:
        raise
    except Exception as exc:
        raise UnrenderableStudyError(f"pixels do not render: {exc}") from exc


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
        ds = pydicom.dcmread(io.BytesIO(raw), stop_before_pixels=True)
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
        study, _created = await ImagingStudyService.index_study(
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
        Handled files are filed by outcome: a row still awaiting a human
        decision moves to ``pending/`` (approve reads the bytes from
        there, then retires the file to ``processed/``), and everything
        decided by the tick itself (auto-imported, rejected, failed) moves
        to ``processed/`` (failed rows keep their error for audit; re-drop
        the file to retry). So a folder holding more than ``limit`` files
        drains over successive ticks instead of stalling on the first
        page, and ticks never re-hash the same files. Returns counts
        ``{scanned, created, approved, pending, failed}``.
        """
        counts = {"scanned": 0, "created": 0, "approved": 0, "pending": 0, "failed": 0}
        try:
            names = sorted(os.listdir(path))
        except OSError:
            return counts
        try:
            os.makedirs(os.path.join(path, WATCH_PROCESSED_DIR), exist_ok=True)
            os.makedirs(os.path.join(path, WATCH_PENDING_DIR), exist_ok=True)
        except OSError:
            logger.exception("RvgService.scan_watch_dir: cannot create watch subdirs in %s", path)
            return counts
        files = [
            n
            for n in names
            if os.path.isfile(os.path.join(path, n))
            and n not in (WATCH_PENDING_DIR, WATCH_PROCESSED_DIR)
        ]
        for name in files[:limit]:
            full = os.path.join(path, name)
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
            _move_watch_file(
                path,
                name,
                WATCH_PENDING_DIR if row.status == "pending" else WATCH_PROCESSED_DIR,
            )
        return counts

    @staticmethod
    def read_source_bytes(clinic_id: UUID, filename: str) -> bytes | None:
        """Read a queued import's source bytes, wherever the scan filed it.

        A pending row's bytes live in ``pending/``; rows decided by an
        earlier tick sit in ``processed/`` and the pre-``pending/`` layout
        left them in the clinic root, so all three are probed in that
        order. ``filename`` is re-stripped to a basename: it came from
        ``os.listdir``, and the row is ours, but a stored name must never
        be able to walk out of the watch dir.
        """
        clinic_dir = _watch_clinic_dir(clinic_id)
        if clinic_dir is None:
            return None
        safe = os.path.basename(filename)
        for sub in (WATCH_PENDING_DIR, WATCH_PROCESSED_DIR, ""):
            candidate = (
                os.path.join(clinic_dir, sub, safe) if sub else os.path.join(clinic_dir, safe)
            )
            if not os.path.isfile(candidate):
                continue
            try:
                with open(candidate, "rb") as fh:
                    return fh.read()
            except OSError:
                logger.exception("RvgService.read_source_bytes: cannot read %s", candidate)
                return None
        return None

    @staticmethod
    def retire_source_file(clinic_id: UUID, filename: str) -> None:
        """Move a decided import's file from ``pending/`` to ``processed/``.

        Best-effort and silent on failure: the import row is already
        decided and owns the durable outcome, and a leftover pending file
        is never re-hashed (the tick only reads the clinic root).
        """
        clinic_dir = _watch_clinic_dir(clinic_id)
        if clinic_dir is None:
            return
        safe = os.path.basename(filename)
        source = os.path.join(clinic_dir, WATCH_PENDING_DIR, safe)
        if not os.path.isfile(source):
            return
        try:
            os.makedirs(os.path.join(clinic_dir, WATCH_PROCESSED_DIR), exist_ok=True)
            dest = os.path.join(clinic_dir, WATCH_PROCESSED_DIR, safe)
            if os.path.exists(dest):
                stem, dot, ext = safe.partition(".")
                n = 1
                while os.path.exists(dest):
                    n += 1
                    dest = os.path.join(
                        clinic_dir,
                        WATCH_PROCESSED_DIR,
                        f"{stem}.{n}{dot}{ext}" if dot else f"{stem}.{n}",
                    )
            os.replace(source, dest)
        except OSError:
            logger.exception("RvgService.retire_source_file: cannot retire %s", safe)

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


def _pixel_spacing_mm(tags: dict) -> tuple[float, float] | None:
    """(row_spacing, column_spacing) in mm, or None when the study has none.

    DICOM PixelSpacing (0028,0030) is ``[row_spacing\\column_spacing]``:
    the first value is the distance between row centres (vertical), the
    second between column centres (horizontal). Returning them unnamed is
    the bug this replaces, so the order is explicit and documented here.
    """
    for key in ("ImagerPixelSpacing", "PixelSpacing"):
        raw = (tags or {}).get(key)
        if not raw:
            continue
        try:
            parts = [float(p) for p in str(raw).replace("\\", " ").split()]
        except ValueError:
            continue
        if len(parts) == 1:
            parts = [parts[0], parts[0]]
        if len(parts) < 2:
            continue
        row_spacing, column_spacing = parts[0], parts[1]
        if row_spacing > 0 and column_spacing > 0:
            return row_spacing, column_spacing
    return None


def _spacing_mm(tags: dict) -> float | None:
    """First pixel-spacing value in mm, or None when the study has none.

    Kept for display (the annotation's ``spacing_mm`` column shows what the
    measurement was based on); ``_ruler_mm`` uses the full pair.
    """
    spacing = _pixel_spacing_mm(tags)
    return spacing[0] if spacing else None


def _ruler_mm(points: list, tags: dict) -> float | None:
    """Ruler length in mm for two normalized (0-1) points, or None.

    Normalized coordinates are fractions of the image, so the pixel delta
    on each axis is the normalized delta times that axis's pixel count, and
    the millimetre distance applies the per-axis spacing:

        dx_px = (x2 - x1) * Columns
        dy_px = (y2 - y1) * Rows
        mm    = hypot(dx_px * column_spacing, dy_px * row_spacing)

    Multiplying the normalized distance by a single spacing value (the
    previous behaviour) ignores the image's aspect ratio and reported a
    plausible-looking but wrong number. Returns None when Rows/Columns or
    PixelSpacing are missing: a measurement is never guessed.
    """
    spacing = _pixel_spacing_mm(tags)
    rows = _positive_int((tags or {}).get("Rows"))
    columns = _positive_int((tags or {}).get("Columns"))
    if not spacing or not rows or not columns:
        return None
    (x1, y1), (x2, y2) = points
    row_spacing, column_spacing = spacing
    dx_px = (x2 - x1) * columns
    dy_px = (y2 - y1) * rows
    return round(
        ((dx_px * column_spacing) ** 2 + (dy_px * row_spacing) ** 2) ** 0.5,
        2,
    )


def _positive_int(raw: object) -> int | None:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _float_or_none(raw: object) -> float | None:
    """Parse a DICOM decimal-string tag, or None when absent/garbage.

    DS values arrive as strings (or ``DSfloat``), and a multi-valued one
    keeps only its first entry, matching how the window tags are read.
    """
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if len(raw) else None
    if raw is None:
        return None
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _move_watch_file(path: str, name: str, subdir: str) -> None:
    """Move a watch file into ``path/subdir`` (collision-safe).

    Best-effort: a move failure only logs — the row already records the
    outcome, and the next tick re-handles the file idempotently.
    """
    try:
        dest = os.path.join(path, subdir, name)
        if os.path.exists(dest):
            stem, dot, ext = name.partition(".")
            n = 1
            while os.path.exists(dest):
                n += 1
                dest = os.path.join(path, subdir, f"{stem}.{n}{dot}{ext}" if dot else f"{stem}.{n}")
        os.replace(os.path.join(path, name), dest)
    except OSError:
        logger.exception("RvgService.scan_watch_dir: cannot move %s to %s/", name, subdir)


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
        if kind == "ruler":
            measured = _ruler_mm(clean["points"], study.dicom_metadata)
            if measured is not None:
                clean["mm"] = measured
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
