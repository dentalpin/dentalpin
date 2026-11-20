"""Permissioned editor for the patient-facing notification templates."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from .channels import Channel
from .models import NotificationType
from .template_editor import (
    EditorValidationError,
    TemplateCopy,
    TemplateEditor,
    TemplatePreview,
    TemplatePreviewRequest,
    TemplateSelection,
    copy_is_editable,
)

editor_router = APIRouter(prefix="/templates/editor")
Read = Annotated[None, Depends(require_permission("notifications.templates.read"))]
Write = Annotated[None, Depends(require_permission("notifications.templates.write"))]


async def _selection(
    template_key: NotificationType,
    channel: Channel,
    locale: Annotated[str, Query(pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")],
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TemplateEditor:
    return TemplateEditor(db, ctx.clinic, template_key, locale, channel)


Selection = Annotated[TemplateEditor, Depends(_selection)]


async def _require_editable(editor: TemplateEditor) -> None:
    if not await copy_is_editable(editor.db, editor.clinic.id, editor.channel):
        raise HTTPException(409, "channel_read_only")


@editor_router.get("/{template_key}")
async def get_selection(editor: Selection, _: Read) -> ApiResponse[TemplateSelection]:
    return ApiResponse(data=await editor.selection())


def _invalid_template(exc: EditorValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"message": "Invalid notification template", "detail": exc.detail()},
    )


@editor_router.post("/{template_key}/preview", response_model=ApiResponse[TemplatePreview])
async def preview_selection(
    request: TemplatePreviewRequest, editor: Selection, _: Read
) -> ApiResponse[TemplatePreview] | JSONResponse:
    if request.content is not None:
        await _require_editable(editor)
    try:
        return ApiResponse(data=await editor.preview(request))
    except EditorValidationError as exc:
        return _invalid_template(exc)


@editor_router.put("/{template_key}", status_code=204)
async def save_selection(data: TemplateCopy, editor: Selection, _: Write) -> Response:
    await _require_editable(editor)
    try:
        if not await editor.save(data):
            raise HTTPException(409, "template_conflict")
    except EditorValidationError as exc:
        return _invalid_template(exc)
    return Response(status_code=204)


@editor_router.delete("/{template_key}", status_code=204)
async def restore_selection(editor: Selection, _: Write) -> Response:
    await _require_editable(editor)
    await editor.restore()
    return Response(status_code=204)
