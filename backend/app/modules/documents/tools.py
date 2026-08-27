"""Agent tools exposed by the documents module.

Each handler wraps an existing service method — no business logic
duplicated.  All handlers filter by ``ctx.clinic_id`` (multi-tenancy).
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.core.agents import Tool, ToolCategory


class GenerateDocumentArgs(BaseModel):
    """Arguments the LLM fills when calling the generate tool."""

    patient_id: uuid.UUID = Field(description="UUID of the patient")
    document_type: str = Field(
        description=(
            "One of: prescription, medical_certificate, "
            "referral, radiology_request"
        )
    )
    title: str = Field(description="Document title")
    content: dict = Field(
        default_factory=dict,
        description="Document-type-specific content payload",
    )


async def _generate_document(ctx, params: GenerateDocumentArgs) -> dict:
    """Create and generate a document for the given patient.

    Returns the created document (without file content — the PDF is
    stored server-side).
    """
    from .service import DocumentService

    doc = await DocumentService.create_document(
        ctx.db,
        ctx.clinic_id,
        patient_id=params.patient_id,
        document_type=params.document_type,
        title=params.title,
        content=params.content,
    )
    # Generate the PDF
    generated = await DocumentService.generate_pdf(
        ctx.db, ctx.clinic_id, doc.id
    )
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
