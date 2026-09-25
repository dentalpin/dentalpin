"""Agent tools for the imaging_ai module. Thin wrappers over AiJobService."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .service import AiJobService


class QueueAiJobArgs(BaseModel):
    patient_id: str = Field(description="UUID of the patient")
    document_id: str = Field(description="UUID of the media document holding DICOM bytes")
    series_document_ids: list[str] = Field(
        default_factory=list,
        description="Rest of the series for volumetric backends (nnunet needs 2+ slices)",
    )
    backend: str = Field(default="pano", description="Runner backend: pano or nnunet")


class ConfirmAiJobArgs(BaseModel):
    job_id: str = Field(description="UUID of the AI job to confirm")


class GetAiJobArgs(BaseModel):
    job_id: str = Field(description="UUID of the AI job")


class ListAiJobsArgs(BaseModel):
    patient_id: str = Field(description="UUID of the patient")
    limit: int = Field(default=20, ge=1, le=100)


def _job_summary(job) -> dict:
    """Return native values — jsonify at the registry coerces UUID/datetime."""
    return {
        "job_id": job.id,
        "patient_id": job.patient_id,
        "document_id": job.document_id,
        "backend": job.backend,
        "model_id": job.model_id,
        "model_version": job.model_version,
        "status": job.status,
        "review_status": job.review_status,
        "error": job.error,
        "artifact_document_ids": job.artifact_document_ids,
    }


async def _queue_ai_job(ctx: AgentContext, params: QueueAiJobArgs) -> dict:
    try:
        job = await AiJobService.queue_job(
            ctx.db,
            ctx.clinic_id,
            UUID(params.patient_id),
            # No authenticated identity on the agent path: this only
            # proposes. A clinician confirms (authorizing the run and
            # fixing artifact attribution) via the confirm tool/endpoint.
            None,
            UUID(params.document_id),
            series_document_ids=[UUID(i) for i in params.series_document_ids],
            backend=params.backend,
        )
    except LookupError:
        return {"error": "Patient or document not found"}
    except ValueError as exc:
        return {"error": str(exc)}
    return _job_summary(job)


async def _confirm_ai_job(ctx: AgentContext, params: ConfirmAiJobArgs) -> dict:
    job = await AiJobService.get_job(ctx.db, ctx.clinic_id, UUID(params.job_id))
    if job is None:
        return {"error": "Job not found"}
    if ctx.supervisor_id is None:
        return {"error": "Confirm needs a supervised session (no supervising clinician)"}
    try:
        # The supervising clinician confirms: authorizes a proposed run
        # (stamping them as queued_by) or records the draft review.
        confirmed = await AiJobService.confirm_job(ctx.db, job, ctx.supervisor_id)
    except ValueError as exc:
        return {"error": str(exc)}
    return _job_summary(confirmed)


async def _get_ai_job(ctx: AgentContext, params: GetAiJobArgs) -> dict:
    job = await AiJobService.get_job(ctx.db, ctx.clinic_id, UUID(params.job_id))
    if not job:
        return {"error": "Job not found"}
    return _job_summary(job)


async def _list_ai_jobs(ctx: AgentContext, params: ListAiJobsArgs) -> dict:
    items, total = await AiJobService.list_jobs(
        ctx.db, ctx.clinic_id, UUID(params.patient_id), page=1, page_size=params.limit
    )
    return {"total": total, "jobs": [_job_summary(j) for j in items]}


def get_all_tools() -> list[Tool]:
    return [
        Tool(
            name="queue_imaging_ai_job",
            description=(
                "Propose an AI run over a patient's DICOM bytes (returns immediately; "
                "a clinician confirms before anything executes — poll the job)"
            ),
            category=ToolCategory.WRITE,
            permissions=["imaging_ai.jobs.write"],
            handler=_queue_ai_job,
            parameters=QueueAiJobArgs,
        ),
        Tool(
            name="confirm_imaging_ai_job",
            description=(
                "Confirm an AI job: authorizes a proposed run or records "
                "the clinician review of finished draft artifacts"
            ),
            category=ToolCategory.WRITE,
            permissions=["imaging_ai.jobs.write"],
            handler=_confirm_ai_job,
            parameters=ConfirmAiJobArgs,
        ),
        Tool(
            name="get_imaging_ai_job",
            description="Get an AI job's status, error, and artifact document ids by ID",
            category=ToolCategory.READ,
            permissions=["imaging_ai.jobs.read"],
            handler=_get_ai_job,
            parameters=GetAiJobArgs,
        ),
        Tool(
            name="list_imaging_ai_jobs",
            description="List a patient's AI segmentation jobs, newest first",
            category=ToolCategory.READ,
            permissions=["imaging_ai.jobs.read"],
            handler=_list_ai_jobs,
            parameters=ListAiJobsArgs,
        ),
    ]
