"""Agent tools exposed by the documents module.

Each handler wraps an existing service method — no business logic
duplicated.  All handlers filter by ``ctx.clinic_id`` (multi-tenancy).
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.core.agents import Tool, ToolCategory

from .schemas import DocumentCreate


class GenerateDocumentArgs(BaseModel):
    """Arguments the LLM fills when calling the generate tool."""

    patient_id: uuid.UUID = Field(description="UUID of the patient")
    document_type: Literal[
        "prescription",
        "medical_certificate",
        "referral",
        "radiology_request",
    ] = Field(description="Type of document to generate")
    title: str = Field(max_length=200, description="Document title")
    content: dict = Field(
        default_factory=dict,
        description=(
            "Document-type-specific content payload. prescription: "
            "{diagnosis, medications: [{name, dose, frequency, duration, "
            "notes}], notes}; medical_certificate: {diagnosis, description, "
            "recommendations, valid_from, valid_until (YYYY-MM-DD)}; "
            "referral: {referred_to, specialty, reason, clinical_summary, "
            "notes}; radiology_request: {exam_type, region, "
            "clinical_question, notes}"
        ),
    )


def _validation_detail(exc: ValidationError) -> str:
    """Compact, LLM-readable summary of a pydantic ValidationError."""
    return "; ".join(
        f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
        for err in exc.errors(include_url=False)
    )


async def _generate_document(ctx, params: GenerateDocumentArgs) -> dict:
    """Create and generate a document for the given patient.

    Returns the created document (without file content — the PDF is
    stored server-side).
    """
    from .service import DocumentService

    # Same validation as ``POST /documents``: the content is checked
    # against the per-type schema (and dates normalised) before
    # anything is stored.
    try:
        payload = DocumentCreate(
            patient_id=params.patient_id,
            document_type=params.document_type,
            title=params.title,
            content=params.content,
        )
    except ValidationError as exc:
        return {"error": "invalid", "detail": _validation_detail(exc)}

    doc = await DocumentService.create_document(
        ctx.db,
        ctx.clinic_id,
        patient_id=payload.patient_id,
        document_type=payload.document_type,
        title=payload.title,
        content=payload.content,
        created_by=ctx.supervisor_id,
    )
    if doc is None:
        return {"error": "patient_not_found"}
    # Generate the PDF
    generated = await DocumentService.generate_pdf(ctx.db, ctx.clinic_id, doc.id)
    return {
        "id": generated.id,  # native UUID — the registry's jsonify coerces
        "document_type": generated.document_type,
        "title": generated.title,
        "status": generated.status,
    }


def get_tools() -> list[Tool]:
    """Return the list of tools exposed by this module."""
    return [
        Tool(
            name="generate_document",
            description=(
                "Create a dental document (prescription, medical "
                "certificate, referral letter or radiology request) for "
                "a patient and generate it as a branded PDF. Returns the "
                "document metadata."
            ),
            parameters=GenerateDocumentArgs,
            handler=_generate_document,
            permissions=["documents.write"],
            category=ToolCategory.WRITE,
        ),
    ]
