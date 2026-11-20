"""Prepare WhatsApp drafts for staff using the notification outbox."""

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import phonenumbers
from jinja2 import TemplateError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.notifications.channels import AdapterResult, Channel, OutboundMessage, SendStatus
from app.modules.notifications.models import ClinicChannelSettings
from app.modules.notifications.template_rendering import render_whatsapp_text, whatsapp_text_fits

ADAPTER_NAME = "whatsapp_manual"


class ManualWhatsAppAdapter:
    """Opt-in, clinic-selected transport that performs no network I/O."""

    channel = Channel.WHATSAPP
    adapter_name = ADAPTER_NAME
    requires_provider_template = False
    requires_whatsapp_opt_in = True
    manual_delivery = True
    supports_session_replies = False

    async def supports(self, db: AsyncSession, clinic_id: UUID) -> bool:
        """Only clinics explicitly configured for manual WhatsApp are eligible."""
        return bool(
            await db.scalar(
                select(ClinicChannelSettings.id).where(
                    ClinicChannelSettings.clinic_id == clinic_id,
                    ClinicChannelSettings.channel == self.channel,
                    ClinicChannelSettings.adapter_name == self.adapter_name,
                    ClinicChannelSettings.is_enabled.is_(True),
                )
            )
        )

    async def normalize_recipient(
        self, db: AsyncSession, clinic_id: UUID, address: str
    ) -> str | None:
        """Resolve local mobile numbers using the clinic's configured country."""
        clinic = await db.get(Clinic, clinic_id)
        if clinic is None:
            return None
        region = (clinic.settings or {}).get("country")
        try:
            number = phonenumbers.parse(
                address, region.upper() if isinstance(region, str) else None
            )
        except phonenumbers.NumberParseException:
            return None
        if number.extension or not phonenumbers.is_valid_number(number):
            return None
        if phonenumbers.number_type(number) not in (
            phonenumbers.PhoneNumberType.MOBILE,
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
        ):
            return None
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)

    async def send(self, db: AsyncSession, msg: OutboundMessage) -> AdapterResult:
        """Render a clinic template or retain literal staff text for the tray."""
        try:
            plain = msg.body_text or ""
            if not msg.metadata.get("literal_body"):
                context = dict(msg.context)
                raw_start = context.get("appointment_start_at")
                if isinstance(raw_start, str):
                    start = datetime.fromisoformat(raw_start)
                    clinic = await db.get(Clinic, msg.clinic_id)
                    if clinic and start.utcoffset() is not None:
                        local_start = start.astimezone(ZoneInfo(clinic.timezone))
                        context["appointment_date"] = local_start.strftime("%d/%m/%Y")
                        context["appointment_time"] = local_start.strftime("%H:%M")
                plain = render_whatsapp_text(plain, context)
        except (TemplateError, ValueError):
            return AdapterResult(
                SendStatus.SKIPPED, self.adapter_name, error_message="invalid_whatsapp_template"
            )
        plain = plain.strip()
        if not whatsapp_text_fits(plain):
            return AdapterResult(
                SendStatus.SKIPPED, self.adapter_name, error_message="invalid_whatsapp_draft"
            )
        return AdapterResult(SendStatus.DEFERRED, self.adapter_name, body_text=plain)
