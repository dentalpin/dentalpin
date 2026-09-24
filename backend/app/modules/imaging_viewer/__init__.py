"""imaging_viewer module — in-app DICOM study viewer (backend PNG render)."""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType, event_bus
from app.core.plugins import BaseModule
from app.core.scheduling import ScheduledJob
from app.modules.media.models import Document

from .models import ImagingAnnotation, ImagingStudy, RvgImport, RvgLink
from .router import router
from .service import (
    DICOM_MIME_TYPES,
    ImagingStudyService,
    RvgService,
    fetch_document_bytes,
    is_dicom_bytes,
)

logger = logging.getLogger(__name__)


async def rvg_watch_tick() -> None:
    """Scheduler tick: scan every clinic's RVG watch subdir (best-effort).

    Layout ``<DENTALPIN_RVG_WATCH_DIR>/<clinic_id>/`` keeps files isolated by
    construction. Unset root or missing per-clinic dir → silent no-op.
    """
    from app.core.auth.models import Clinic
    from app.database import async_session_maker

    root = os.environ.get("DENTALPIN_RVG_WATCH_DIR", "")
    if not root or not os.path.isdir(root):
        return
    async with async_session_maker() as db:
        clinic_ids = list((await db.execute(select(Clinic.id))).scalars().all())
        for clinic_id in clinic_ids:
            path = os.path.join(root, str(clinic_id))
            if not os.path.isdir(path):
                continue
            try:
                await RvgService.scan_watch_dir(db, clinic_id, path)
            except Exception:  # noqa: BLE001 — one clinic never breaks the tick
                logger.exception("imaging_viewer.rvg_watch_tick: scan failed for %s", clinic_id)


class ImagingViewerModule(BaseModule):
    """DICOM study index + PNG renderer on top of media documents.

    Pixel data stays in the referenced media ``Document``; this module owns
    the study index row and the clinic-scoped PNG render (server-side
    windowing) feeding the viewer and the annotation canvas.
    """

    manifest = {
        "name": "imaging_viewer",
        "version": "0.1.0",
        "summary": "In-app DICOM study viewer (PNG render) indexed on media documents.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["media", "patients"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["studies.read", "studies.write", "rvg.read", "rvg.write"],
            "hygienist": ["studies.read", "rvg.read"],
            "assistant": ["studies.read", "rvg.read"],
            "receptionist": ["studies.read", "rvg.read"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.imagingViewer",
                    "icon": "i-lucide-image",
                    "to": "/imaging",
                    "permission": "imaging_viewer.studies.read",
                    "order": 93,
                }
            ],
        },
    }

    def get_models(self) -> list:
        return [ImagingStudy, RvgLink, RvgImport, ImagingAnnotation]

    def get_router(self) -> APIRouter:
        return router

    def get_tools(self) -> list:
        from .tools import get_all_tools

        return get_all_tools()

    def get_permissions(self) -> list[str]:
        return ["studies.read", "studies.write", "rvg.read", "rvg.write"]

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        return [
            ScheduledJob(
                id="rvg_watch",
                func=rvg_watch_tick,
                trigger="interval",
                trigger_args={"seconds": 90},
                name="Scan RVG watch folders (90s)",
            )
        ]

    def get_event_handlers(self) -> dict[str, Any]:
        """Register event handlers."""
        return {
            EventType.PHOTO_UPLOADED: self._on_photo_uploaded,
            EventType.PATIENT_ARCHIVED: self._on_patient_archived,
        }

    async def _on_photo_uploaded(self, data: dict, *, db: AsyncSession) -> None:
        """Auto-index DICOM uploads as viewable studies (best-effort).

        Runs inside the media upload's transaction (ADR 0019): flush-only,
        no commit, and the bytes are fetched exactly once and reused for
        the magic-byte sniff and the tag parse — never re-read. Documents
        whose mime is neither DICOM nor sniffed-DICOM stay gallery-only.
        Never raises, and never poisons the borrowed session: the index
        runs in a savepoint, so even a failed flush rolls back only the
        index while the upload commits normally. The insert path itself
        is deterministic (idempotency pre-check first).
        """
        try:
            document_id = data.get("document_id")
            clinic_id = data.get("clinic_id")
            patient_id = data.get("patient_id")
            if not document_id or not clinic_id or not patient_id:
                return
            document = (
                await db.execute(
                    select(Document).where(
                        Document.id == UUID(str(document_id)),
                        Document.clinic_id == UUID(str(clinic_id)),
                    )
                )
            ).scalar_one_or_none()
            if document is None or document.mime_type not in DICOM_MIME_TYPES:
                return
            raw = await fetch_document_bytes(document)
            if document.mime_type != "application/dicom" and not is_dicom_bytes(raw):
                return
            # Savepoint: a failed index rolls back only itself — the media
            # upload holding this session commits normally afterwards.
            async with db.begin_nested():
                study, _created = await ImagingStudyService.index_core(
                    db,
                    UUID(str(clinic_id)),
                    UUID(str(patient_id)),
                    document,
                    raw,
                )
                await db.flush()
                await event_bus.publish(
                    EventType.IMAGING_STUDY_INDEXED,
                    {
                        "study_id": str(study.id),
                        "clinic_id": str(clinic_id),
                        "patient_id": str(patient_id),
                        "document_id": str(document_id),
                        "study_uid": study.study_uid,
                    },
                    db=db,
                )
        except Exception:  # noqa: BLE001 — best-effort indexing, log and continue
            logger.exception("imaging_viewer._on_photo_uploaded: auto-index failed")

    async def _on_patient_archived(self, data: dict, *, db: AsyncSession) -> None:
        """Cascade soft-archive of the patient's studies.

        Pending RVG imports are rejected (nothing auto-imports for a gone
        patient) and approved DICOM-identity links are dropped so the
        identity stops matching.
        """
        clinic_id = data.get("clinic_id")
        patient_id = data.get("patient_id")
        if not clinic_id or not patient_id:
            logger.error(
                "imaging_viewer._on_patient_archived: missing patient_id/clinic_id: %r",
                data,
            )
            return
        studies = (
            (
                await db.execute(
                    select(ImagingStudy).where(
                        ImagingStudy.clinic_id == UUID(str(clinic_id)),
                        ImagingStudy.patient_id == UUID(str(patient_id)),
                        ImagingStudy.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )
        for study in studies:
            study.status = "archived"
            for annotation in (
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
            ):
                annotation.status = "archived"
        pending = (
            (
                await db.execute(
                    select(RvgImport).where(
                        RvgImport.clinic_id == UUID(str(clinic_id)),
                        RvgImport.status == "pending",
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in pending:
            if row.suggested_patient_id == UUID(str(patient_id)):
                row.status = "rejected"
                row.error = "patient archived"
        links = (
            (
                await db.execute(
                    select(RvgLink).where(
                        RvgLink.clinic_id == UUID(str(clinic_id)),
                        RvgLink.patient_id == UUID(str(patient_id)),
                    )
                )
            )
            .scalars()
            .all()
        )
        for link in links:
            await db.delete(link)
        # Transactional handler (ADR 0019): flush only — the publisher owns
        # the commit, so a rolled-back archive rolls our cascade back too.
        await db.flush()
