"""Read and mutate a clinic's editable template copy by its full identity."""

from datetime import UTC, datetime
from uuid import UUID

from jinja2 import TemplateError
from pydantic import BaseModel
from sqlalchemy import delete, or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.email import email_service

from .channels import Channel, channel_registry
from .channels.email_adapter import default_notification_subject
from .models import NotificationTemplate, NotificationType
from .service import NotificationService
from .template_rendering import (
    TemplateValidationError,
    render_whatsapp_text,
    rendering_error,
    validate_source,
    whatsapp_text_fits,
)
from .template_variables import available_fields, example_context, optional_fields


class TemplateCopy(BaseModel):
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None


class TemplateVariable(BaseModel):
    key: str
    example: str | list[dict] | int | float | None
    optional: bool


class TemplateSelection(BaseModel):
    editable: bool
    current: TemplateCopy | None
    has_override: bool
    default_locale: str | None
    variables: list[TemplateVariable]


class TemplatePreviewRequest(BaseModel):
    content: TemplateCopy | None = None
    use_default: bool = False
    minimal: bool = False


class TemplatePreview(BaseModel):
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None


class EditorValidationError(ValueError):
    def __init__(self, field: str, error: TemplateValidationError):
        self.field = field
        self.error = error
        super().__init__(str(error))

    def detail(self) -> dict:
        return {
            "code": self.error.code,
            "field": self.field,
            "line": self.error.line,
            "variable": self.error.variable,
        }


async def copy_is_editable(db: AsyncSession, clinic_id: UUID, channel: Channel) -> bool:
    if channel == Channel.EMAIL:
        return True
    if channel == Channel.WHATSAPP:
        adapter = channel_registry.get_by_name("whatsapp_manual")
        return bool(adapter and await adapter.supports(db, clinic_id))
    return False


def _copy(row: NotificationTemplate | None, channel: Channel) -> TemplateCopy | None:
    if row is None:
        return None
    return TemplateCopy(
        subject=None if channel == Channel.WHATSAPP else row.subject,
        body_html=row.body_html if channel == Channel.EMAIL else None,
        body_text=row.body_text,
    )


class TemplateEditor:
    def __init__(
        self, db: AsyncSession, clinic: Clinic, key: NotificationType, locale: str, channel: Channel
    ):
        self.db = db
        self.clinic = clinic
        self.key = key
        self.locale = locale
        self.channel = channel

    async def _template(self, *, system_only: bool = False) -> NotificationTemplate | None:
        return await NotificationService.get_template(
            self.db,
            None if system_only else self.clinic.id,
            self.key,
            self.locale,
            self.channel,
            require_text=self.channel == Channel.WHATSAPP,
        )

    async def selection(self) -> TemplateSelection:
        editable = await copy_is_editable(self.db, self.clinic.id, self.channel)
        current = await self._template()
        system = await self._template(system_only=True)
        default_locale = self.locale if system else None
        if self.channel == Channel.EMAIL and (system is None or not system.body_html):
            bundled = email_service.bundled_template(self.key, self.locale, "html")
            default_locale = bundled[1] if bundled else None
        samples = example_context(self.key, self.locale, self.clinic)
        return TemplateSelection(
            editable=editable,
            current=_copy(current, self.channel),
            has_override=current is not None and current.clinic_id == self.clinic.id,
            default_locale=default_locale,
            variables=[
                TemplateVariable(
                    key=field, example=samples[field], optional=field in optional_fields(self.key)
                )
                for field in available_fields(self.key, self.channel)
                if editable
            ],
        )

    def _render_field(self, field: str, source: str, context: dict, *, validate: bool) -> str:
        try:
            if validate:
                if field == "subject" and len(source) > 255:
                    raise TemplateValidationError("invalid_subject")
                fields = set(available_fields(self.key, self.channel))
                validate_source(source, fields, fields & {"items", "treatments"})
            if self.channel == Channel.WHATSAPP:
                rendered = render_whatsapp_text(source, context).strip()
                if not whatsapp_text_fits(rendered):
                    raise TemplateValidationError("whatsapp_length")
                return rendered
            rendered = email_service.render_custom_template(source, context, strict=validate)
            if field == "subject" and (len(rendered) > 255 or "\r" in rendered or "\n" in rendered):
                raise TemplateValidationError("invalid_subject")
            return rendered
        except TemplateValidationError as exc:
            raise EditorValidationError(field, exc) from exc
        except TemplateError as exc:
            raise EditorValidationError(field, rendering_error(exc)) from exc
        except (TypeError, ValueError, ArithmeticError) as exc:
            raise EditorValidationError(field, TemplateValidationError("render_error")) from exc

    def _render_copy(
        self, content: TemplateCopy, *, minimal: bool = False, validate: bool = True
    ) -> TemplatePreview:
        context = example_context(self.key, self.locale, self.clinic, minimal=minimal)
        if self.channel == Channel.WHATSAPP:
            if not content.body_text:
                return TemplatePreview()
            return TemplatePreview(
                body_text=self._render_field(
                    "body_text", content.body_text, context, validate=validate
                )
            )
        if self.channel in (Channel.PUSH, Channel.SMS):
            return TemplatePreview(subject=content.subject, body_text=content.body_text)

        subject = content.subject or default_notification_subject(self.key)
        return TemplatePreview(
            subject=self._render_field("subject", subject, context, validate=validate),
            body_html=self._email_body("body_html", content.body_html, context, "html", validate),
            body_text=self._email_body("body_text", content.body_text, context, "txt", validate),
        )

    async def preview(self, request: TemplatePreviewRequest) -> TemplatePreview:
        if request.content is not None:
            return self._render_copy(request.content, minimal=request.minimal)
        row = await self._template(system_only=request.use_default)
        return self._render_copy(
            _copy(row, self.channel) or TemplateCopy(),
            minimal=request.minimal,
            validate=row is not None and row.clinic_id is not None,
        )

    def _email_body(
        self, field: str, source: str | None, context: dict, extension: str, validate: bool
    ) -> str | None:
        if source:
            return self._render_field(field, source, context, validate=validate)
        bundled = email_service.bundled_template(self.key, self.locale, extension)
        return bundled[0].render(context) if bundled else None

    async def save(self, content: TemplateCopy) -> bool:
        required = "body_html" if self.channel == Channel.EMAIL else "body_text"
        if not (getattr(content, required) or "").strip():
            raise EditorValidationError(required, TemplateValidationError("required"))
        self._render_copy(content)
        self._render_copy(content, minimal=True)

        values = (
            content.model_dump()
            if self.channel == Channel.EMAIL
            else {"body_text": content.body_text}
        )
        stmt = (
            insert(NotificationTemplate)
            .values(
                clinic_id=self.clinic.id,
                template_key=self.key,
                locale=self.locale,
                channel=self.channel,
                is_system=False,
                is_active=True,
                **values,
            )
            .on_conflict_do_update(
                constraint="uq_notification_template_clinic_key_locale_channel",
                set_={**values, "is_active": True, "updated_at": datetime.now(UTC)},
                # Inactive provider mappings cannot be revived by a copy edit.
                where=NotificationTemplate.is_system.is_(False)
                & or_(
                    NotificationTemplate.is_active.is_(True),
                    NotificationTemplate.provider_template_name.is_(None)
                    & NotificationTemplate.provider_template_status.is_(None),
                ),
            )
            .returning(NotificationTemplate.id)
        )
        updated = await self.db.scalar(stmt)
        return updated is not None

    async def restore(self) -> None:
        ours = (
            NotificationTemplate.clinic_id == self.clinic.id,
            NotificationTemplate.template_key == self.key,
            NotificationTemplate.locale == self.locale,
            NotificationTemplate.channel == self.channel,
            NotificationTemplate.is_system.is_(False),
        )
        if self.channel == Channel.WHATSAPP:
            await self.db.execute(update(NotificationTemplate).where(*ours).values(body_text=None))
        else:
            await self.db.execute(delete(NotificationTemplate).where(*ours))
