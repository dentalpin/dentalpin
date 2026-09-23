"""Agent tools for the imaging_ai module. Thin wrappers over AiJobService."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .service import AiJobService


class QueueAiJobArgs(BaseModel):
    patient_id: str = Field(description="UUID of the patient")
    study_id: str = Field(description="UUID of the imaging study (opaque audit link)")
    document_id: str = Field(description="UUID of the media document holding DICOM bytes")
    backend: str = Field(default="nnunet", description="Runner backend: nnunet or pano")


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
        "study_id": job.study_id,
        "backend": job.backend,
        "model_id": job.model_id,
        "model_version": job.model_version,
        "status": job.status,
        "error": job.error,
        "artifact_document_ids": job.artifact_document_ids,
    }


async def _queue_ai_job(ctx: AgentContext, params: QueueAiJobArgs) -> dict:
    try:
        job = await AiJobService.queue_job(
            ctx.db,
            ctx.clinic_id,
            UUID(params.patient_id),
            # No authenticated identity on the agent path (L25) — the HTTP
            # route passes ctx.user_id instead.
            None,
            UUID(params.study_id),
            UUID(params.document_id),
            backend=params.backend,
        )
    except LookupError:
        return {"error": "Patient or document not found"}
    except ValueError as exc:
        return {"error": str(exc)}
    return _job_summary(job)


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
            description="Queue an AI segmentation run over a study's DICOM bytes (returns immediately; poll the job)",
            category=ToolCategory.WRITE,
            permissions=["imaging_ai.jobs.write"],
            handler=_queue_ai_job,
            parameters=QueueAiJobArgs,
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
