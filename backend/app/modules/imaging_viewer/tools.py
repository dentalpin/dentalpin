"""Agent tools for the imaging_viewer module. Thin wrappers over ImagingStudyService."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .service import AnnotationService, ImagingStudyService, RvgService


class ListStudiesArgs(BaseModel):
    patient_id: str = Field(description="UUID of the patient")
    limit: int = Field(default=20, ge=1, le=100)


class GetStudyArgs(BaseModel):
    study_id: str = Field(description="UUID of the imaging study")


class IndexStudyArgs(BaseModel):
    patient_id: str = Field(description="UUID of the patient")
    document_id: str = Field(description="UUID of the media document holding the DICOM bytes")
    study_uid: str | None = None
    modality: str | None = None


class ListRvgImportsArgs(BaseModel):
    status: str | None = Field(
        default=None, description="Filter by queue status: pending, approved, rejected, failed"
    )
    limit: int = Field(default=20, ge=1, le=100)


class ListAnnotationsArgs(BaseModel):
    study_id: str = Field(description="UUID of the imaging study")


def _study_summary(study) -> dict:
    """Return native values — jsonify at the registry coerces UUID/datetime."""
    return {
        "study_id": study.id,
        "patient_id": study.patient_id,
        "document_id": study.document_id,
        "study_uid": study.study_uid,
        "modality": study.modality,
        "dicom_metadata": study.dicom_metadata,
        "status": study.status,
    }


def _rvg_import_summary(row) -> dict:
    """Return native values — jsonify at the registry coerces UUID/datetime."""
    return {
        "import_id": row.id,
        "filename": row.filename,
        "patient_id": row.patient_id,
        "study_id": row.study_id,
        "suggested_patient_id": row.suggested_patient_id,
        "match_score": row.match_score,
        "match_reason": row.match_reason,
        "status": row.status,
        "error": row.error,
    }


async def _list_studies(ctx: AgentContext, params: ListStudiesArgs) -> dict:
    items, total = await ImagingStudyService.list_studies(
        ctx.db,
        ctx.clinic_id,
        UUID(params.patient_id),
        page=1,
        page_size=params.limit,
    )
    return {"total": total, "studies": [_study_summary(s) for s in items]}


async def _get_study(ctx: AgentContext, params: GetStudyArgs) -> dict:
    study = await ImagingStudyService.get_study(ctx.db, ctx.clinic_id, UUID(params.study_id))
    if not study:
        return {"error": "Study not found"}
    return _study_summary(study)


async def _index_study(ctx: AgentContext, params: IndexStudyArgs) -> dict:
    try:
        study = await ImagingStudyService.index_study(
            ctx.db,
            ctx.clinic_id,
            UUID(params.patient_id),
            UUID(params.document_id),
            study_uid=params.study_uid,
            modality=params.modality,
        )
    except LookupError:
        return {"error": "Document not found"}
    return _study_summary(study)


async def _list_rvg_imports(ctx: AgentContext, params: ListRvgImportsArgs) -> dict:
    items, total = await RvgService.list_imports(
        ctx.db,
        ctx.clinic_id,
        status=params.status,
        page=1,
        page_size=params.limit,
    )
    return {"total": total, "imports": [_rvg_import_summary(i) for i in items]}


async def _list_annotations(ctx: AgentContext, params: ListAnnotationsArgs) -> dict:
    try:
        rows = await AnnotationService.list(ctx.db, ctx.clinic_id, UUID(params.study_id))
    except LookupError:
        return {"error": "Study not found"}
    return {
        "study_id": params.study_id,
        "annotations": [
            {
                "annotation_id": r.id,
                "kind": r.kind,
                "payload": r.payload,
                "spacing_mm": r.spacing_mm,
                "status": r.status,
            }
            for r in rows
        ],
    }


def get_all_tools() -> list[Tool]:
    return [
        Tool(
            name="list_imaging_studies",
            description="List a patient's viewable DICOM imaging studies",
            category=ToolCategory.READ,
            permissions=["imaging_viewer.studies.read"],
            handler=_list_studies,
            parameters=ListStudiesArgs,
        ),
        Tool(
            name="get_imaging_study",
            description="Get detailed metadata about a specific imaging study by ID",
            category=ToolCategory.READ,
            permissions=["imaging_viewer.studies.read"],
            handler=_get_study,
            parameters=GetStudyArgs,
        ),
        Tool(
            name="index_imaging_study",
            description="Index an uploaded media document as a viewable DICOM study",
            category=ToolCategory.WRITE,
            permissions=["imaging_viewer.studies.write"],
            handler=_index_study,
            parameters=IndexStudyArgs,
        ),
        Tool(
            name="list_rvg_imports",
            description="List the RVG watch-folder import queue (pending approvals, failures)",
            category=ToolCategory.READ,
            permissions=["imaging_viewer.rvg.read"],
            handler=_list_rvg_imports,
            parameters=ListRvgImportsArgs,
        ),
        Tool(
            name="list_study_annotations",
            description="List a study's human annotation overlays (rulers, drawings, notes)",
            category=ToolCategory.READ,
            permissions=["imaging_viewer.studies.read"],
            handler=_list_annotations,
            parameters=ListAnnotationsArgs,
        ),
    ]
