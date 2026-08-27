"""Notifications module API router."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .gateway import NotificationGateway
from .schemas import (
    ChannelAvailabilityResponse,
    ClinicNotificationSettingsResponse,
    ClinicNotificationSettingsUpdate,
    ConversationMessageResponse,
    ConversationReplyRequest,
    EmailLogResponse,
    EmailTemplateCreate,
    EmailTemplateResponse,
    EmailTemplateUpdate,
    ManualSendRequest,
    ManualSendResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    SmtpSettingsResponse,
    SmtpSettingsUpdate,
    SmtpTestRequest,
    TestEmailRequest,
    TestEmailResponse,
)
from .service import NotificationService

router = APIRouter()


# ============================================================================
# Email Template Endpoints
# ============================================================================


@router.get("/templates", response_model=PaginatedApiResponse[EmailTemplateResponse])
async def list_templates(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.templates.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    locale: str | None = Query(default=None, max_length=5),
    include_system: bool = Query(default=True),
) -> PaginatedApiResponse[EmailTemplateResponse]:
    """List email templates for the clinic.

    Includes clinic-specific templates and optionally system templates.
    """
    templates, total = await NotificationService.list_templates(
        db,
        ctx.clinic_id,
        page=page,
        page_size=page_size,
        locale=locale,
        include_system=include_system,
    )
    return PaginatedApiResponse(
        data=[EmailTemplateResponse.model_validate(t) for t in templates],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/templates/{template_id}", response_model=ApiResponse[EmailTemplateResponse])
async def get_template(
    template_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.templates.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[EmailTemplateResponse]:
    """Get an email template by ID."""
    template = await NotificationService.get_template_by_id(db, ctx.clinic_id, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return ApiResponse(data=EmailTemplateResponse.model_validate(template))


@router.post(
    "/templates",
    response_model=ApiResponse[EmailTemplateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    data: EmailTemplateCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.templates.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[EmailTemplateResponse]:
    """Create a custom email template for the clinic.

    Custom templates override system templates with the same key and locale.
    """
    # Check if template already exists for this clinic
    existing = await NotificationService.get_template(
        db, ctx.clinic_id, data.template_key, data.locale
    )
    if existing and existing.clinic_id == ctx.clinic_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template '{data.template_key}' for locale '{data.locale}' already exists",
        )

    template = await NotificationService.create_template(db, ctx.clinic_id, data.model_dump())
    return ApiResponse(data=EmailTemplateResponse.model_validate(template))


@router.put("/templates/{template_id}", response_model=ApiResponse[EmailTemplateResponse])
async def update_template(
    template_id: UUID,
    data: EmailTemplateUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.templates.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[EmailTemplateResponse]:
    """Update an email template."""
    template = await NotificationService.get_template_by_id(db, ctx.clinic_id, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify system templates",
        )

    if template.clinic_id != ctx.clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify templates from other clinics",
        )

    try:
        updated = await NotificationService.update_template(
            db, template, data.model_dump(exclude_unset=True)
        )
        return ApiResponse(data=EmailTemplateResponse.model_validate(updated))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.templates.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a custom email template.

    Deleting a custom template will cause the system template to be used instead.
    """
    template = await NotificationService.get_template_by_id(db, ctx.clinic_id, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system templates",
        )

    if template.clinic_id != ctx.clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete templates from other clinics",
        )

    try:
        await NotificationService.delete_template(db, template)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# Patient Notification Preferences Endpoints
# ============================================================================


@router.get(
    "/preferences/patient/{patient_id}",
    response_model=ApiResponse[NotificationPreferenceResponse],
)
async def get_patient_preferences(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.preferences.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[NotificationPreferenceResponse]:
    """Get notification preferences for a patient.

    Creates default preferences if they don't exist.
    """
    prefs = await NotificationService.get_or_create_patient_preferences(
        db, ctx.clinic_id, patient_id
    )
    return ApiResponse(data=NotificationPreferenceResponse.model_validate(prefs))


@router.put(
    "/preferences/patient/{patient_id}",
    response_model=ApiResponse[NotificationPreferenceResponse],
)
async def update_patient_preferences(
    patient_id: UUID,
    data: NotificationPreferenceUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.preferences.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[NotificationPreferenceResponse]:
    """Update notification preferences for a patient."""
    prefs = await NotificationService.update_patient_preferences(
        db, ctx.clinic_id, patient_id, data.model_dump(exclude_unset=True)
    )
    return ApiResponse(data=NotificationPreferenceResponse.model_validate(prefs))


# ============================================================================
# Clinic Settings Endpoints
# ============================================================================


def _settings_response(
    settings, available_channels: list[str]
) -> ClinicNotificationSettingsResponse:
    """Serialize clinic settings + the computed available_channels list."""
    return ClinicNotificationSettingsResponse(
        id=settings.id,
        clinic_id=settings.clinic_id,
        preferred_channel=settings.preferred_channel,
        fallback_enabled=settings.fallback_enabled,
        manual_channels=list(settings.manual_channels or []),
        settings=settings.settings,
        available_channels=available_channels,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


@router.get("/settings", response_model=ApiResponse[ClinicNotificationSettingsResponse])
async def get_clinic_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ClinicNotificationSettingsResponse]:
    """Get notification settings for the clinic.

    Creates default settings if they don't exist. ``available_channels`` is
    computed from the channel registry + each adapter's per-clinic
    ``supports`` check (WhatsApp appears only when its vendor adapter is
    installed and connected for this clinic).
    """
    settings = await NotificationService.get_or_create_clinic_settings(db, ctx.clinic_id)
    available = await NotificationService.available_channels(db, ctx.clinic_id)
    return ApiResponse(data=_settings_response(settings, available))


@router.put("/settings", response_model=ApiResponse[ClinicNotificationSettingsResponse])
async def update_clinic_settings(
    data: ClinicNotificationSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ClinicNotificationSettingsResponse]:
    """Update notification settings for the clinic.

    Per-type ``settings`` control which notifications fire automatically vs
    manually; ``preferred_channel`` / ``fallback_enabled`` /
    ``manual_channels`` control which channel they use. Channel values must
    be available to this clinic (422 otherwise).
    """
    payload = data.model_dump(exclude_unset=True)
    current = await NotificationService.get_or_create_clinic_settings(db, ctx.clinic_id)
    available = await NotificationService.available_channels(db, ctx.clinic_id)

    if (
        payload.get("preferred_channel") is not None
        and payload["preferred_channel"] not in available
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"preferred_channel '{payload['preferred_channel']}' is not available "
                f"for this clinic (available: {available})"
            ),
        )

    manual = payload.get("manual_channels")
    if manual is not None:
        unavailable = [c for c in manual if c not in available]
        if unavailable:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"manual_channels {unavailable} are not available "
                    f"for this clinic (available: {available})"
                ),
            )

    # Invariant: the preferred channel is always a manual channel too, so
    # staff can resend on the same wire. Insert it if the client omitted it.
    preferred = payload.get("preferred_channel") or current.preferred_channel
    effective_manual = list(manual if manual is not None else (current.manual_channels or []))
    if preferred not in effective_manual:
        payload["manual_channels"] = [preferred, *effective_manual]

    settings = await NotificationService.update_clinic_settings(db, ctx.clinic_id, payload)
    return ApiResponse(data=_settings_response(settings, available))


# ============================================================================
# Email Log Endpoints
# ============================================================================


@router.get("/logs", response_model=PaginatedApiResponse[EmailLogResponse])
async def list_email_logs(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.logs.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    patient_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None, max_length=20),
    template_key: str | None = Query(default=None, max_length=100),
) -> PaginatedApiResponse[EmailLogResponse]:
    """List email logs for the clinic.

    Can be filtered by patient, status, or template.
    """
    logs, total = await NotificationService.list_logs(
        db,
        ctx.clinic_id,
        page=page,
        page_size=page_size,
        patient_id=patient_id,
        status=status,
        template_key=template_key,
    )
    return PaginatedApiResponse(
        data=[EmailLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================================================
# Manual Send Endpoints
# ============================================================================


@router.post("/send", response_model=ApiResponse[ManualSendResponse])
async def send_notification(
    data: ManualSendRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.send"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ManualSendResponse]:
    """Manually send a notification.

    Used for notifications that are not auto-sent, like welcome messages
    or budget messages when auto_send is disabled. Optional ``channels``
    picks the wire (e.g. ``["whatsapp"]``); the recipient is resolved per
    channel (phone for WhatsApp, email for email). Without ``channels`` the
    legacy email behaviour applies.
    """
    from sqlalchemy import select

    from app.modules.agenda.models import Appointment
    from app.modules.patients.models import Patient

    # Get patient if provided
    patient = None
    patient_email = None

    if data.patient_id:
        result = await db.execute(
            select(Patient).where(
                Patient.id == data.patient_id,
                Patient.clinic_id == ctx.clinic_id,
            )
        )
        patient = result.scalar_one_or_none()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        # Legacy (no channels requested): email is the only wire, so a
        # missing email is a hard 400. With explicit channels the recipient
        # is validated per channel below — a phone-only patient can receive
        # a WhatsApp send.
        if not data.channels and not patient.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient has no email address",
            )
        patient_email = patient.email

    # Build context based on notification type
    context = data.custom_context or {}

    if patient:
        context["patient_name"] = f"{patient.first_name} {patient.last_name}"

    # Get clinic info
    from app.core.auth.models import Clinic

    result = await db.execute(select(Clinic).where(Clinic.id == ctx.clinic_id))
    clinic = result.scalar_one_or_none()
    if clinic:
        context["clinic_name"] = clinic.name
        context["clinic_phone"] = clinic.phone
        context["clinic_address"] = clinic.address

    # Handle appointment-related notifications
    if data.notification_type in [
        "appointment_confirmation",
        "appointment_reminder",
        "appointment_cancelled",
    ]:
        if not data.appointment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="appointment_id is required for appointment notifications",
            )

        result = await db.execute(
            select(Appointment).where(
                Appointment.id == data.appointment_id,
                Appointment.clinic_id == ctx.clinic_id,
            )
        )
        appointment = result.scalar_one_or_none()
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        context["appointment_date"] = appointment.start_time.strftime("%d/%m/%Y")
        context["appointment_time"] = appointment.start_time.strftime("%H:%M")

        # Get professional
        if appointment.professional_id:
            from app.core.auth.models import User

            result = await db.execute(select(User).where(User.id == appointment.professional_id))
            professional = result.scalar_one_or_none()
            if professional:
                context["professional_name"] = f"{professional.first_name} {professional.last_name}"

        # Use patient from appointment if not provided
        if not patient:
            result = await db.execute(select(Patient).where(Patient.id == appointment.patient_id))
            patient = result.scalar_one_or_none()
            if patient:
                context["patient_name"] = f"{patient.first_name} {patient.last_name}"
                patient_email = patient.email

    # Handle budget notifications
    if data.notification_type in ["budget_sent", "budget_accepted"]:
        if not data.budget_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="budget_id is required for budget notifications",
            )

        from app.modules.budget.models import Budget, BudgetItem

        result = await db.execute(
            select(Budget).where(
                Budget.id == data.budget_id,
                Budget.clinic_id == ctx.clinic_id,
            )
        )
        budget = result.scalar_one_or_none()
        if not budget:
            raise HTTPException(status_code=404, detail="Budget not found")

        context["budget_number"] = budget.budget_number
        context["budget_date"] = budget.valid_from.strftime("%d/%m/%Y")
        context["total"] = float(budget.total)
        context["subtotal"] = float(budget.subtotal)
        context["discount_amount"] = float(budget.total_discount) if budget.total_discount else None
        context["notes"] = budget.patient_notes

        if budget.valid_until:
            context["validity_days"] = (budget.valid_until - budget.valid_from).days

        if data.notification_type == "budget_accepted":
            context["accepted_date"] = budget.updated_at.strftime("%d/%m/%Y")

        # Get budget items for budget_sent
        if data.notification_type == "budget_sent":
            result = await db.execute(select(BudgetItem).where(BudgetItem.budget_id == budget.id))
            items = result.scalars().all()

            treatments = []
            for item in items:
                from app.modules.catalog.models import TreatmentCatalogItem

                result = await db.execute(
                    select(TreatmentCatalogItem).where(
                        TreatmentCatalogItem.id == item.catalog_item_id
                    )
                )
                catalog_item = result.scalar_one_or_none()
                treatments.append(
                    {
                        "name": catalog_item.name if catalog_item else "Tratamiento",
                        "tooth": item.tooth_number,
                        "price": float(item.line_total),
                    }
                )
            context["treatments"] = treatments

        # Use patient from budget if not provided
        if not patient:
            result = await db.execute(select(Patient).where(Patient.id == budget.patient_id))
            patient = result.scalar_one_or_none()
            if patient:
                context["patient_name"] = f"{patient.first_name} {patient.last_name}"
                patient_email = patient.email

    if data.channels:
        # Recipient per requested channel: phone for WhatsApp, email for
        # email. A phone-only patient must not 400 on a WhatsApp send.
        has_recipient = any(
            (channel == "whatsapp" and patient is not None and patient.phone)
            or (channel == "email" and patient_email)
            for channel in data.channels
        )
        if not has_recipient:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient has no contact address for the requested channels",
            )
    elif not patient_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine recipient email address",
        )

    # Enqueue the notification (force_send=True to bypass auto_send check).
    # Delivery happens asynchronously via the outbox dispatch job.
    msg = await NotificationGateway.enqueue(
        db=db,
        clinic_id=ctx.clinic_id,
        notification_type=data.notification_type,
        context=context,
        patient_id=patient.id if patient else None,
        to_address=patient_email,
        channels=data.channels,
        triggered_by_user_id=ctx.user.id,
        force_send=True,
    )

    if msg is not None and msg.status == "queued":
        return ApiResponse(
            data=ManualSendResponse(
                success=True,
                message="Notificación encolada para envío",
                log_id=msg.id,
            )
        )

    reason = msg.error_message if msg else "no se pudo encolar"
    return ApiResponse(
        data=ManualSendResponse(
            success=False,
            message=f"No se pudo enviar: {reason}",
            log_id=msg.id if msg else None,
        )
    )


# ============================================================================
# Conversation Endpoints (patient message thread + reply)
# ============================================================================


@router.get(
    "/channels",
    response_model=ApiResponse[ChannelAvailabilityResponse],
)
async def list_available_channels(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.logs.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ChannelAvailabilityResponse]:
    """Channels with a registered adapter that is configured for this clinic.

    Same permission as the conversation thread — the card that gates on
    this renders for every role that can read the thread.
    """
    from .channels import channel_registry

    available: list[str] = []
    for channel in channel_registry.available_channels():
        adapter = channel_registry.get_for_channel(channel)
        if adapter is not None and await adapter.supports(db, ctx.clinic_id):
            available.append(channel.value)
    return ApiResponse(data=ChannelAvailabilityResponse(available=available))


@router.get(
    "/conversations/{patient_id}",
    response_model=ApiResponse[list[ConversationMessageResponse]],
)
async def get_conversation(
    patient_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.logs.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    channel: str | None = Query(default=None, max_length=20),
) -> ApiResponse[list[ConversationMessageResponse]]:
    """Return a patient's message thread (inbound + outbound), oldest first."""
    messages = await NotificationService.list_conversation(
        db, ctx.clinic_id, patient_id, channel=channel
    )
    return ApiResponse(data=[ConversationMessageResponse.model_validate(m) for m in messages])


@router.post(
    "/conversations/{patient_id}/reply",
    response_model=ApiResponse[ConversationMessageResponse],
    status_code=status.HTTP_201_CREATED,
)
async def reply_to_conversation(
    patient_id: UUID,
    data: ConversationReplyRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.send"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ConversationMessageResponse]:
    """Send a free-form reply to the patient (within the 24h session window)."""
    msg = await NotificationGateway.enqueue(
        db,
        ctx.clinic_id,
        "reply",
        context={},
        patient_id=patient_id,
        channels=[data.channel],
        message_kind="session",
        body_text=data.body,
        force_send=True,
        triggered_by_user_id=ctx.user.id,
    )
    if msg is None or msg.status == "skipped":
        reason = msg.error_message if msg else "no se pudo enviar"
        # Most common: the 24h free-form window is closed → needs a template.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No se puede responder en texto libre: la ventana de 24h está "
                f"cerrada o el canal no está disponible ({reason})."
            ),
        )
    return ApiResponse(data=ConversationMessageResponse.model_validate(msg))


# ============================================================================
# SMTP Settings Endpoints
# ============================================================================


@router.get("/smtp-settings", response_model=ApiResponse[SmtpSettingsResponse])
async def get_smtp_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SmtpSettingsResponse]:
    """Get SMTP settings for the clinic.

    Returns the current SMTP configuration. Passwords are never returned,
    only a flag indicating if one is set.
    """
    settings = await NotificationService.get_or_create_smtp_settings(db, ctx.clinic_id)

    return ApiResponse(
        data=SmtpSettingsResponse(
            provider=settings.provider,
            host=settings.host,
            port=settings.port,
            username=settings.username,
            has_password=bool(settings.password_encrypted),
            use_tls=settings.use_tls,
            use_ssl=settings.use_ssl,
            from_email=settings.from_email,
            from_name=settings.from_name,
            is_active=settings.is_active,
            is_verified=settings.is_verified,
            last_verified_at=settings.last_verified_at,
        )
    )


@router.put("/smtp-settings", response_model=ApiResponse[SmtpSettingsResponse])
async def update_smtp_settings(
    data: SmtpSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SmtpSettingsResponse]:
    """Update SMTP settings for the clinic.

    Passwords are encrypted before storage. If password is not provided
    in the update, the existing password is preserved.
    """
    settings = await NotificationService.update_smtp_settings(
        db, ctx.clinic_id, data.model_dump(exclude_unset=True)
    )

    return ApiResponse(
        data=SmtpSettingsResponse(
            provider=settings.provider,
            host=settings.host,
            port=settings.port,
            username=settings.username,
            has_password=bool(settings.password_encrypted),
            use_tls=settings.use_tls,
            use_ssl=settings.use_ssl,
            from_email=settings.from_email,
            from_name=settings.from_name,
            is_active=settings.is_active,
            is_verified=settings.is_verified,
            last_verified_at=settings.last_verified_at,
        )
    )


@router.post("/smtp-settings/test", response_model=ApiResponse[TestEmailResponse])
async def test_smtp_settings(
    data: SmtpTestRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[TestEmailResponse]:
    """Test SMTP connection with the provided settings.

    Sends a test email to verify the configuration before saving.
    On success, marks the SMTP settings as verified.
    """
    result = await NotificationService.test_smtp_settings(
        db=db,
        clinic_id=ctx.clinic_id,
        host=data.host,
        port=data.port,
        username=data.username,
        password=data.password,
        use_tls=data.use_tls,
        use_ssl=data.use_ssl,
        from_email=data.from_email,
        to_email=data.to_email,
    )

    return ApiResponse(
        data=TestEmailResponse(
            success=result.is_success,
            message="Conexión SMTP exitosa. Email de prueba enviado."
            if result.is_success
            else f"Error: {result.error_message}",
            provider="smtp",
        )
    )


# ============================================================================
# Test Email Endpoint
# ============================================================================


@router.post("/test", response_model=ApiResponse[TestEmailResponse])
async def test_email_connection(
    data: TestEmailRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("notifications.settings.write"))],
) -> ApiResponse[TestEmailResponse]:
    """Send a test email to verify email configuration.

    Requires admin permissions.
    """
    result = await NotificationService.test_email_connection(data.to_email)

    return ApiResponse(
        data=TestEmailResponse(
            success=result.is_success,
            message="Test email enviado correctamente"
            if result.is_success
            else f"Error: {result.error_message}",
            provider=result.provider,
        )
    )
