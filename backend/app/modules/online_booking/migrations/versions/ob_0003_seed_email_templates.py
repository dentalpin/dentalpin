"""Seed the system email templates for booking confirmation and rejection.

``booking_confirmation`` carries the one-time confirmation link and
``booking_rejection`` the reception message. Both are rendered by the
notifications gateway at dispatch time, like every other email type.

One system row (``clinic_id`` NULL, ``is_system``) per type and locale.
Spanish and English are real copy; the ten other locales the interface
ships hold the English copy until translated. Clinics can override any
key/locale with their own row, which takes precedence and is never touched
here. Downgrade removes exactly the seeded rows (matched by the marker).

Revision ID: ob_0003
Revises: ob_0002
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ob_0003"
down_revision: str | None = "ob_0002"
branch_labels: str | Sequence[str] | None = None
# The seed INSERTs into notification_templates, which notif_0002 created and
# whose channel column notif_0008 last touched. notifications is
# removable=False, so no branch uninstall ever downgrades through this edge
# (same drag edge as smg_0002).
depends_on: str | Sequence[str] | None = ("notif_0008",)

MARKER = "Seeded by online_booking ob_0003 (system booking email templates)"

OTHER_LOCALES = ("ar", "de", "fr", "hi", "hu", "it", "pl", "pt", "ta", "te")

# Plain placeholders only; no medical data. ``confirm_url`` is a one-time
# link, so it appears solely in the confirmation message.
COPY: dict[str, dict[str, dict[str, str]]] = {
    "es": {
        "booking_confirmation": {
            "subject": "Confirma tu solicitud de cita en {{ clinic_name }}",
            "title": "Confirma tu solicitud de cita",
            "greeting": "Hola {{ patient_name }},",
            "intro": (
                "Hemos recibido tu solicitud de cita en <strong>{{ clinic_name }}</strong> "
                "para el <strong>{{ appointment_date }}</strong> a las "
                "<strong>{{ appointment_time }}</strong>."
            ),
            "action": (
                "Confírmala en los próximos {{ expires_minutes }} minutos para que "
                "podamos revisarla:"
            ),
            "button": "Confirmar mi solicitud",
            "after": (
                "Cuando la confirmes, el equipo de la clínica la revisará y se pondrá "
                "en contacto contigo. Hasta entonces la cita no está reservada."
            ),
            "ignore": "Si no has sido tú, puedes ignorar este mensaje.",
            "footer": "Este email fue enviado por",
            "text": (
                "Hola {{ patient_name }},\n\n"
                "Hemos recibido tu solicitud de cita en {{ clinic_name }} para el "
                "{{ appointment_date }} a las {{ appointment_time }}.\n\n"
                "Confírmala en los próximos {{ expires_minutes }} minutos para que "
                "podamos revisarla:\n{{ confirm_url }}\n\n"
                "Cuando la confirmes, el equipo de la clínica la revisará y se pondrá "
                "en contacto contigo. Hasta entonces la cita no está reservada.\n\n"
                "Si no has sido tú, puedes ignorar este mensaje.\n"
            ),
        },
        "booking_rejection": {
            "subject": "Novedades sobre tu solicitud de cita en {{ clinic_name }}",
            "title": "Sobre tu solicitud de cita",
            "greeting": "Hola {{ patient_name }},",
            "intro": (
                "Lo sentimos: no hemos podido aceptar tu solicitud de cita en "
                "<strong>{{ clinic_name }}</strong> para el "
                "<strong>{{ appointment_date }}</strong> a las "
                "<strong>{{ appointment_time }}</strong>."
            ),
            "message_label": "Mensaje de la clínica:",
            "action": "Si quieres, puedes pedir otra hora o ponerte en contacto con nosotros.",
            "footer": "Este email fue enviado por",
            "text": (
                "Hola {{ patient_name }},\n\n"
                "Lo sentimos: no hemos podido aceptar tu solicitud de cita en "
                "{{ clinic_name }} para el {{ appointment_date }} a las "
                "{{ appointment_time }}.\n\n"
                "Mensaje de la clínica:\n{{ rejection_message }}\n\n"
                "Si quieres, puedes pedir otra hora o ponerte en contacto con nosotros.\n"
            ),
        },
    },
    "en": {
        "booking_confirmation": {
            "subject": "Confirm your appointment request at {{ clinic_name }}",
            "title": "Confirm your appointment request",
            "greeting": "Hello {{ patient_name }},",
            "intro": (
                "We received your appointment request at <strong>{{ clinic_name }}</strong> "
                "for <strong>{{ appointment_date }}</strong> at "
                "<strong>{{ appointment_time }}</strong>."
            ),
            "action": (
                "Please confirm it within the next {{ expires_minutes }} minutes so "
                "that we can review it:"
            ),
            "button": "Confirm my request",
            "after": (
                "Once you confirm, the clinic team will review it and get in touch "
                "with you. Until then the appointment is not booked."
            ),
            "ignore": "If this was not you, you can ignore this message.",
            "footer": "This email was sent by",
            "text": (
                "Hello {{ patient_name }},\n\n"
                "We received your appointment request at {{ clinic_name }} for "
                "{{ appointment_date }} at {{ appointment_time }}.\n\n"
                "Please confirm it within the next {{ expires_minutes }} minutes so "
                "that we can review it:\n{{ confirm_url }}\n\n"
                "Once you confirm, the clinic team will review it and get in touch "
                "with you. Until then the appointment is not booked.\n\n"
                "If this was not you, you can ignore this message.\n"
            ),
        },
        "booking_rejection": {
            "subject": "Update on your appointment request at {{ clinic_name }}",
            "title": "About your appointment request",
            "greeting": "Hello {{ patient_name }},",
            "intro": (
                "We are sorry: we could not accept your appointment request at "
                "<strong>{{ clinic_name }}</strong> for "
                "<strong>{{ appointment_date }}</strong> at "
                "<strong>{{ appointment_time }}</strong>."
            ),
            "message_label": "Message from the clinic:",
            "action": "You are welcome to request another time or contact us.",
            "footer": "This email was sent by",
            "text": (
                "Hello {{ patient_name }},\n\n"
                "We are sorry: we could not accept your appointment request at "
                "{{ clinic_name }} for {{ appointment_date }} at "
                "{{ appointment_time }}.\n\n"
                "Message from the clinic:\n{{ rejection_message }}\n\n"
                "You are welcome to request another time or contact us.\n"
            ),
        },
    },
}


def _html(locale: str, key: str, copy: dict[str, str]) -> str:
    # The footer wording is a top-level assignment so the parent layout sees it.
    parts = [
        '{% extends "base.html" %}',
        "{% set footer_sent_by = '"
        + copy["footer"]
        + " ' ~ (clinic_name | default('DentalPin')) %}",
        "{% block title %}" + copy["subject"] + "{% endblock %}",
        "{% block content %}",
        "<h2>" + copy["title"] + "</h2>",
        "<p>" + copy["greeting"] + "</p>",
        "<p>" + copy["intro"] + "</p>",
    ]
    if key == "booking_confirmation":
        parts += [
            "<p>" + copy["action"] + "</p>",
            '<div class="button-container">'
            '<a href="{{ confirm_url }}" class="button">' + copy["button"] + "</a></div>",
            "<p>" + copy["after"] + "</p>",
            "<p>" + copy["ignore"] + "</p>",
        ]
    else:
        parts += [
            "<p>" + copy["message_label"] + "</p>",
            "<blockquote>{{ rejection_message }}</blockquote>",
            "<p>" + copy["action"] + "</p>",
        ]
    parts.append("{% endblock %}")
    return "\n".join(parts) + "\n"


def _text(copy: dict[str, str]) -> str:
    # Plain text must not be HTML-escaped (the link and the clinic message).
    return "{% autoescape false %}" + copy["text"] + "{% endautoescape %}"


def _rows() -> list[dict[str, str]]:
    rows = []
    for locale in ("es", "en", *OTHER_LOCALES):
        language = locale if locale in COPY else "en"
        for key, copy in COPY[language].items():
            rows.append(
                {
                    "key": key,
                    "locale": locale,
                    "subject": copy["subject"],
                    "html": _html(language, key, copy),
                    "text": _text(copy),
                    "marker": MARKER,
                }
            )
    return rows


_INSERT = sa.text(
    """
INSERT INTO notification_templates
    (id, clinic_id, channel, template_key, locale, subject, body_html,
     body_text, is_system, is_active, description, created_at, updated_at)
SELECT gen_random_uuid(), NULL, 'email',
       CAST(:key AS VARCHAR(100)), CAST(:locale AS VARCHAR(5)),
       CAST(:subject AS VARCHAR(255)), CAST(:html AS TEXT), CAST(:text AS TEXT),
       TRUE, TRUE, CAST(:marker AS VARCHAR(500)), now(), now()
WHERE NOT EXISTS (
    SELECT 1 FROM notification_templates
    WHERE clinic_id IS NULL
      AND channel = 'email'
      AND template_key = :key
      AND locale = :locale
)
"""
)

_DELETE = sa.text(
    """
DELETE FROM notification_templates
WHERE clinic_id IS NULL
  AND channel = 'email'
  AND description = :marker
"""
)


def upgrade() -> None:
    conn = op.get_bind()
    for row in _rows():
        conn.execute(_INSERT, row)


def downgrade() -> None:
    op.get_bind().execute(_DELETE, {"marker": MARKER})
